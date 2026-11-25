"""Public model options and registration with Pydantic's config keywords."""

from typing import Literal

from pydantic._internal._config import config_keys
from pydantic_settings import SettingsConfigDict as PydanticSettingsConfigDict


class ConfigModelDict(PydanticSettingsConfigDict, total=False):
    """Configuration options for :class:`BaseConfig`.

    Attributes
    ----------
    case_sensitive
        Whether environment-variable and command-line names are case-sensitive.
    nested_model_default_partial_update
        Whether source values may partially update default nested models.
    env_prefix
        Prefix applied to environment variable names at this class's MRO level.
        ``None`` disables process environment parsing at that level; an empty
        string enables it without a prefix. Parent levels retain their own
        settings. Dotenv and secret-file loading are not disabled by ``None``.
    env_prefix_target
        Names to which ``env_prefix`` applies: ``"variable"``, ``"alias"``,
        or ``"all"``.
    env_file
        Dotenv file or files to load. ``None`` disables dotenv loading unless
        ``env_file_discovery`` is enabled. Later files override earlier files.
    env_file_discovery
        Whether to call :meth:`BaseConfig.find_dotenv` when no dotenv file is
        configured or supplied per instance. An explicit ``_env_file=None``
        also requests discovery when enabled; disable discovery to suppress it.
    env_file_encoding
        Text encoding used to read ``env_file``.
    env_file_depth
        Number of parent directories to search for a relative ``env_file``.
        Requires Pydantic Settings 2.16 or later.
    dotenv_filtering
        Policy for filtering dotenv variables before validation. The default
        ``"only_existing"`` keeps variables matching declared fields;
        ``"match_prefix"`` also includes otherwise unused prefixed variables.
        ``None`` includes unused variables regardless of prefix, subject to
        the model's extra-field policy during validation.
    env_ignore_empty
        Whether empty environment and dotenv values are ignored.
    env_nested_delimiter
        Delimiter used to map environment and dotenv variables to nested values.
    env_nested_max_split
        Maximum number of ``env_nested_delimiter`` splits for one variable.
    env_parse_none_str
        Environment and dotenv string value interpreted as ``None``.
    env_parse_enums
        Whether environment and dotenv enum member names are parsed as values.
    cli_help
        Whether Confidantic's generated CLI parser provides its standard help
        option. Defaults to ``True``; does not change a supplied custom parser.
    cli_prog_name
        Program name displayed in command-line help.
    cli_parse_args
        ``True`` parses process arguments; a list or tuple supplies explicit
        arguments. ``None`` and ``False`` disable automatic parsing. Only the
        most-derived class parses CLI arguments. In notebook-like runtimes,
        ``True`` is ignored while ``sys.argv`` still belongs to the kernel
        launcher; explicit argument sequences and replaced ``sys.argv`` (such
        as IPython ``%run``) are still parsed.
    cli_parse_none_str
        Command-line string value interpreted as ``None``. When
        ``env_parse_none_str`` is set, the settings CLI uses that value instead.
    cli_hide_none_type
        Whether command-line help hides ``None`` in field types.
    cli_avoid_json
        Whether command-line help avoids JSON syntax for complex values.
    cli_enforce_required
        Whether required fields are enforced by the command-line parser.
    cli_use_class_docs_for_groups
        Whether command-line argument groups use class docstrings.
    cli_show_env_vars
        Whether command-line help displays resolved environment variable names.
        Defaults to ``False``. When constructing a Pydantic Settings
        ``CliSettingsSource`` directly, enable this only with an explicit string
        ``env_prefix`` (including ``""`` for unprefixed variables).
    cli_exit_on_error
        Whether command-line parsing exits when it encounters an error.
    cli_prefix
        Prefix for root command-line arguments.
    cli_flag_prefix_char
        Prefix character for command-line option flags.
    cli_implicit_flags
        Whether boolean fields use implicit flags, and their ``"dual"`` or
        ``"toggle"`` mode.
    cli_ignore_unknown_args
        Whether command-line parsing ignores unknown arguments.
    cli_kebab_case
        Whether command-line option names use kebab case, including its
        ``"all"`` and ``"no_enums"`` modes.
    cli_shortcuts
        Mapping from field names to command-line shortcut names.
    secrets_dir
        Directory, or ordered directories, containing secret files.
    json_file, json_file_encoding
        JSON configuration file or files and their text encoding. Add a
        :class:`pydantic_settings.JsonConfigSettingsSource` through
        :meth:`BaseConfig.settings_customise_sources` to use them.
    yaml_file, yaml_file_encoding, yaml_config_section
        YAML configuration file or files, their text encoding, and an optional
        dotted section. Add a :class:`pydantic_settings.YamlConfigSettingsSource`
        through :meth:`BaseConfig.settings_customise_sources` to use them.
    toml_file, toml_table_header
        TOML configuration file or files and an optional table header. Add a
        :class:`pydantic_settings.TomlConfigSettingsSource` through
        :meth:`BaseConfig.settings_customise_sources` to use them.
    pyproject_toml_depth, pyproject_toml_table_header
        Number of parent directories to search for ``pyproject.toml`` and the
        table header to load. Add a
        :class:`pydantic_settings.PyprojectTomlConfigSettingsSource` through
        :meth:`BaseConfig.settings_customise_sources` to use them.
    enable_decoding
        Whether settings sources decode complex values by default. Field-level
        ``pydantic_settings.NoDecode`` and ``pydantic_settings.ForceDecode``
        annotations override this setting.
    use_attribute_docstrings
        Whether field descriptions are read from attribute docstrings. This is
        enabled by default except in Jupyter-like runtimes, where source
        mapping may be unavailable. An explicit per-class setting takes
        precedence. Explicit field descriptions remain available when extraction
        is disabled and take precedence over attribute docstrings when enabled.
    docstring_set_attributes_section
        Whether model fields replace an ``@attrs`` marker in the class
        docstring's ``Attributes`` section when a configuration subclass is
        created. ``None`` enables marker replacement by default.
    docstring_style
        Expected format for marked class docstrings: ``"numpy"`` or
        ``"google"``. ``None`` detects the format from the Attributes section.
        Invalid marked docstrings raise ``ValueError`` during class creation.
    """

    docstring_set_attributes_section: bool | None
    docstring_style: Literal["numpy", "google"] | None
    env_file_discovery: bool
    cli_help: bool


# Pydantic must recognize these keys before BaseConfig subclasses are created.
_CUSTOM_CONFIG_KEYS = frozenset(ConfigModelDict.__annotations__) - frozenset(
    PydanticSettingsConfigDict.__annotations__
)
config_keys.update(_CUSTOM_CONFIG_KEYS)
