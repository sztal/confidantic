# confidantic.\_config.\_cli

`_CliSettings` resolves one MRO level's parser and environment options. Private
CliSettingsSource subclasses expose concrete factory defaults and control generated
help. Parsing syntax and most CLI behavior remain owned by Pydantic Settings.

## Parser selection

The initializer examines installed source signatures and combines supported options
with model configuration. Non-None per-call values take precedence. It retains the
original environment prefix separately from the parser-facing empty-string fallback;
that distinction allows None to disable process environment parsing. A configured
environment null token also becomes the CLI null token.

`source()` returns a supplied source unchanged. Disabled parsing also defers to
upstream behavior. A custom generated source is needed only for factory-default
fields or disabled default help; ordinary parsers are constructed upstream.

`_FactoryCliSettingsSource.supports()` detects direct Factory annotations with
concrete factory instance defaults. It does not inspect union branches or evaluate
default factories. `_sort_arg_fields()` copies parser-facing FieldInfo and substitutes
the default's concrete factory type, exposing its nested options without mutating
the original model schema. `_import_annotation()` represents type choices with a
target-constrained Import annotation. Help-disabled subclasses override only the
standard-help installation hook.

## Suppression lifetime

The separate `_CLI_SUPPRESSED` ContextVar spans complete public factory-resolution
calls, including target constructors. A token restores the surrounding policy even
on failure. The settings validation wrapper consults it to disable automatic parsing;
other settings sources remain available. This state is not stored on model classes.

Preserve caller-supplied parsers, copied field metadata, and signature-based option
forwarding when editing this module. Parser errors keep upstream exit/exception
policy. Changes to suppression need nested-construction and restoration checks.

Evidence: [source](../../../src/confidantic/_config/_cli.py) and
[CLI tests](../../../tests/_config/test_cli.py).
Read [CLI concepts](../../concepts/clis.md),
[dynamic template CLIs](../../examples/advanced/dynamic-template-clis.md), and
[the configuration index](README.md).
