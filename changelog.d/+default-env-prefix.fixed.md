Changed `BaseConfig` environment parsing to require an explicit `env_prefix`.
Use `env_prefix=""` for unprefixed process variables; `env_prefix=None` still
loads dotenv files without a prefix.
