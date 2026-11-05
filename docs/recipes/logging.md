# Configure console and file logging

[BaseLogging][confidantic.logging.BaseLogging] builds Python logging configuration
with independent console and file levels. Logging itself needs only core Confidantic.
This example uses a temporary file so it leaves no application log behind:

```python
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from confidantic.logging import BaseLogging


with TemporaryDirectory() as directory:
    log_path = Path(directory) / "application.log"
    config = BaseLogging(
        level="INFO",
        file=log_path,
        file_level="DEBUG",
        format="%(levelname)s: %(message)s",
    )
    logger = config.get_logger("orders")
    logger.debug("Prepared the order.")
    logger.info("Order accepted.")
    print(log_path.read_text(encoding="utf-8"), end="")
    # Close the temporary file handler before its directory is removed.
    logging.shutdown()
```

The console handler writes `INFO: Order accepted.` to stderr. Reading the file
prints both records to stdout:

```text
DEBUG: Prepared the order.
INFO: Order accepted.
```

Set `env_prefix` in a subclass's `ConfigModelDict` when levels should come from
environment variables. Standard level names are case-insensitive; aliases such
as `warn` are normalized to `WARNING`.

## Prepare a dictionary or apply it

`config.config()` returns a standard `dictConfig` dictionary without installing
handlers or opening files. `config.get_logger(...)` applies that dictionary to the
root logging system and returns the requested logger.

!!! warning "Applying logging changes the root handlers"

    Calling `get_logger()` replaces root handlers and normally enables warning
    capture. Configure logging at an application entry point. Prepare the dictionary
    first if you need to combine it with another logging policy.

`root_level` governs loggers inheriting their level from the root. Handler levels
filter the records they receive; a named logger with an explicit level can
propagate past an ancestor's logger level. Choose handler levels for the intended
console and file output.

File paths become absolute when the dictionary is built. Home expansion and parent
directory creation are left to the application. File logging rotates according to
`file_max_bytes` and `file_backup_count`. Invalid dictionary configuration is
reported when Python logging applies it.

See the [API reference][confidantic.logging.BaseLogging] for every option and the
[wiki logging guide](https://github.com/sztal/confidantic/blob/master/wiki/examples/logging.md)
for environment-based examples.
