---
name: tidy-code
description: Organize definitions and function or method bodies in code files, modules, or packages to make their structure legible and predictable. Use when tidying code, organizing class members, grouping related functions and classes, consolidating module globals, or arranging longer function bodies into logical blocks with informative comments. Preserve behavior and public APIs.
---

# Tidy Code

Organize definitions and function or method bodies within the requested files
so readers can predict where to find declarations, constructors, public
operations, implementation details, and each stage of a computation. Apply the
rules below to Python code, using equivalent constructs where applicable in
other languages.

## Scope

- Accept a file, module, or package as the target, together with optional
  contextual requests about related concepts or preferred reading order.
- For a package, apply the ordering within its files; do not move definitions
  between modules, split files, or change exports unless requested.
- Use the target established by the conversation. If none is identifiable,
  ask for the target rather than reorganizing the entire repository.
- Keep this a structural edit. Preserve names, signatures, decorators,
  docstrings, and implementation behavior. Move attached comments and
  docstrings with their definitions or statements, updating section comments
  only as needed to describe the reorganized blocks.

## Class bodies

Keep the class docstring first, then use this order:

1. **Class attributes and variables:** constants, annotated fields,
   configuration declarations, and other class-level data.
1. **Dunder methods:** `__init__` first, followed by the remaining special
   methods, such as `__new__`, `__repr__`, and protocol implementations.
1. **Properties:** regular and cached properties, with each getter, setter,
   and deleter kept together in their required order. Include private
   properties here; classify them by their property role.
1. **Constructors:** alternative constructors such as `from_*` classmethods
   and other methods whose purpose is to create instances. Classify by
   behavior, not just by name or the presence of `@classmethod`.
1. **Public methods:** remaining public instance, class, and static methods.
1. **Private methods:** remaining implementation helpers at the very end,
   including private classmethods and staticmethods. Dunders belong in the
   dunder section, not here.

Within each category, keep related operations together and choose a natural
reading order, such as lifecycle or workflow order. Do not alphabetize
mechanically. Keep existing relative order when it is already coherent.

## Function and method bodies

- Review function and method bodies as well as definition order, especially
  longer bodies. Arrange related statements into cohesive logical blocks.
- Where dependencies and existing behavior permit, put input validation,
  invariant checks, and guard clauses first, followed by input preparation,
  step-by-step computations, and final state updates or result assembly.
  Keep checks that depend on intermediate results beside those results.
- Keep each computation stage together and order stages by their data flow.
  Avoid interleaving unrelated preparation, calculation, and output handling.
- Separate substantial logical blocks with blank lines and short, informative
  comments describing their purpose, relevant invariant, or non-obvious
  reasoning. Prefer domain-specific descriptions over generic labels such as
  "Step 1" or comments that merely repeat the next statement.
- Do not add a comment for every statement or force headings into short,
  self-explanatory bodies. Preserve useful existing comments and keep them
  attached to the logic they explain.
- Reorder only when safe: preserve evaluation and exception order, short-circuit
  behavior, mutation timing, resource lifetimes, and other side effects. Do not
  move checks ahead of earlier operations if that changes observable behavior.
- Do not extract helpers, introduce abstractions, add checks, or change
  algorithms merely to produce a tidier layout.

## Module and file structure

- Keep the module docstring and imports at the beginning, respecting future
  imports and existing import conventions.
- Place module-level variables and globals immediately after imports and
  before function and class definitions. This includes constants, loggers,
  sentinels, registries, type aliases, and `__all__`.
- Group function and class definitions by logically related responsibility.
  Within each group, generally place functions first and classes second.
  Prefer meaningful conceptual groups over collecting unrelated functions
  together solely because they are functions.
- In a long file with clearly separated logical groups, a global specific to
  one group may appear at the beginning of that group. Shared globals still
  belong at the top. Do not create artificial groups to justify scattered
  assignments, or bury globals between unrelated definitions.
- Use short section comments only when they clarify substantial groups;
  small files do not need a heading for every category.

## Preserve order-dependent behavior

Check definition-time dependencies before moving blocks. Base classes,
decorators, default argument expressions, evaluated annotations, aliases,
and instantiated globals may require earlier definitions. Preserve decorator
application and registration order, including dispatch implementations, and
keep overload declarations with their implementation.

Preserve field order where frameworks such as dataclasses, enums, or Pydantic
give it meaning. Keep executable initialization and entry-point code in an
order that preserves side effects. Do not convert instance state into class
attributes just to put declarations at the top.

When a dependency prevents the preferred layout, make the smallest necessary
exception and explain it in the completion report. Do not introduce lazy
initialization, wrappers, new imports, or other behavioral refactoring merely
to force an ordering rule.

## Validation

Review the diff for unintended changes beyond moving complete definitions or
logical statement blocks and updating their section comments. Check that body
reordering preserves data dependencies and observable execution order. Follow
the project's applicable agent instructions and documented environment setup.
Run the project's required lint checks and tests relevant to the changed code,
including doctests or focused smoke checks where appropriate. For broad
reorganizations, consider a full test run if selective test tracking may miss
affected behavior. Report any checks that could not be run.

Report the files organized, any necessary ordering exceptions, and validation
results.
