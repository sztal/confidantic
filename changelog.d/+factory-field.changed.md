`Factory` is now nongeneric; annotate typed factory fields with `Factory.Field[T]`. `BaseConfig` validates field defaults by default, and typed factory fields reject factories for another target.
