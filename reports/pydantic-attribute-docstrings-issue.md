# Suggested title: Attribute-docstring inspection raises TypeError while cloudpickle reconstructs a local model in a fresh worker

## Initial Checks

- [x] I confirm that I'm using Pydantic V2

## Description

A model defined inside a function in a normally imported module cannot be
restored by cloudpickle in a fresh interpreter where that module is unavailable
when it inherits `use_attribute_docstrings=True`. The producer succeeds;
the worker raises `TypeError: <class 'model_defs.Config'> is a built-in class`.
The class is not a built-in class.

I expect unavailable source to produce no extracted attribute descriptions,
just as it does when source inspection raises `OSError`, rather than preventing
reconstruction of an otherwise serializable model. Disabling attribute-docstring
extraction before constructing the producer's model makes the same transfer work.
This reproduction uses only Pydantic and cloudpickle.

### Root cause and proposed fix

Cloudpickle reconstructs local classes by value. Creating the skeleton child
class invokes Pydantic's metaclass before cloudpickle restores its full state.
The parent already enables attribute-docstring extraction, so field collection
calls `extract_docstrings_from_cls()`.

On Python 3.13, that function calls `inspect.getsourcelines(cls)`. When the
class's module is unavailable, Python's `inspect.getfile()` raises `TypeError`.
Pydantic catches `OSError` at this location but not `TypeError`.

Proposed change in `pydantic/_internal/_docs_extraction.py`, scoped only to
retrieving source:

```diff
 try:
     source, _ = inspect.getsourcelines(cls)
-except OSError:
+except (OSError, TypeError):
     return {}
```

I verified this change in an isolated process using Pydantic 2.13.5: the worker
then restores the model and its value successfully. Installed dependency files
were not modified. No claim is made that this resolves every dynamic-class
serialization problem.

### Related issue and duplicate search

[Pydantic #12389](https://github.com/pydantic/pydantic/issues/12389) reports the
same inspection exception during manual `importlib` loading. It was closed with
advice to register the module in `sys.modules` or use normal importing.

This reproduction already imports the producer module normally and asserts
that it is registered in `sys.modules`. Its local classes are serialized by
value; the worker intentionally has no access to their defining module. No
`__module__` rewriting or manual `importlib` loading is involved.

A search on 2026-09-25 for
`repo:pydantic/pydantic "use_attribute_docstrings" "cloudpickle"` found no
matching issue. Searching for `"built-in class" "docstrings"` found #12389;
I did not find an exact report for this worker reconstruction case.

## Example Code

Create the following layout in an empty directory:

```text
producer/
    model_defs.py
    produce.py
worker/
    consume.py
```

`producer/model_defs.py`:

```python
from pydantic import BaseModel, ConfigDict


def make_model(*, use_attribute_docstrings: bool = True) -> type[BaseModel]:
    class Parent(BaseModel):
        model_config = ConfigDict(use_attribute_docstrings=use_attribute_docstrings)

    class Config(Parent):
        value: int = 1
        """A documented field."""

    return Config
```

`producer/produce.py`:

```python
import sys
from pathlib import Path

import cloudpickle
import model_defs

assert sys.modules["model_defs"] is model_defs
Config = model_defs.make_model(use_attribute_docstrings="--no-docstrings" not in sys.argv)
Path(__file__).resolve().parents[1].joinpath("worker/payload.pkl").write_bytes(
    cloudpickle.dumps(Config(value=7))
)
print("producer succeeded")
```

`worker/consume.py`:

```python
from importlib.util import find_spec
from pathlib import Path

import cloudpickle

assert find_spec("model_defs") is None
config = cloudpickle.loads(Path(__file__).with_name("payload.pkl").read_bytes())
assert config.value == 7
print("worker succeeded")
```

From the directory containing `producer/` and `worker/`, run with Python 3.13:

```console
python -m venv .venv
.venv/bin/python -m pip install pydantic==2.13.5 cloudpickle==3.1.2
.venv/bin/python producer/produce.py
.venv/bin/python worker/consume.py
```

The producer prints `producer succeeded`. The worker's `find_spec` assertion
passes, then unpickling fails. Ensure the `producer/` directory is not added to
`PYTHONPATH`; script execution adds it only to the producer's import path.

Observed traceback on 2.13.5 (environment paths normalized):

```text
Traceback (most recent call last):
  File "<repro>/worker/consume.py", line 7, in <module>
    config = cloudpickle.loads(Path(__file__).with_name("payload.pkl").read_bytes())
  File "<repro>/latest/lib/python3.13/site-packages/cloudpickle/cloudpickle.py", line 553, in _make_skeleton_class
    skeleton_class = types.new_class(
        name, bases, {"metaclass": type_constructor}, lambda ns: ns.update(type_kwargs)
    )
  File "<python>/lib/python3.13/types.py", line 75, in new_class
    return meta(name, resolved_bases, ns, **kwds)
  File "<repro>/latest/lib/python3.13/site-packages/pydantic/_internal/_model_construction.py", line 243, in __new__
    set_model_fields(cls, config_wrapper=config_wrapper, ns_resolver=ns_resolver)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<repro>/latest/lib/python3.13/site-packages/pydantic/_internal/_model_construction.py", line 579, in set_model_fields
    fields, pydantic_extra_info, class_vars = collect_model_fields(
                                              ~~~~~~~~~~~~~~~~~~~~^
        cls, config_wrapper, ns_resolver, typevars_map=typevars_map
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "<repro>/latest/lib/python3.13/site-packages/pydantic/_internal/_fields.py", line 423, in collect_model_fields
    _update_fields_from_docstrings(cls, fields)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "<repro>/latest/lib/python3.13/site-packages/pydantic/_internal/_fields.py", line 122, in _update_fields_from_docstrings
    fields_docs = extract_docstrings_from_cls(cls, use_inspect=use_inspect)
  File "<repro>/latest/lib/python3.13/site-packages/pydantic/_internal/_docs_extraction.py", line 99, in extract_docstrings_from_cls
    source, _ = inspect.getsourcelines(cls)
                ~~~~~~~~~~~~~~~~~~~~~~^^^^^
  File "<python>/lib/python3.13/inspect.py", line 1245, in getsourcelines
    lines, lnum = findsource(object)
                  ~~~~~~~~~~^^^^^^^^
  File "<python>/lib/python3.13/inspect.py", line 1060, in findsource
    file = getsourcefile(object)
  File "<python>/lib/python3.13/inspect.py", line 963, in getsourcefile
    filename = getfile(object)
  File "<python>/lib/python3.13/inspect.py", line 932, in getfile
    raise TypeError('{!r} is a built-in class'.format(object))
TypeError: <class 'model_defs.Config'> is a built-in class
```

### Passing control and workaround

Regenerate the payload with source inspection disabled on the parent model:

```console
.venv/bin/python producer/produce.py --no-docstrings
.venv/bin/python worker/consume.py
```

Both commands succeed, and the worker prints `worker succeeded`. This disables
a documentation feature rather than addressing the exception handling. It must
be chosen before producing the model; changing an environment variable in the
consumer does not reconfigure an arbitrary serialized Pydantic model.
Making the defining module importable in the worker is another possible
application-level approach when that deployment constraint is acceptable.

## Python, Pydantic & OS Version

The producer and worker use the same environment below. It reproduces the
failure with attribute-docstring extraction enabled and passes the control with
extraction disabled.

Output from
`python -c "import pydantic.version; print(pydantic.version.version_info())"`,
with the cloudpickle version appended:

```text
             pydantic version: 2.13.5
        pydantic-core version: 2.46.5
          pydantic-core build: profile=release pgo=false
               python version: 3.13.9 (main, Oct 14 2025, 21:29:44) [Clang 20.1.4 ]
                     platform: Linux-7.1.1-76070101-generic-x86_64-with-glibc2.35
             related packages: typing_extensions-4.16.0
                       commit: unknown
cloudpickle: 3.1.2
```
