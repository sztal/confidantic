Replaced `FactoryConfig` with generic `Factory[T]`. Annotate factory fields with
the materialized target type, such as `service: Factory[Service]`, and use
`Factory[Service].instance_from(Service)` for a type-safe default.
