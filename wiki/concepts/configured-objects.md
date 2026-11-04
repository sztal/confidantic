# Configured objects

Use Configurable when a runtime class should explicitly own an InstanceConfig.
The configuration describes durable inputs; the runtime object owns caches, handles,
and derived resources. This differs from Factory, which derives a configuration
schema from an existing constructor.

## Association and construction

A Configurable subclass directly declares a concrete `Config` class. That declaration
associates the configuration's `Parent`, allowing `config.to_parent()` to construct
the runtime object. Inheriting Config does not change its association. Reusing the
same configuration class in several direct declarations replaces Parent with the
last association; prefer distinct configuration classes when ownership differs.

Construction accepts mappings, Pydantic models, or an existing instance of the
expected configuration class. An existing compatible configuration is reused when
there are no updates. With updates it is copied and validated; normal settings
priority still applies to newly constructed configurations.

## Lifecycle consequences

`reconfigure()` and its `rc()` alias mutate the retained configuration. Other objects
sharing that instance observe the change, but constructors and derived-cache setup
do not run again. `copy(**updates)` constructs a new runtime object from copied
configuration, then applies updates; constructor-derived state may still reflect
the earlier configuration. Design resource refresh explicitly in the runtime class.

Equality and hashing are based on configuration, not arbitrary resources. Pickle
restoration installs configuration without calling the constructor. For portable
persistence, dump the concrete InstanceConfig, validate it on loading, then call
`to_parent()` to build fresh runtime resources.

See [the configured-object guide](../examples/configurable-objects.md),
[implementation details](../api/configurable.md), and
[serialization concepts](serialization.md). Return to [all concepts](README.md).
