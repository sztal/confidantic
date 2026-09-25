# Known bugs

This file is the backlog for confirmed, unresolved source defects. Include a
concise symptom, reproduction or evidence, affected behavior, and expected
behavior. Remove an entry after its regression test and required checks pass.
Do not track bugs in `wiki/`.

## Generated factories can fail during cloudpickle restoration

After fixing internal ContextVar serialization, a generated factory class or
instance can still raise `KeyError: 'type'` during unpickling. Observed with
Python 3.13.9, Pydantic 2.13.4, and cloudpickle 3.1.2. Run as a script:

```python
import cloudpickle
from confidantic import Factory


class Target:
    def __init__(self, value: int = 3):
        self.value = value


Config = Factory.model_from(Target)
cloudpickle.loads(cloudpickle.dumps(Config()))
```

Expected: restore the generated configuration and retain `model_resolve()`
behavior. Serializing its schema, validator, or serializer also exposed the
failure during investigation. The root cause and ownership are unresolved;
do not assume the ContextVar fix resolves generated factories.

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
serializable configuration class. The observed path is Pydantic's attribute
source inspection; a complete upstream fix has not been investigated.
Confidantic inherits this failure when attribute-docstring extraction is enabled.
Setting `CONFIDANTIC_USE_ATTRIBUTE_DOCSTRINGS=false` before importing the package
in the producer and workers is a workaround, not a fix to Pydantic inspection.
