"""Importable constructor targets shared by factory tests."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel

from confidantic import Factory

_UNTYPED_DEFAULT = object()


class Product:
    """Target with representative constructor parameter kinds."""

    def __init__(
        self,
        count: int,
        label: str = "default",
        untyped: Any = _UNTYPED_DEFAULT,
        *args: Any,
        enabled: bool = True,
        **kwargs: Any,
    ) -> None:
        self.count = count
        self.label = label
        self.untyped = untyped
        self.args = args
        self.enabled = enabled
        self.kwargs = kwargs


Product.__init__.__annotations__.pop("untyped")


class Basket:
    """Target with mutable constructor attributes."""

    def __init__(self, items: list[str], metadata: dict[str, int]) -> None:
        self.items = items
        self.metadata = metadata


class Child:
    """Nested materialization target."""

    def __init__(self, value: int | None = None) -> None:
        self.value = value


class ServiceBase:
    """Base type for selector matching tests."""


class Service(ServiceBase):
    """Concrete service used as a nested factory source."""

    def __init__(self, value: int = 1) -> None:
        self.value = value


_DEFAULT_SERVICE = Service()


class ServiceHolder:
    """Target with a concrete nested service default."""

    def __init__(
        self, service: ServiceBase = _DEFAULT_SERVICE, label: str = "holder"
    ) -> None:
        self.service = service
        self.label = label


class OptionalServiceHolder:
    """Target with an optional concrete nested service default."""

    def __init__(self, service: ServiceBase | None = None) -> None:
        self.service = service


class AlternativeServiceHolder:
    """Target with nested factory and unrelated union alternatives."""

    def __init__(self, service: ServiceBase | str | None = None) -> None:
        self.service = service


class ParameterizedAlternativeServiceHolder:
    """Target with literal and annotated union alternatives."""

    def __init__(
        self,
        service: ServiceBase
        | Literal["fallback"]
        | Annotated[str, "tag"]
        | None = None,
    ) -> None:
        self.service = service


class RequiredServiceHolder:
    """Target with a required service field."""

    def __init__(self, service: ServiceBase) -> None:
        self.service = service


class ProductModel(BaseModel):
    """Model containing a typed product factory."""

    factory: Factory[Product]


class SimpleTarget:
    """Importable constructor for directive round trips."""

    def __init__(self, value: int = 1) -> None:
        self.value = value


class DerivedTarget(SimpleTarget):
    """Compatible subclass for factory validation."""


class UnrelatedTarget:
    """Unrelated factory target."""


_DEFAULT_TARGET = SimpleTarget()


class ParentTarget:
    """Target containing a concrete default."""

    def __init__(self, child: SimpleTarget = _DEFAULT_TARGET) -> None:
        self.child = child
