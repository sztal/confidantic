# Describe and inspect settings

Field descriptions help people understand command-line help and configuration
reports. Start with an explicit description when you want the intent beside the
field definition:

```python
from pydantic import Field

from confidantic import BaseConfig


class AppConfig(BaseConfig):
    retries: int = Field(3, description="Number of retry attempts.")


print(AppConfig.model_fields["retries"].description)
```

```text
Number of retry attempts.
```

## Field documentation

Confidantic reads attribute docstrings into field descriptions by default.
This extraction uses Pydantic and does not require the `docstrings` extra.
Extraction is disabled automatically in Jupyter-like runtimes, including VS Code
Interactive, where source inspection can fail.

An explicit `model_config = ConfigModelDict(use_attribute_docstrings=...)` on a
configuration class takes precedence over the package default.

Disabling extraction does not remove explicit `Field(description=...)`
descriptions or disable the `@attrs` replacement below.

Install `confidantic[docstrings]` and add an `@attrs` marker to a `BaseConfig`
subclass's NumPy or Google `Attributes`
section to replace the entire section with effective model field names and descriptions.
The format is detected automatically, and text outside the section is preserved:

```python
from confidantic import BaseConfig
from pydantic import Field


class AppConfig(BaseConfig):
	"""Application configuration.

	Attributes
	----------
	@attrs
	"""

	retries: int = Field(3, description="Number of retry attempts.")
```

Google sections accept either `@attrs` or `@attrs:`:

```python
from confidantic import BaseConfig, ConfigModelDict
from pydantic import Field


class AppConfig(BaseConfig):
    """Application configuration.

    Attributes:
        @attrs
    """

    model_config = ConfigModelDict(docstring_style="google")
    retries: int = Field(3, description="Number of retry attempts.")
```

`docstring_style` accepts `"numpy"`, `"google"`, or `None` (the default, for
automatic detection). The setting is inherited; set it to `None` on a subclass
to restore detection. An explicit style specifies the expected input format
and does not convert docstrings.

??? info "Docstring generation errors and optional imports"

    Generation validates the completed docstring using the selected parser and
    requires exactly one Attributes section with the generated fields. Invalid
    marked sections, conflicting styles, duplicate sections, and invalid generated
    output raise `ValueError` during class creation. An empty marked Google section
    also raises because the parser requires an attribute entry; an empty NumPy
    section is accepted. Unmarked docstrings and marker mentions in prose, examples,
    or nested literal content are unchanged.

    Without `docstring-parser`, a valid active generation request raises `ImportError`
    during class creation, naming `confidantic[docstrings]`. Structural marker errors
    still raise `ValueError` before importing the parser. Unmarked docstrings,
    ignored markers, and explicitly disabled generation do not import the parser.

Set `docstring_set_attributes_section=False` to retain an `@attrs` marker
without replacing it:

```python
from confidantic import BaseConfig, ConfigModelDict


class AppConfig(BaseConfig):
	"""Application configuration.

	Attributes
	----------
	@attrs
	"""

	model_config = ConfigModelDict(
		docstring_set_attributes_section=False,
	)
```

Explicit `Field(description=...)` descriptions take precedence over extracted
attribute docstrings. If you use attribute docstrings, define the class in a
normal Python source file where source inspection is available.

## Configuration display

Install `confidantic[rich]` to use `Config.model_info()` or `config.info()`.
All three output modes require Rich: `"table"` returns a Rich table, `"string"`
returns its rendering, and `"print"` prints it. The methods raise `ImportError`
with the installation command when Rich is unavailable.

??? info "Inspecting display method annotations"

    Return annotations retain the Rich table type for static type checking without
    importing Rich during model creation. Runtime `typing.get_type_hints()` on these
    methods requires an explicit namespace supplying `Table`; ordinary
    `inspect.signature()` remains available without Rich.

With the `rich` extra installed, this complete example prints the current values:

```python
from confidantic import BaseConfig


class AppConfig(BaseConfig):
    name: str = "orders"
    retries: int = 3


config = AppConfig(retries=5)
config.info()
```

The table shows `name` as `orders` and `retries` as `5`; its layout adapts to the
terminal. `model_info()` describes declared fields rather than one instance's
stored values. The table output uses [rich.table.Table][].

Both methods omit top-level fields declared with `Field(repr=False)` by default.
Pass `respect_field_repr=False` to include those fields. This option only controls
table rows; nested values retain their own representations, and `Field(exclude=True)`
controls serialization rather than display. Repr filtering is not a general
secrecy guarantee.

For plain Python data, `model_dump()` needs no display extra. To find an input's
origin, use [source provenance](sources.md#explain-a-values-origin).
