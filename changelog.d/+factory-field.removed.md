Removed the `FactoryField` API. Use generic `Factory[T]` fields instead; factory
input validation now only checks target compatibility and converts non-factory
target values through `Factory.model_from()`.
