# Command-line interfaces

A CLI is another settings source for a configuration model. Enable it on the root
model with `cli_parse_args=True`, or supply an explicit argument sequence. Automatic
parsing is disabled by default; in notebook-like runtimes, `cli_parse_args=True` is
ignored while `sys.argv` still belongs to the kernel launcher, whereas explicit
argument sequences and replaced `sys.argv` (such as IPython `%run`) are still parsed.
Pydantic Settings owns parser syntax and subcommands.

## Options and precedence

CLI input normally has priority over initializer input and other sources. Only
the most-derived MRO level parses it. Defaults use kebab-case option names and
explicit boolean values, so a boolean option is written as `--dry-run true` unless
implicit flags are enabled. Unknown options are ignored by default, which supports
staged parsers; choose a stricter policy when appropriate for a standalone command.

Nested model fields expose dotted options. Concrete generated factory annotations
and supported factory instance defaults let the parser discover dependency fields
such as `--application.database.host`. A generic or opaque annotation cannot expose
arbitrary attributes of an object that has not been described as model fields.

## Commands, help, and stages

`CliSubCommand`, `CliPositionalArg`, and `get_subcommand` come from Pydantic Settings.
Use outermost CliSubCommand annotations without field defaults, then dispatch the
selected model. Root parsing is enough; command models need not parse independently.

Confidantic's `cli_help=False` suppresses generated standard help without replacing
a supplied custom parser. Field descriptions and class docstrings feed help text;
environment variable names are hidden by default. Runtime-selected dependency types
require selecting the type before generating its final configuration and parser.

Factory resolution suppresses automatic CLI parsing throughout target construction
to avoid interpreting application arguments again. Other settings sources remain
active, and the previous parser policy is restored when resolution exits.

See [CLI examples](../examples/clis.md),
[dynamic template CLIs](../examples/advanced/dynamic-template-clis.md), and
[parser internals](../api/_config/_cli.md). Return to [concepts](README.md).
