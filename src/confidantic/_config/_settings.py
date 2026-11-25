"""Settings-source assembly, default barriers, provenance, and schema integration.

Builders own per-call option mappings; sources own their collected values and
provenance. Importable schema callbacks bridge these objects to BaseConfig's
overridable hooks without capturing context-local validation state.
"""

from collections.abc import Callable, Collection, Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import wraps
from inspect import Parameter, get_annotations, signature
from typing import Any, cast

from pydantic import ConfigDict, GetCoreSchemaHandler, PydanticUserError, TypeAdapter
from pydantic.fields import FieldInfo
from pydantic_core import CoreSchema, core_schema
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
)
from pydantic_settings.sources import DefaultSettingsSource
from pydantic_settings.sources.types import ENV_FILE_SENTINEL
from pydantic_settings.sources.utils import InitState, _get_alias_names

from confidantic._config._cli import _CliSettings
from confidantic._config._nested import _NestedModelUpdates
from confidantic._config._options import _CUSTOM_CONFIG_KEYS
from confidantic.utils import is_runtime_jupyterlike

_FieldSource = tuple[type[PydanticBaseSettingsSource], type[BaseSettings]]
_SourceResult = tuple[tuple[PydanticBaseSettingsSource, ...], dict[str, Any]]

# Ordinary default factories and discriminated defaults block lower-priority
# sources. Pydantic, rather than the source builder, evaluates their actual value.
_FACTORY_DEFAULT = object()


@dataclass(frozen=True)
class _CopiedDefault:
    """Copy a generated default while retaining its settings-merge template.

    Attributes
    ----------
    template
        Original default retained by reference. Each call deep-copies it, so
        generated fields and settings sources receive independent values. Copy
        errors propagate to the caller.
    """

    template: Any

    def __call__(self) -> Any:
        return deepcopy(self.template)


class ClassDefaultsSource(PydanticBaseSettingsSource):
    """Load defaults declared directly on one settings class.

    Static defaults become source values so they participate in BaseConfig's
    per-MRO priority and nested merging. Default factories and discriminated
    defaults act as whole-field barriers until Pydantic evaluates them during
    validation. Generated copy-default wrappers contribute independently copied
    templates instead, preserving static-default merging without sharing state.

    Parameters
    ----------
    settings_cls
        Settings class whose defaults are loaded.
    field_names
        Field names to consider. By default, use fields declared directly on
        ``settings_cls``.
    _init_state
        Optional source state shared with other Pydantic Settings sources.

    Attributes
    ----------
    defaults
        Collected source values, keyed by the first validation alias or field
        name. Deferred defaults use an internal barrier sentinel until settings
        assembly removes it and Pydantic evaluates the field's actual default.
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        field_names: Collection[str] | None = None,
        _init_state: InitState | None = None,
    ) -> None:
        super().__init__(settings_cls, _init_state)
        self.defaults: dict[str, Any] = {}
        field_names = (
            get_annotations(settings_cls) if field_names is None else field_names
        )
        for field_name in field_names:
            if field_name not in settings_cls.model_fields:
                continue
            field = settings_cls.model_fields[field_name]
            if field.is_required():
                continue

            aliases, _ = _get_alias_names(field_name, field)
            key = aliases[0] if aliases else field_name
            if (
                field.default_factory is not None
                and not isinstance(field.default_factory, _CopiedDefault)
            ) or _NestedModelUpdates.has_discriminator(field):
                self.defaults[key] = _FACTORY_DEFAULT
            else:
                default = (
                    field.default_factory()
                    if isinstance(field.default_factory, _CopiedDefault)
                    else field.get_default(call_default_factory=False)
                )
                adapter_config = (
                    ConfigDict(arbitrary_types_allowed=True)
                    if settings_cls.model_config.get("arbitrary_types_allowed")
                    else None
                )
                annotation = cast(Any, field.annotation)
                try:
                    adapter: TypeAdapter[Any] = TypeAdapter(
                        annotation, config=adapter_config
                    )
                except PydanticUserError as error:
                    if error.code != "type-adapter-config-unused":
                        raise
                    adapter = TypeAdapter(annotation)
                self.defaults[key] = adapter.dump_python(default)

    def __call__(self) -> dict[str, Any]:
        """Return the collected defaults mapping without making another copy."""
        return self.defaults

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        """Satisfy the source interface; defaults are collected in bulk instead."""
        return None, "", False  # pragma: no cover


class _InitSettingsSource(InitSettingsSource):
    """Keep mapping values intact when upstream hashing cannot normalize them.

    Only the unhashable-dictionary TypeError falls back to the stored init
    mapping. Other upstream failures propagate without changing their meaning.
    """

    def __call__(self) -> dict[str, Any]:
        try:
            return super().__call__()
        except TypeError as error:
            if "unhashable type: 'dict'" not in str(error):
                raise
            return self.init_kwargs


class _ProvenanceSource(PydanticBaseSettingsSource):
    """Record top-level source winners without contributing settings values.

    The source chain's intermediate states identify the first source supplying
    each field. init_fields tracks unchanged inputs from the actual init source
    supplied to the customization hook, so copying can retain prior provenance.
    Bare callables provide no source state and therefore disable provenance.

    Parameters
    ----------
    settings_cls
        Concrete model whose field names and aliases identify source winners.
    sources
        Sources in descending priority, excluding this terminal observer.
    _init_state
        Shared upstream source state used to inspect the final merged values.
    nested_model_default_partial_update
        Effective policy retained for the nested-update preparation step.

    Attributes
    ----------
    field_sources
        Canonical declared field names mapped to source and settings classes.
        Recomputed on each call; extra fields are not included.
    init_fields
        Declared fields and extras supplied by unchanged entries in the marked
        initialization source. Validated copies use these to retain metadata.
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        sources: tuple[PydanticBaseSettingsSource, ...],
        _init_state: InitState,
        nested_model_default_partial_update: bool,
    ) -> None:
        super().__init__(settings_cls, _init_state)
        self.sources = sources
        self.nested_model_default_partial_update = nested_model_default_partial_update
        self.field_sources: dict[str, _FieldSource] = {}
        self.init_fields: set[str] = set()

    def __call__(self) -> dict[str, Any]:
        """Refresh winner metadata from successive source states and return no values."""
        self.field_sources.clear()
        self.init_fields.clear()
        if not all(
            isinstance(source, PydanticBaseSettingsSource) for source in self.sources
        ):
            return {}

        field_keys = {
            name: (*_get_alias_names(name, field)[0], name)
            for name, field in self.settings_cls.model_fields.items()
        }
        known_keys = {key for keys in field_keys.values() for key in keys}
        extra_keys = self.current_state.keys() - known_keys
        for field_name, keys in (
            field_keys | {key: (key,) for key in extra_keys}
        ).items():
            for index, source in enumerate(self.sources):
                next_state = (
                    self.sources[index + 1].current_state
                    if index + 1 < len(self.sources)
                    else self.current_state
                )
                if any(
                    key not in source.current_state and key in next_state
                    for key in keys
                ):
                    if field_name in field_keys:
                        self.field_sources[field_name] = (
                            InitSettingsSource
                            if isinstance(source, _InitSettingsSource)
                            else type(source),
                            source.settings_cls,
                        )
                    if any(
                        key in getattr(source, "_confidantic_init_input", ())
                        for key in keys
                    ):
                        self.init_fields.add(field_name)
                    break

        return {}

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        return None, "", False  # pragma: no cover


class _SettingsSources:
    """Build and finalize the source chain for one settings construction.

    Parameters
    ----------
    model_type
        Concrete settings class whose public hook is being dispatched.
    levels
        Concrete-to-parent MRO levels, excluding BaseConfig itself. The caller
        selects this boundary so this module need not import BaseConfig.
    options
        Arguments already bound against the current upstream source-builder
        signature, including its defaults.
    find_dotenv
        Bound discovery hook on the concrete class, called at most once.

    Notes
    -----
    build returns the upstream source tuple and init-kwargs contract. Values are
    merged by the caller's upstream hook before finalize_values removes default
    barriers and prepares nested updates. No builder is stored on a model.
    """

    def __init__(
        self,
        model_type: type[BaseSettings],
        *,
        levels: tuple[type[BaseSettings], ...],
        options: Mapping[str, Any],
        find_dotenv: Callable[[], str],
    ) -> None:
        self.model_type = model_type
        self.levels = levels
        self.options = dict(options)
        self.source_options = self.options.copy()
        self.init_kwargs = self.options["_init_kwargs"]
        if self.init_kwargs is None:
            self.init_kwargs = {}
        # This transient envelope carries custom per-call options through
        # overridable source hooks without adding arguments to their signatures.
        self.config_options = self.init_kwargs.pop("__confidantic_config_options", {})
        self.find_dotenv = find_dotenv

    def build(self, fallback: Callable[..., _SourceResult]) -> _SourceResult:
        """Assemble MRO sources, or use the bound super hook for bare BaseConfig.

        Parameters
        ----------
        fallback
            Bound upstream source builder, used when no subclass levels exist.

        Returns
        -------
        tuple
            Source tuple and initialization mapping for upstream value assembly.
            Subclass chains retain CLI sources only at the concrete level,
            append each level's declared defaults, and finish with provenance.

        Notes
        -----
        Dotenv discovery runs at most once per build. Sources are constructed
        here but their values are merged later by the upstream settings hook.
        """
        model_config = {**self.model_type.model_config, **self.config_options}
        env_file = self.options["_env_file"]
        if model_config.get("env_file_discovery") and (
            env_file is None
            or (env_file is ENV_FILE_SENTINEL and model_config.get("env_file") is None)
        ):
            self.source_options["_env_file"] = self.find_dotenv()
        if not self.levels:
            if self.source_options.get("_env_prefix") is None:
                self.source_options["_env_prefix"] = ""
            return fallback(**self.source_options)

        resolved_sources: list[PydanticBaseSettingsSource] = []
        init_state = InitState()
        partial_update = False
        for index, level in enumerate(self.levels):
            level_sources, default_source = self._sources_for_level(
                level, concrete=index == 0
            )
            if index == 0:
                partial_update = bool(
                    default_source.nested_model_default_partial_update
                )
            init_state = default_source._init_state
            resolved_sources.extend(
                source
                for source in level_sources
                if not isinstance(source, DefaultSettingsSource)
                and (index == 0 or not isinstance(source, CliSettingsSource))
            )
            defaults = ClassDefaultsSource(
                level, _init_state=default_source._init_state
            )
            if defaults.defaults:
                resolved_sources.append(defaults)

        sources = tuple(resolved_sources)
        provenance = _ProvenanceSource(
            self.model_type,
            sources,
            _init_state=init_state,
            nested_model_default_partial_update=partial_update,
        )
        return (*sources, provenance), self.init_kwargs

    def _sources_for_level(
        self, level: type[BaseSettings], *, concrete: bool
    ) -> tuple[tuple[PydanticBaseSettingsSource, ...], DefaultSettingsSource]:
        """Let upstream build one class's sources, then normalize built-in sources.

        Parameters
        ----------
        level
            Settings class at the current position in the concrete-to-parent MRO.
        concrete
            Whether this is the most-derived level, where CLI parsing is enabled.

        Returns
        -------
        tuple
            Normalized sources and their upstream default source. The latter
            supplies shared init state and the effective partial-update policy.

        Notes
        -----
        Only exact built-in environment and init sources are removed or
        replaced; user subclasses retain their behavior. A disabled environment
        prefix leaves dotenv and secrets sources available.
        """
        source_builder = BaseSettings.__dict__["_settings_init_sources"].__get__(
            None, level
        )
        level_config = {**level.model_config, **self.config_options}
        cli = _CliSettings(level, self.options, level_config)
        cli_source = (
            cli.source(self.options["_cli_settings_source"]) if concrete else None
        )
        level_options = self.source_options | {
            "_env_prefix": cli.env_prefix or "",
            "_cli_parse_args": self.options["_cli_parse_args"] if concrete else False,
            "_cli_settings_source": cli_source,
            "_init_kwargs": self.init_kwargs,
        }
        level_sources, _ = source_builder(**level_options)
        normalized_sources = []
        for source in level_sources:
            # Exact-type checks retain user-defined source subclasses.
            if cli.env_prefix is None and type(source) is EnvSettingsSource:
                continue
            if type(source) is InitSettingsSource:
                replacement = _InitSettingsSource(
                    source.settings_cls,
                    source.init_kwargs,
                    source.nested_model_default_partial_update,
                    source._init_state,
                )
                cast(Any, replacement)._confidantic_init_input = getattr(
                    source, "_confidantic_init_input", ()
                )
                source = replacement
            normalized_sources.append(source)
        sources = tuple(normalized_sources)
        default_source = next(
            source
            for source in reversed(sources)
            if isinstance(source, DefaultSettingsSource)
        )
        return sources, default_source

    @staticmethod
    def finalize_values(
        model_type: type[BaseSettings],
        sources: tuple[PydanticBaseSettingsSource, ...],
        values: dict[str, Any],
    ) -> dict[str, Any]:
        """Remove untouched defaults and prepare the active nested-update scope.

        Parameters
        ----------
        model_type
            Concrete model that will validate the assembled values.
        sources
            Evaluated source chain, including class defaults and provenance.
        values
            Merged settings mapping. A new top-level mapping is returned.

        Returns
        -------
        dict[str, Any]
            Input for model validation with untouched defaults omitted, allowing
            Pydantic to apply them. When partial updates are enabled, nested
            model baselines are also recorded in the active scope and unpatched
            initialization instances are restored in the returned mapping.
        """
        defaults: dict[str, Any] = {}
        seen_defaults: set[str] = set()
        for source in sources:
            if isinstance(source, ClassDefaultsSource):
                for key, value in source.defaults.items():
                    if key in seen_defaults:
                        continue
                    seen_defaults.add(key)
                    if key not in source.current_state:
                        defaults[key] = value

        values = {
            key: value
            for key, value in values.items()
            if key not in defaults or defaults[key] != value
        }
        provenance = next(
            (
                source
                for source in reversed(sources)
                if isinstance(source, _ProvenanceSource)
            ),
            None,
        )
        updates = _NestedModelUpdates.current()
        if (
            provenance is not None
            and provenance.nested_model_default_partial_update
            and updates is not None
        ):
            updates.prepare(model_type, values, sources)
        return values

    @staticmethod
    def track_customization(method: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap a customization hook to mark unchanged initialization inputs.

        Parameters
        ----------
        method
            Unbound ``settings_customise_sources`` implementation. Its caller
            supplies ``init_settings`` as a keyword argument.

        Returns
        -------
        Callable
            Wrapper preserving the method's metadata and return value. After
            customization it marks keys still referring to their original
            objects on the supplied init source. A wrapper marker lets subclass
            initialization avoid wrapping the same implementation repeatedly.
        """

        @wraps(method)
        def tracked(*args: Any, **kwargs: Any) -> Any:
            # Mark the actual source supplied to the customization hook, rather
            # than treating every user-created InitSettingsSource as carried input.
            init_settings = kwargs["init_settings"]
            inputs = dict(init_settings.init_kwargs)
            sources = method(*args, **kwargs)
            init_settings._confidantic_init_input = {
                key
                for key, value in inputs.items()
                if key in init_settings.init_kwargs
                and init_settings.init_kwargs[key] is value
            }
            return sources

        cast(Any, tracked)._confidantic_tracks_init = True
        return tracked


def wrap_settings_schema(source: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
    """Wrap model validation while retaining recursive schema references.

    Parameters
    ----------
    source
        Model type with a ``_validate_settings`` hook.
    handler
        Pydantic schema generator for the underlying model.

    Returns
    -------
    CoreSchema
        Schema calling the settings hook around normal validation. A definition
        reference is returned unchanged; otherwise the reference belongs to the
        wrapper so recursive validation also assembles settings sources.
    """
    schema = handler(source)
    if schema["type"] == "definition-ref":
        return schema
    model_schema = dict(schema)
    # Recursive references must include source assembly, not just the inner model.
    reference = model_schema.pop("ref", None)
    return core_schema.no_info_wrap_validator_function(
        source._validate_settings, cast(CoreSchema, model_schema), ref=reference
    )


def validate_settings(
    model_type: type[BaseSettings], value: Any, handler: Callable[[Any], Any]
) -> Any:
    """Assemble settings inside the active Pydantic validation chain.

    Parameters
    ----------
    model_type
        Concrete settings class whose source hooks are dispatched.
    value
        Model input. Mappings are copied and split into settings options and
        field inputs; non-mapping inputs go directly to the validation handler.
    handler
        Remaining model validation chain, retaining its per-call options.

    Returns
    -------
    Any
        Validated result with provenance attached when the source chain tracks
        it. Source and validation errors propagate.

    Notes
    -----
    Automatic CLI parsing is suppressed in notebook and resolution contexts.
    A fresh nested-update scope spans value assembly and validation, restoring
    any enclosing scope on exit. Importable callbacks keep this transient state
    out of serialized model classes.
    """
    if not isinstance(value, Mapping):
        return handler(value)
    kwargs = dict(value)
    if _CliSettings.is_suppressed() or is_runtime_jupyterlike():
        kwargs["_cli_parse_args"] = False

    config_options = {
        name: kwargs.pop(f"_{name}")
        for name in _CUSTOM_CONFIG_KEYS
        if f"_{name}" in kwargs
    }

    build_sources = kwargs.pop("_build_sources", None)
    if build_sources is None:
        option_names = {
            name
            for method in (
                BaseSettings._settings_init_sources,
                model_type._settings_init_sources,
            )
            for name, parameter in signature(method).parameters.items()
            if parameter.kind
            in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
        }
        source_options = {
            key: kwargs.pop(key)
            for key in tuple(kwargs)
            if key in option_names and key != "_init_kwargs"
        }
        build_sources = model_type._settings_init_sources(
            **source_options,
            _init_kwargs={
                **kwargs,
                "__confidantic_config_options": config_options,
            },
        )

    with _NestedModelUpdates.scope():
        result = handler(model_type._settings_build_values(*build_sources))

    sources, _ = build_sources
    resolved_source = next(
        (
            source
            for source in reversed(sources)
            if isinstance(source, _ProvenanceSource)
        ),
        None,
    )
    if resolved_source is not None:
        result._model_field_sources = resolved_source.field_sources.copy()
        result._model_init_fields = resolved_source.init_fields.copy()
    return result
