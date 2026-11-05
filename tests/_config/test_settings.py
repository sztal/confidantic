"""Settings-source ordering, defaults, provenance, and validation options."""

from collections.abc import Callable
from inspect import Parameter, signature
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import (
    BaseModel,
    Field,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
)

from confidantic import BaseConfig, ClassDefaultsSource, ConfigModelDict, Factory
from tests._config.factory_targets import SimpleTarget


def test_base_config_accepts_base_settings_sunder_arguments() -> None:
    """BaseConfig forwards every per-instance Pydantic Settings override."""
    base_settings_options = tuple(
        name
        for name in signature(BaseSettings._settings_init_sources).parameters
        if name != "_init_kwargs"
    )
    BaseConfig(**dict.fromkeys(base_settings_options))


def test_base_config_accepts_positional_source_options() -> None:
    """Positional arguments follow the installed upstream source signature."""

    class Config(BaseConfig):
        value: str = "default"

    sources, _ = Config._settings_init_sources(True)
    dotenv = next(
        source for source in sources if isinstance(source, DotEnvSettingsSource)
    )
    assert dotenv.case_sensitive is True


def test_base_config_forwards_future_settings_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """New upstream options reach each settings source without a local signature edit."""
    original = BaseSettings.__dict__["_settings_init_sources"].__func__
    original_signature = signature(original)
    received: list[tuple[type[BaseSettings], int | None]] = []

    def upstream(settings_cls: type[BaseSettings], **kwargs: Any) -> Any:
        received.append((settings_cls, kwargs.pop("_future_option", None)))
        return original(settings_cls, **kwargs)

    cast(Any, upstream).__signature__ = original_signature.replace(
        parameters=(
            *original_signature.parameters.values(),
            Parameter("_future_option", Parameter.KEYWORD_ONLY, default=None),
        )
    )
    monkeypatch.setattr(BaseSettings, "_settings_init_sources", classmethod(upstream))

    class Parent(BaseConfig):
        value: str = "default"

    class Child(Parent):
        pass

    assert Child(_future_option=17).value == "default"
    assert received == [(Child, 17), (Parent, 17)]
    with pytest.raises(ValidationError, match="_unknown_option"):
        Child(_unknown_option=17)


def test_base_config_accepts_subclass_source_options() -> None:
    """Explicit options on a subclass source-builder override are retained."""
    received: list[int | None] = []

    class Config(BaseConfig):
        @classmethod
        def _settings_init_sources(
            cls, _custom_option: int | None = None, **kwargs: Any
        ) -> Any:
            received.append(_custom_option)
            return super()._settings_init_sources(**kwargs)

    Config(_custom_option=7)
    assert received == [7]


def test_class_defaults_source_is_public() -> None:
    """The public source loads only defaults declared at its class level."""

    class ParentConfig(BaseConfig):
        inherited: str = "inherited"

    class Config(ParentConfig):
        local: int = Field(1, alias="LOCAL")
        required: str

    assert ClassDefaultsSource(Config)() == {"LOCAL": 1}
    assert ClassDefaultsSource(Config, {"inherited"})() == {"inherited": "inherited"}
    assert ClassDefaultsSource(Config, set())() == {}
    assert ClassDefaultsSource(Config, {"unknown"})() == {}


def test_class_defaults_source_supports_arbitrary_types() -> None:
    """Static defaults respect a model's arbitrary-types configuration."""

    class Dependency:
        pass

    dependency = Dependency()

    class Config(BaseConfig, arbitrary_types_allowed=True):
        value: Dependency = dependency

    assert isinstance(ClassDefaultsSource(Config)()["value"], Dependency)
    assert isinstance(Config().value, Dependency)


def test_model_field_sources_track_defaults_and_init() -> None:
    """Field sources identify both resolution and inheritance coordinates."""

    class Config(BaseConfig):
        value: str = "from-default"

    assert Config().model_field_sources == {"value": (ClassDefaultsSource, Config)}
    assert Config(value="from-init").model_field_sources == {
        "value": (InitSettingsSource, Config)
    }


def test_model_field_sources_track_standard_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Built-in sources expose their exact source and configuration classes."""
    env_file = tmp_path / ".env"
    env_file.write_text("APP_VALUE=from-dotenv\n", encoding="utf-8")
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "APP_value").write_text("from-secret", encoding="utf-8")

    class Config(BaseConfig):
        model_config = ConfigModelDict(env_prefix="APP_")

        value: str = "from-default"

    cli = Config(
        _cli_parse_args=["--value=from-cli"],
        _env_file=env_file,
        _secrets_dir=secrets_dir,
    )
    assert cli.model_field_sources["value"] == (CliSettingsSource, Config)

    monkeypatch.setenv("APP_VALUE", "from-environment")
    environment = Config(
        _env_file=env_file,
        _secrets_dir=secrets_dir,
    )
    assert environment.model_field_sources["value"] == (
        EnvSettingsSource,
        Config,
    )

    monkeypatch.delenv("APP_VALUE")
    dotenv = Config(_env_file=env_file, _secrets_dir=secrets_dir)
    assert dotenv.model_field_sources["value"] == (DotEnvSettingsSource, Config)

    secret = Config(_env_file=None, _secrets_dir=secrets_dir)
    assert secret.model_field_sources["value"] == (SecretsSettingsSource, Config)


def test_model_field_sources_track_mro_and_nested_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Coordinates retain MRO owners and top-level nested priority."""
    monkeypatch.setenv("CHILD_OPTIONS", '{"child": "environment"}')
    monkeypatch.setenv("PARENT_INHERITED", "environment")

    class ParentConfig(BaseConfig):
        model_config = ConfigModelDict(env_prefix="PARENT_")

        inherited: str = "parent-default"
        parent_default: str = "parent-default"
        options: dict[str, str] = Field(default={"parent": "default"})

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(env_prefix="CHILD_")

        factory: list[str] = Field(default_factory=list)

    config = ChildConfig()

    assert config.options == {"child": "environment", "parent": "default"}
    assert config.model_field_sources == {
        "inherited": (EnvSettingsSource, ParentConfig),
        "parent_default": (ClassDefaultsSource, ParentConfig),
        "options": (EnvSettingsSource, ChildConfig),
        "factory": (ClassDefaultsSource, ChildConfig),
    }


def test_model_field_sources_use_names_and_retain_input_provenance() -> None:
    """Aliases and validators do not replace settings-source provenance."""

    class Config(BaseConfig):
        value: int = Field(1, alias="VALUE")

        @field_validator("value")
        @classmethod
        def double_value(cls, value: int) -> int:
            return value * 2

    default = Config()
    explicit = Config(VALUE="4")

    assert default.model_field_sources == {"value": (ClassDefaultsSource, Config)}
    assert explicit.value == 8
    assert explicit.model_field_sources == {"value": (InitSettingsSource, Config)}
    assert explicit.model_dump() == {"value": 8}
    assert explicit.model_fields_set == {"value"}
    with pytest.raises(TypeError):
        explicit.model_field_sources["value"] = (
            ClassDefaultsSource,
            Config,
        )


def test_model_field_sources_preserve_custom_source_identity() -> None:
    """Custom settings sources run once and retain their exact class."""
    calls = 0

    class CustomSource(InitSettingsSource):
        def __call__(self) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return super().__call__()

    class Config(BaseConfig):
        value: str

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (CustomSource(settings_cls, {"value": "from-custom"}),)

    config = Config()

    assert config.model_field_sources == {"value": (CustomSource, Config)}
    assert calls == 1


def test_model_field_sources_omit_bare_callable_sources() -> None:
    """Sources without a settings-class axis remain usable but untracked."""

    def custom_source() -> dict[str, str]:
        return {"value": "from-custom"}

    class Config(BaseConfig):
        value: str

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (custom_source,)  # type: ignore[return-value]

    config = Config()

    assert config.value == "from-custom"
    assert config.model_field_sources == {}


def test_child_default_precedes_parent_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child default resolves before sources configured on its parent."""
    monkeypatch.setenv("PARENT_VALUE", "from-parent-environment")
    monkeypatch.setenv("PARENT_INHERITED", "from-parent-environment")

    class ParentConfig(BaseConfig):
        model_config = ConfigModelDict(env_prefix="PARENT_")

        value: str = "from-parent-default"
        inherited: str = "from-parent-default"

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(env_prefix="CHILD_")

        value: str = "from-child-default"

    config = ChildConfig()

    assert config.value == "from-child-default"
    assert config.inherited == "from-parent-environment"


def test_standard_source_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Built-in sources retain Pydantic Settings priority."""
    env_file = tmp_path / ".env"
    env_file.write_text("APP_VALUE=from-dotenv\n", encoding="utf-8")
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "APP_value").write_text("from-secret", encoding="utf-8")
    monkeypatch.setenv("APP_VALUE", "from-environment")

    class Config(BaseConfig):
        model_config = ConfigModelDict(env_prefix="APP_")

        value: str = "from-default"

    assert (
        Config(
            value="from-init",
            _cli_parse_args=["--value=from-cli"],
            _env_file=env_file,
            _secrets_dir=secrets_dir,
        ).value
        == "from-cli"
    )
    assert (
        Config(
            value="from-init",
            _env_file=env_file,
            _secrets_dir=secrets_dir,
        ).value
        == "from-init"
    )
    assert (
        Config(_env_file=env_file, _secrets_dir=secrets_dir).value == "from-environment"
    )

    monkeypatch.delenv("APP_VALUE")
    assert Config(_env_file=env_file, _secrets_dir=secrets_dir).value == "from-dotenv"
    assert Config(_env_file=None, _secrets_dir=secrets_dir).value == "from-secret"
    assert Config(_env_file=None, _secrets_dir=None).value == "from-default"


def test_default_env_prefix_ignores_process_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A None prefix ignores process variables but still loads dotenv values."""
    env_file = tmp_path / ".env"
    env_file.write_text("VALUE=from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("VALUE", "from-environment")

    class Config(BaseConfig):
        value: str = "from-default"

    config = Config(_env_file=env_file)

    assert config.value == "from-dotenv"
    assert config.model_field_sources["value"] == (DotEnvSettingsSource, Config)


def test_empty_env_prefix_enables_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicitly empty prefix enables unprefixed process variables."""
    monkeypatch.setenv("VALUE", "from-environment")

    class Config(BaseConfig):
        model_config = ConfigModelDict(env_prefix="")

        value: str = "from-default"

    config = Config()

    assert config.value == "from-environment"
    assert config.model_field_sources["value"] == (EnvSettingsSource, Config)


def test_dotenv_filters_keys_by_each_mro_prefix(tmp_path: Path) -> None:
    """Dotenv sources load their level's prefix and ignore unrelated keys."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CHILD_VALUE=from-child\nPARENT_INHERITED=from-parent\nUNRELATED=ignored\n",
        encoding="utf-8",
    )

    class ParentConfig(BaseConfig):
        model_config = ConfigModelDict(env_prefix="PARENT_")

        inherited: str

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(env_prefix="CHILD_")

        value: str

    config = ChildConfig(_env_file=env_file)

    assert config.model_dump() == {
        "inherited": "from-parent",
        "value": "from-child",
    }


def test_dotenv_ignores_undeclared_unprefixed_keys(tmp_path: Path) -> None:
    """Unprefixed dotenv files provide declared fields without extra errors."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "VALUE=from-dotenv\nUNRELATED=ignored\n",
        encoding="utf-8",
    )

    class Config(BaseConfig):
        value: str

    assert Config(_env_file=env_file).value == "from-dotenv"


def test_dotenv_discovery_is_opt_in() -> None:
    """An absent dotenv file does not invoke discovery by default."""

    class Config(BaseConfig):
        value: str = "from-default"

        @classmethod
        def find_dotenv(cls) -> str:
            raise AssertionError("dotenv discovery should be disabled")

    assert Config(_env_file=None).value == "from-default"


@pytest.mark.skipif(
    "_env_file_depth" not in signature(BaseSettings._settings_init_sources).parameters,
    reason="requires Pydantic Settings with dotenv depth support",
)
def test_dotenv_depth_override_searches_parents_across_mro(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per-instance dotenv depth reaches each configuration class's sources."""
    (tmp_path / ".env").write_text(
        "PARENT_VALUE=parent\nCHILD_CHILD_VALUE=child\n", encoding="utf-8"
    )
    nested = tmp_path / "one" / "two"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv("PARENT_VALUE", raising=False)
    monkeypatch.delenv("CHILD_CHILD_VALUE", raising=False)

    class Parent(BaseConfig):
        model_config = cast(
            ConfigModelDict,
            {"env_file": ".env", "env_prefix": "PARENT_", "env_file_depth": 2},
        )
        value: str = "default"

    class Child(Parent):
        model_config = ConfigModelDict(env_prefix="CHILD_")
        child_value: str = "default"

    assert Child(_env_file_depth=1).model_dump() == {
        "value": "default",
        "child_value": "default",
    }
    assert Child().model_dump() == {
        "value": "parent",
        "child_value": "child",
    }
    assert Child(_env_file_depth=2).model_dump() == {
        "value": "parent",
        "child_value": "child",
    }


@pytest.mark.parametrize("options", ({}, {"_env_file": None}))
def test_dotenv_discovery_uses_concrete_class_once_across_mro(
    tmp_path: Path,
    options: dict[str, object],
) -> None:
    """A concrete config discovers one dotenv file for every MRO level."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CHILD_VALUE=from-child\nPARENT_INHERITED=from-parent\n",
        encoding="utf-8",
    )
    calls = 0

    class ParentConfig(BaseConfig):
        model_config = ConfigModelDict(env_prefix="PARENT_")

        inherited: str

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(
            env_file_discovery=True,
            env_prefix="CHILD_",
        )

        value: str

        @classmethod
        def find_dotenv(cls) -> str:
            nonlocal calls
            calls += 1
            return str(env_file)

    config = ChildConfig(**options)

    assert config.model_dump() == {
        "inherited": "from-parent",
        "value": "from-child",
    }
    assert calls == 1


def test_explicit_dotenv_file_bypasses_discovery(tmp_path: Path) -> None:
    """An explicit dotenv file remains authoritative over discovery."""
    env_file = tmp_path / ".env"
    env_file.write_text("VALUE=from-explicit\n", encoding="utf-8")

    class Config(BaseConfig):
        model_config = ConfigModelDict(env_file_discovery=True)

        value: str

        @classmethod
        def find_dotenv(cls) -> str:
            raise AssertionError("explicit dotenv files bypass discovery")

    config = Config(_env_file=env_file)

    assert config.value == "from-explicit"
    assert config.model_field_sources == {"value": (DotEnvSettingsSource, Config)}


def test_nested_values_merge_across_mro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lower MRO levels fill missing nested keys without replacing child keys."""
    monkeypatch.setenv(
        "CHILD_OPTIONS",
        '{"shared": "child-env", "child_env": "child-env"}',
    )
    monkeypatch.setenv(
        "PARENT_OPTIONS",
        '{"shared": "parent-env", "parent_env": "parent-env"}',
    )

    class ParentConfig(BaseConfig):
        model_config = ConfigModelDict(env_prefix="PARENT_")

        options: dict[str, str] = Field(
            default={
                "shared": "parent-default",
                "parent_default": "parent-default",
            }
        )

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(env_prefix="CHILD_")

        options: dict[str, str] = Field(
            default={
                "shared": "child-default",
                "child_default": "child-default",
            }
        )

    assert ChildConfig().options == {
        "shared": "child-env",
        "child_env": "child-env",
        "child_default": "child-default",
        "parent_env": "parent-env",
        "parent_default": "parent-default",
    }


def test_nested_model_defaults_merge_across_mro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nested model defaults contribute missing values across MRO levels."""
    monkeypatch.setenv("CHILD_OPTIONS", '{"child": 2}')

    class Options(BaseModel):
        child: int = 0
        parent: int = 0

    class ParentConfig(BaseConfig):
        options: Options = Field(default=Options(parent=1))

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(env_prefix="CHILD_")

    assert ChildConfig().options == Options(child=2, parent=1)


def test_default_factory_blocks_parent_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child factory stays lazy and blocks the corresponding parent field."""
    monkeypatch.setenv("PARENT_VALUES", '["from-parent-environment"]')
    calls = 0

    def make_values() -> list[str]:
        nonlocal calls
        calls += 1
        return ["from-child-factory"]

    class ParentConfig(BaseConfig):
        model_config = ConfigModelDict(env_prefix="PARENT_")

        values: list[str] = Field(default=["from-parent-default"])

    class ChildConfig(ParentConfig):
        model_config = ConfigModelDict(env_prefix="CHILD_")

        values: list[str] = Field(default_factory=make_values)

    first = ChildConfig()
    second = ChildConfig()

    assert first.values == ["from-child-factory"]
    assert second.values == ["from-child-factory"]
    assert first.values is not second.values
    assert calls == 2


def test_validated_data_default_factory_keeps_pydantic_semantics() -> None:
    """Factories that consume validated data are evaluated by Pydantic."""

    class Config(BaseConfig):
        seed: int = 3
        values: list[int] = Field(default_factory=lambda data: [data["seed"]])

    assert Config().values == [3]


def test_aliases_validators_and_fields_set_are_preserved() -> None:
    """MRO resolution still delegates aliases and validation to Pydantic."""

    class Config(BaseConfig):
        value: int = Field(1, alias="VALUE")

        @field_validator("value")
        @classmethod
        def double_value(cls, value: int) -> int:
            return value * 2

    default = Config()
    explicit = Config(VALUE="4")

    assert default.value == 2
    assert default.model_fields_set == set()
    assert explicit.value == 8
    assert explicit.model_fields_set == {"value"}


def test_values_equal_to_defaults_are_in_fields_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit sources retain provenance when their values equal defaults."""

    class Config(BaseConfig):
        model_config = ConfigModelDict(env_prefix="APP_")

        value: str = "same"

    default = Config()
    explicit = Config(value="same")
    monkeypatch.setenv("APP_VALUE", "same")
    environment = Config()

    assert default.model_fields_set == set()
    assert explicit.model_fields_set == {"value"}
    assert environment.model_fields_set == {"value"}
    assert default.model_field_sources["value"] == (ClassDefaultsSource, Config)
    assert explicit.model_field_sources["value"] == (InitSettingsSource, Config)
    assert environment.model_field_sources["value"] == (EnvSettingsSource, Config)


@pytest.mark.parametrize(
    ("custom_first", "expected"),
    [(True, "from-custom"), (False, "from-init")],
)
def test_subclass_controls_custom_source_priority(
    custom_first: bool,
    expected: str,
) -> None:
    """Structured-style custom sources keep their subclass-selected position."""

    class Config(BaseConfig):
        value: str

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            custom = InitSettingsSource(
                settings_cls,
                {"value": "from-custom"},
            )
            standard = (
                init_settings,
                env_settings,
                dotenv_settings,
                file_secret_settings,
            )
            return (custom, *standard) if custom_first else (init_settings, custom)

    assert Config(value="from-init").value == expected


def test_c3_mro_controls_duplicate_defaults() -> None:
    """The first declaration in the concrete C3 MRO has priority."""

    class RootConfig(BaseConfig):
        root: str = "root"

    class LeftConfig(RootConfig):
        value: str = "left"

    class RightConfig(RootConfig):
        value: str = "right"
        right: str = "right"

    class Config(LeftConfig, RightConfig):
        pass

    config = Config()

    assert config.value == "left"
    assert config.root == "root"
    assert config.right == "right"
    assert config.model_field_sources == {
        "root": (ClassDefaultsSource, RootConfig),
        "value": (ClassDefaultsSource, LeftConfig),
        "right": (ClassDefaultsSource, RightConfig),
    }


class ContextConfig(BaseConfig):
    """Settings with a context-sensitive validator."""

    count: int = 1

    @field_validator("count")
    @classmethod
    def offset(cls, value: int, info: ValidationInfo) -> int:
        return value + (info.context or {}).get("offset", 0)


@pytest.mark.parametrize(
    ("loader", "data"),
    [
        ("model_validate", {"count": "2"}),
        ("model_validate_json", '{"count":"2"}'),
        ("model_validate_yaml", 'count: "2"'),
        ("model_validate_toml", 'count = "2"'),
    ],
)
def test_settings_per_call_strictness(loader: str, data: Any) -> None:
    with pytest.raises(ValidationError):
        getattr(ContextConfig, loader)(data, strict=True)


@pytest.mark.parametrize(
    "entry", ["python", "json", "yaml", "toml", "adapter", "nested"]
)
def test_settings_context_and_extra_override(entry: str) -> None:
    options = {"context": {"offset": 10}, "extra": "ignore"}
    if entry == "adapter":
        result = TypeAdapter(ContextConfig).validate_python(
            {"count": 2, "unknown": 3}, **options
        )
    elif entry == "nested":

        class Outer(BaseModel):
            child: ContextConfig

        result = Outer.model_validate(
            {"child": {"count": 2, "unknown": 3}}, **options
        ).child
    else:
        loader, data = {
            "python": ("model_validate", {"count": 2, "unknown": 3}),
            "json": ("model_validate_json", '{"count":2,"unknown":3}'),
            "yaml": ("model_validate_yaml", "count: 2\nunknown: 3"),
            "toml": ("model_validate_toml", "count = 2\nunknown = 3"),
        }[entry]
        result = getattr(ContextConfig, loader)(data, **options)
    assert result.count == 12
    assert result.model_extra is None


def test_settings_user_validators_see_merged_values_once() -> None:
    calls: list[tuple[str, Any]] = []

    class Config(BaseConfig, cli_parse_args=["--count", "7"]):
        count: int = 1

        @model_validator(mode="before")
        @classmethod
        def before(cls, value: Any) -> Any:
            calls.append(("before", value["count"]))
            return value

        @model_validator(mode="wrap")
        @classmethod
        def wrap(cls, value: Any, handler: Callable[[Any], Any]) -> Any:
            calls.append(("wrap", value["count"]))
            return handler(value)

    result = Config.model_validate({"count": 2})
    assert result.count == 7
    assert calls == [("wrap", "7"), ("before", "7")]


def test_settings_factory_options_and_instance_revalidation() -> None:
    model = Factory.model_from(SimpleTarget)
    with pytest.raises(ValidationError):
        model.model_validate({"value": "2"}, strict=True)
    assert model.model_validate({"value": 2, "unknown": 3}, extra="ignore").value == 2
    original = ContextConfig(count=2)
    assert ContextConfig.model_validate(original) is original

    class Revalidated(ContextConfig, revalidate_instances="always"):
        pass

    invalid = Revalidated.model_construct(count="wrong")
    with pytest.raises(ValidationError):
        Revalidated.model_validate(invalid)


def test_settings_custom_constructor_and_context_cleanup() -> None:
    from confidantic._config._nested import _NestedModelUpdates

    calls: list[int] = []

    class Custom(BaseConfig):
        value: int = 1

        def __init__(self, value: int = 1, **kwargs: Any) -> None:
            calls.append(value)
            super().__init__(value=value + 1, **kwargs)

    assert Custom(value=2).value == 3
    assert Custom.model_validate({"value": 4}).value == 5
    assert calls == [2, 4]
    with pytest.raises(ValidationError):
        ContextConfig.model_validate({"count": "invalid"}, context={"offset": 10})
    assert _NestedModelUpdates.current() is None
    assert ContextConfig(count=2).count == 2


def test_settings_nested_recursive_schema_keeps_options() -> None:
    class Node(BaseConfig):
        child: "Node | None" = None
        value: int = 1

    with pytest.raises(ValidationError):
        Node.model_validate({"child": {"value": "2"}}, strict=True)
    assert (
        Node.model_validate(
            {"child": {"value": 2, "unknown": 3}}, extra="ignore"
        ).child.value
        == 2
    )
