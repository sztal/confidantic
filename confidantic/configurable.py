"""Build runtime objects from durable, validated configuration.

Use :class:`InstanceConfig` to describe every durable input that determines an
object's behavior. Keep caches, open handles, and other transient runtime state
on :class:`Configurable` subclasses; derive that state from ``self.config`` and
do not treat it as part of the object's portable representation.

Persist an ``InstanceConfig`` with its ``model_dump*`` methods. Deserialize it
through the concrete configuration class's ``model_validate*`` methods, then
call :meth:`InstanceConfig.to_parent` to create a new runtime instance. This
module deliberately does not add portable serialization methods to runtime
objects themselves.
"""

from collections.abc import Mapping
from typing import Any, ClassVar, Self

from pydantic import BaseModel

from confidantic import BaseConfig

__all__ = ("Configurable", "InstanceConfig")


class InstanceConfig(BaseConfig):
    """Base configuration for instances of configurable classes.

    Subclass this type to define durable, validated inputs for one concrete
    :class:`Configurable` subclass. Its inherited Pydantic serialization and
    validation methods form the portable persistence boundary; call
    :meth:`to_parent` after validation to construct the runtime object.

    A configuration class receives ``Parent`` only when a configurable class
    directly declares it as ``Config``. This avoids silently associating an
    inherited configuration with an unrelated subclass.
    """

    Parent: ClassVar[type["Configurable"]]

    def to_parent(self, *args: Any, **kwargs: Any) -> "Configurable":
        """Construct this configuration's directly associated parent class.

        Parameters
        ----------
        *args
            Positional arguments forwarded to the parent constructor after this
            configuration.
        **kwargs
            Keyword arguments forwarded to the parent constructor after this
            configuration.

        Returns
        -------
        Configurable
            New instance of the directly associated parent class.

        Raises
        ------
        TypeError
            If this concrete configuration class has no directly declared
            ``Parent`` attribute referring to a Configurable subclass.
        """
        parent_cls = type(self).__dict__.get("Parent")
        if not isinstance(parent_cls, type) or not issubclass(parent_cls, Configurable):
            errmsg = (
                f"cannot construct a parent from '{type(self).__name__}' "
                "without a valid 'Parent' class attribute "
                f"that is a subclass of '{Configurable.__name__}'"
            )
            raise TypeError(errmsg)
        return parent_cls(self, *args, **kwargs)


class Configurable:
    """Base class for runtime objects whose durable behavior comes from configuration.

    Subclasses declare or inherit a concrete :class:`InstanceConfig` as
    ``Config``. New input is validated into that type and exposed through
    ``config``; an existing instance is reused when no updates are supplied.
    Core behavior should derive from this configuration, while instance-specific
    caches and resources remain transient. Copying, equality, hashing, and pickle
    state operate on the configuration rather than arbitrary runtime attributes.

    Serialize and deserialize the concrete ``Config`` class instead of the runtime
    object, then use :meth:`InstanceConfig.to_parent` to materialize an instance.
    """

    Config: ClassVar[type[InstanceConfig]]

    def __init__(
        self,
        config: InstanceConfig | BaseModel | Mapping[Any, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the object with the given configuration.

        Parameters
        ----------
        config
            The configuration for this object. If not provided, a default
            configuration will be created. An instance of ``self.Config`` is
            reused without revalidation when no updates are supplied; with
            updates, :meth:`BaseConfig.copy` creates a validated replacement.
            Other Pydantic models are dumped to mappings before construction.
        **kwargs
            Configuration values used to create or update ``config``, taking
            precedence over mapping input. Normal settings-source priorities
            still apply during construction.
        """
        if not isinstance(getattr(self, "Config", None), type) or not issubclass(
            self.Config, InstanceConfig
        ):
            errmsg = (
                f"cannot instantiate '{self.__class__.__name__}' "
                "without a valid 'Config' class attribute "
                f"that is a subclass of '{InstanceConfig.__name__}'"
            )
            raise TypeError(errmsg)
        if config is None:
            config = self.Config(**kwargs)
        else:
            if isinstance(config, self.Config):
                if kwargs:
                    config = config.copy(**kwargs)
            else:
                if isinstance(config, BaseModel):
                    config = config.model_dump()
                if isinstance(config, Mapping):
                    config = self.Config(**{**config, **kwargs})
                else:
                    errmsg = (  # type: ignore[unreachable]
                        f"Expected config of type {self.Config.__name__}, "
                        f"got {type(config).__name__}"
                    )
                    raise TypeError(errmsg)
        self.config = config

    def __init_subclass__(cls) -> None:
        """Associate a directly declared InstanceConfig class with this subclass."""
        super().__init_subclass__()
        if (
            (config_cls := cls.__dict__.get("Config")) is not None
            and isinstance(config_cls, type)
            and issubclass(config_cls, InstanceConfig)
        ):
            config_cls.Parent = cls

    def __hash__(self) -> int:
        """Return a hash based on the configuration of the object."""
        return hash(self.config)

    def __eq__(self, other: Any) -> bool:
        """Compare model dumps for compatible Configurable instances."""
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.config.model_dump() == other.config.model_dump()

    def __getstate__(self) -> Any:
        """Return only the configuration for pickling; omit other runtime state."""
        return {"config": self.config}

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.config = self.Config.model_validate(state["config"])

    def __copy__(self) -> Self:
        """Construct a new runtime object from a shallow configuration copy."""
        return self.__class__(config=self.config.__copy__())

    def __deepcopy__(self, memo: dict[int, Any] | None = None) -> Self:
        """Construct a new runtime object from a deep configuration copy."""
        return self.__class__(config=self.config.__deepcopy__(memo))

    def reconfigure(self, **kwargs: Any) -> Self:
        """Mutate the existing configuration and return this runtime object.

        Objects sharing this configuration observe the update. The runtime
        constructor is not called again, so derived caches are not refreshed.
        See :meth:`BaseConfig.mutate` for validation and hash implications.

        Parameters
        ----------
        **kwargs
            Keyword arguments to update the configuration of the object.

        Returns
        -------
        Self
            This runtime object.
        """
        self.config.mutate(**kwargs)
        return self

    def rc(self, **kwargs: Any) -> Self:
        """Alias for :meth:`reconfigure`."""
        return self.reconfigure(**kwargs)

    def copy(self, **kwargs: Any) -> Self:
        """Construct a new object, then apply validated configuration updates.

        The constructor receives a shallow configuration copy before updates
        are applied. Arbitrary runtime attributes are not copied.

        Parameters
        ----------
        **kwargs
            Keyword arguments to update the configuration of the copied object.

        Returns
        -------
        Self
            Newly constructed runtime object with its configuration updated.
        """
        return self.__copy__().reconfigure(**kwargs)

    def deepcopy(self, **kwargs: Any) -> Self:
        """Construct a new object from a deep configuration copy, then update it.

        Updates are validated after construction. Arbitrary runtime attributes
        are not copied.

        Parameters
        ----------
        **kwargs
            Keyword arguments to update the configuration of the copied object.

        Returns
        -------
        Self
            Newly constructed runtime object with its configuration updated.
        """
        return self.__deepcopy__().reconfigure(**kwargs)

    def info(self, *args: Any, **kwargs: Any) -> Any:
        """Display configuration values through :meth:`BaseConfig.info`.

        Parameters
        ----------
        *args, **kwargs
            Arguments forwarded unchanged to the configuration's ``info`` method.

        Returns
        -------
        Table | str | None
            The configuration method's table, rendered string, or ``None`` after
            printing, according to its ``output`` argument.
        """
        return self.config.info(*args, **kwargs)
