# Configure console and file logging

[logging_config.py](../../examples/logging_config.py) needs `confidantic[docstrings]`
because its class requests an `@attrs` section. The logging operations themselves
use the core package and Python logging.

```console
uv run python examples/logging_config.py
```

The script writes `application.log` in the current working directory. Its smoke test
runs in a temporary directory. File-handler parent directories must already exist.

## Choose independent handler levels

The AppLogging subclass selects a file and DEBUG file verbosity. This excerpt follows
that definition:

```python
logger = AppLogging(level="INFO").get_logger(__name__)
logger.debug("Written to the file but not the console.")
logger.info("Written to the console and file.")
```

Expect the INFO record on the console and both records in the file. Timestamps vary.
Later assertions show that a lowercase `EXAMPLE_LOG_LEVEL=warning` environment value
becomes `"WARNING"`, and the configured file remains selected.

## Prepare data or apply it

`config()` only returns a standard dictConfig dictionary. `get_logger()` applies it
to the root logging system and returns the requested logger. Calling it replaces
root handlers and normally enables warning capture. Prefer preparing the dictionary
first when your application needs to combine logging policies before installation.

Root logger level and handler levels have different jobs. A named logger with an
explicit level can propagate records past an ancestor's level, while handler levels
still filter them. File paths are made absolute when the configuration dictionary
is built; home expansion and directory creation are left to the application.

Read [configuration models](../concepts/configuration-models.md),
[logging implementation](../api/logging.md), and
[optional integration boundaries](../architecture/optional-integrations.md).
Return to [all guides](README.md).
