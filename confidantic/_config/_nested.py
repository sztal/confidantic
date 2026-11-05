"""Nested model baselines scoped to one active settings validation.

The context variable bridges source assembly and Pydantic's field validators.
Only importable helper methods access it; model callbacks never capture a scope.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from types import UnionType
from typing import Annotated, Any, Union, get_args, get_origin

from pydantic import BaseModel, Discriminator, ValidationInfo
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    InitSettingsSource,
    PydanticBaseSettingsSource,
)
from pydantic_settings.sources.utils import _get_alias_names

# Factory-backed baselines must wait until previously validated field values
# are available. This sentinel is distinct from a whole-field source barrier.
_DEFERRED_MODEL_DEFAULT = object()
_ACTIVE_NESTED_UPDATES: ContextVar[_NestedModelUpdates | None] = ContextVar(
    "confidantic_nested_model_updates", default=None
)


class _NestedModelUpdates:
    """Retain and apply nested model baselines during one validation call.

    prepare selects baselines from the resolved source chain without evaluating
    ordinary default factories. apply runs at field-validation time, when
    validated-data factories can safely receive earlier field values. Nested
    scopes allocate separate maps and restore their enclosing scope on exit.

    Attributes
    ----------
    baselines
        Canonical field names mapped to existing model instances or a deferred
        default sentinel. Deferred entries are evaluated during field validation.
    """

    def __init__(self) -> None:
        self.baselines: dict[str, BaseModel | object] = {}

    @classmethod
    @contextmanager
    def scope(cls) -> Generator[_NestedModelUpdates]:
        """Activate a fresh baseline map until source assembly and validation end.

        Yields
        ------
        _NestedModelUpdates
            Isolated baseline state. The enclosing state is restored even if
            source assembly or validation raises an exception.
        """
        updates = cls()
        token = _ACTIVE_NESTED_UPDATES.set(updates)
        try:
            yield updates
        finally:
            _ACTIVE_NESTED_UPDATES.reset(token)

    @classmethod
    def current(cls) -> _NestedModelUpdates | None:
        """Return the active scope, or None outside settings validation."""
        return _ACTIVE_NESTED_UPDATES.get()

    def prepare(
        self,
        model_type: type[BaseSettings],
        values: dict[str, Any],
        sources: tuple[PydanticBaseSettingsSource, ...],
    ) -> None:
        """Select baselines and restore unpatched model instances in values.

        Parameters
        ----------
        model_type
            Concrete settings class supplying fields, aliases, and defaults.
        values
            Assembled input mapping, modified in place when an initialization
            model has no higher-priority patch and can be retained directly.
        sources
            Evaluated sources in priority order. Initialization model instances
            take precedence over field defaults as merge baselines.

        Notes
        -----
        Only mapping inputs need baselines. Discriminated fields are skipped,
        and ordinary default factories are deferred until field validation so
        they can receive previously validated fields.
        """
        for field_name, field in model_type.model_fields.items():
            if self.has_discriminator(field):
                continue
            aliases, _ = _get_alias_names(field_name, field)
            keys = aliases or (field_name,)
            selected_key = next(
                (candidate for candidate in keys if candidate in values),
                None,
            )
            if selected_key is None or not isinstance(values[selected_key], Mapping):
                continue

            for source in sources:
                if not isinstance(source, InitSettingsSource):
                    continue
                source_key = next(
                    (
                        candidate
                        for candidate in keys
                        if candidate in source.init_kwargs
                    ),
                    None,
                )
                if source_key is None:
                    continue
                baseline = source.init_kwargs[source_key]
                if not isinstance(baseline, BaseModel):
                    continue
                if not any(candidate in source.current_state for candidate in keys):
                    values[selected_key] = baseline
                else:
                    self.baselines[field_name] = baseline
                break
            else:
                if not field.is_required():
                    if field.default_factory is not None:
                        if self._annotation_has_model(field.annotation):
                            self.baselines[field_name] = _DEFERRED_MODEL_DEFAULT
                    else:
                        baseline = field.get_default(call_default_factory=False)
                        if isinstance(baseline, BaseModel):
                            self.baselines[field_name] = baseline

    def apply(
        self,
        model_type: type[BaseSettings],
        value: Any,
        info: ValidationInfo,
    ) -> Any:
        """Apply this field's mapping to its concrete model baseline, if present.

        Parameters
        ----------
        model_type
            Model supplying the default factory for a deferred baseline.
        value
            Current field input. Non-mapping inputs pass through unchanged.
        info
            Validation metadata identifying the field and previously validated
            values needed by a data-aware default factory.

        Returns
        -------
        Any
            Revalidated baseline model, or the original input if no applicable
            model baseline exists. Factory and nested-validation errors propagate.
        """
        if info.field_name not in self.baselines:
            return value

        baseline = self.baselines[info.field_name]
        if baseline is _DEFERRED_MODEL_DEFAULT:
            baseline = model_type.model_fields[info.field_name].get_default(
                call_default_factory=True,
                validated_data=info.data,
            )
        if isinstance(baseline, BaseModel) and isinstance(value, Mapping):
            return self._update_model(baseline, value)
        return value

    @staticmethod
    def has_discriminator(field: FieldInfo) -> bool:
        """Whether a field selects replacement variants instead of merging them."""
        return field.discriminator is not None or any(
            isinstance(metadata, Discriminator) for metadata in field.metadata
        )

    @classmethod
    def _annotation_has_model(cls, annotation: Any) -> bool:
        """Detect direct model types through Annotated and union wrappers.

        Container element annotations are not inspected: the baseline must be
        a model value itself, not a collection containing models.
        """
        if isinstance(annotation, type):
            return issubclass(annotation, BaseModel)
        origin = get_origin(annotation)
        if origin is Annotated:
            return cls._annotation_has_model(get_args(annotation)[0])
        if origin in (Union, UnionType):
            return any(cls._annotation_has_model(item) for item in get_args(annotation))
        return False

    @classmethod
    def _update_model(
        cls,
        model: BaseModel,
        update: Mapping[str, Any],
    ) -> BaseModel:
        """Revalidate a mapping patch while retaining the baseline's concrete type.

        Parameters
        ----------
        model
            Baseline instance supplying stored fields, extras, and explicit-field
            metadata. Its fields are read without assigning to the baseline.
        update
            Patch using field names or validation aliases. Nested model values
            are patched recursively unless their field has a discriminator.

        Returns
        -------
        BaseModel
            New validated instance of the baseline's concrete class. Its
            explicit fields combine the baseline set with patched model fields.

        Notes
        -----
        Reconstruction uses stored values instead of a serialization dump.
        Per-call strictness, extra policy, and validation context from the outer
        model are not forwarded to this separate validation pass.
        """
        model_type = type(model)
        values = {
            field_name: getattr(model, field_name)
            for field_name in model_type.model_fields
        }
        remaining = dict(update)
        updated_fields: set[str] = set()

        for field_name, field in model_type.model_fields.items():
            aliases, _ = _get_alias_names(
                field_name,
                field,
                populate_by_name=True,
            )
            key = next((alias for alias in aliases if alias in update), None)
            if key is None:
                continue

            value = update[key]
            current = values[field_name]
            if (
                isinstance(current, BaseModel)
                and isinstance(value, Mapping)
                and not cls.has_discriminator(field)
            ):
                value = cls._update_model(current, value)
            values[field_name] = value
            updated_fields.add(field_name)
            for alias in aliases:
                remaining.pop(alias, None)

        values.update(model.model_extra or {})
        values.update(remaining)
        updated = model_type.model_validate(values, by_alias=True, by_name=True)
        object.__setattr__(
            updated,
            "__pydantic_fields_set__",
            model.model_fields_set | updated_fields,
        )
        return updated
