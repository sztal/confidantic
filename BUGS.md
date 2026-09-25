# Known bugs

This file is the backlog for confirmed, unresolved source defects. Include a
concise symptom, reproduction or evidence, affected behavior, and expected
behavior. Remove an entry after its regression test and required checks pass.
Do not track bugs in `wiki/`.

## Attribute-docstring inspection can fail during class reconstruction

A class defined in a module unavailable to a worker can fail cloudpickle
restoration with `TypeError: <class 'unavailable_worker_module.Config'> is a built-in class`. Observed with Python 3.13.9, Pydantic 2.13.4, and cloudpickle
3.1.2. This reduced reproduction also fails without Confidantic:

```python
import cloudpickle
from pydantic import BaseModel, ConfigDict


class Parent(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)


class Config(Parent):
    value: int = 1


Config.__module__ = "unavailable_worker_module"
cloudpickle.loads(cloudpickle.dumps(Config()))
```

Expected: unavailable source should not prevent reconstructing an otherwise
serializable configuration class. The confirmed cause is Pydantic's attribute
source inspection catching
`OSError` but not the `TypeError` raised when a reconstructed class's module is
unavailable. Catching both exceptions at source retrieval fixes the standalone
reproduction in an isolated process. The failure also reproduces on Pydantic
2.13.5 / Pydantic-core 2.46.5.
Confidantic inherits this failure when attribute-docstring extraction is enabled.
Setting `CONFIDANTIC_USE_ATTRIBUTE_DOCSTRINGS=false` before importing the package
in the producer and workers is a workaround, not a fix to Pydantic inspection.

A complete producer/worker reproduction, verified versions, proposed narrow
upstream fix, and related-issue search are in the
[prepared Pydantic issue report](reports/pydantic-attribute-docstrings-issue.md).
The report is for manual review and submission; no upstream issue has been filed.
This defect remains unresolved in the dependency.

## Current-directory secondary paths fail validation

`BasePaths(data=".")` raises a validation error with `not enough values to unpack (expected at least 1, got 0)`. Empty strings and declared path fields
whose default is `Path(".")` hit the same path. `_canonicalize_path` unpacks
`expanded.parts` before joining a relative secondary path to the root, but
`Path(".").parts` is empty.

Expected: a current-directory secondary path resolves to the configured root,
just like any other relative path. Root paths themselves are unaffected.

## Hashable mutable factory defaults are shared

`Factory.model_from` installs source attributes as static field defaults.
The `_requires_default_factory` and `_cloned_default` helpers are never called.
Pydantic copies unhashable defaults, but hashable mutable values can be shared
by the source and all generated configuration instances:

```python
from typing import Any
from confidantic import Factory


class HashableList(list):
    __hash__ = object.__hash__


class Target:
    def __init__(self, items: Any) -> None:
        self.items = items


source = Target(HashableList([1]))
Config = Factory.model_from(source)
first, second = Config(), Config()
first.items.append(2)
assert first.items is second.items is source.items
assert second.items == [1, 2]
```

Expected: mutable collection defaults are isolated per factory configuration,
including hashable mutable collections. Normal list/dict isolation tests pass
because Pydantic already handles those defaults. The audit corrected the
unsupported docstring claim that field default factories perform this copying;
the source isolation defect remains unresolved.
