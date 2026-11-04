"""Importable configuration models shared by serialization tests."""

from pydantic import BaseModel

from confidantic import BaseConfig
from confidantic.annotations import Make


class PolymorphicConfig(BaseConfig):
    """Base configuration for marker-driven validation tests."""

    name: str


class PolymorphicChildConfig(PolymorphicConfig):
    """Concrete configuration with a child-only field."""

    count: int = 1


class PolymorphicSiblingConfig(PolymorphicConfig):
    """Sibling configuration used to test subtype constraints."""

    enabled: bool = True


class PolymorphicContainer(BaseModel):
    """Pydantic model with polymorphic configuration fields."""

    item: Make[PolymorphicConfig]
    items: list[Make[PolymorphicConfig]]
