"""Factory traversal, resolved annotations, cycles, and model reconstruction."""

from typing import Annotated, Any

import pytest
from pydantic import BaseModel, ConfigDict, Field, create_model

from confidantic import BaseConfig, Factory
from confidantic._config._factory_resolution import (
    _FactoryResolver,
    _ResolvedModelTypes,
    contains_factory,
)
from tests._config.factory_targets import Child, SimpleTarget, UnrelatedTarget


def test_model_resolve_resolves_nested_base_models() -> None:
    """Resolution updates nested BaseModel annotations containing factories."""
    child_type = Factory.model_from(Child)

    class Payload(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)

        child: child_type

    class Parent:
        def __init__(self, payload: Payload) -> None:
            self.payload = payload

    payload = Payload(child=child_type(value=3))
    resolved = Factory.model_from(Parent)(payload=payload).model_resolve()

    assert isinstance(resolved.payload.child, Child)
    assert resolved.payload.child.value == 3


def test_resolved_annotation_rebuilds_container_annotations() -> None:
    """Nested concrete factory annotations are replaced inside containers."""
    child_type = Factory.model_from(Child)

    assert _ResolvedModelTypes().resolve_annotation(list[child_type]) == list[Child]


def test_resolved_annotation_preserves_unchanged_and_union_annotations() -> None:
    """Annotation resolution preserves plain types and rebuilds unions."""
    types = _ResolvedModelTypes()
    assert types.resolve_annotation(Any) is Any
    assert types.resolve_annotation(list[int]) == list[int]
    assert types.resolve_annotation(Factory[Child] | str) == Child | str


def test_resolved_annotation_keeps_unmodified_model_type() -> None:
    """Model types without factory annotations do not create a replacement."""

    class Payload(BaseModel):
        value: int

    assert _ResolvedModelTypes().resolve_annotation(Payload) is Payload


def test_resolve_value_resolves_factory_class() -> None:
    """Recursive value resolution materializes concrete factory classes."""
    child_type = Factory.model_from(Child)

    resolved = _FactoryResolver().resolve(child_type)

    assert isinstance(resolved, Child)


def test_contains_factory_handles_cycles_and_mapping_keys() -> None:
    """Factory detection handles cyclic containers and mapping keys."""
    cyclic: list[Any] = []
    cyclic.append(cyclic)
    assert not contains_factory(cyclic)

    child_type = Factory.model_from(Child)
    assert contains_factory({child_type: "factory key"})


def test_base_config_model_resolve_generates_resolved_model() -> None:
    """BaseConfig resolution replaces Factory fields with target instances."""

    class Config(BaseConfig):
        child: Factory[Child] = Factory.model_from(Child)  # type: ignore[assignment]

    config = Config(child=Factory.model_from(Child)(value=3))

    resolved = config.model_resolve(name="ResolvedConfig")

    assert type(resolved).__name__ == "ResolvedConfig"
    assert type(resolved).model_fields["child"].annotation is Child
    assert isinstance(resolved.child, Child)
    assert resolved.child.value == 3
    assert config.child.value == 3


@pytest.mark.parametrize("name", [None, "ResolvedFactory"])
def test_base_config_resolution_rebuilds_a_factory_root(name: str | None) -> None:
    """An explicit base-method call keeps the root model and resolves its fields."""

    class Parent:
        def __init__(self, child: Factory[Child]) -> None:
            self.child = child

    config = Factory.model_from(Parent)(child=Factory.instance_from(Child, value=3))

    # Pydantic already warns when this path overrides the inherited field.
    with pytest.warns(UserWarning, match='Field name "child".*shadows an attribute'):
        result = BaseConfig.model_resolve(config, name=name)

    assert isinstance(result, Factory)
    assert result.factory_target is Parent
    assert type(result).__name__ == (name or "ParentConfigResolved")
    assert isinstance(result.child, Child)
    assert result.child.value == 3


def test_base_config_model_resolve_resolves_factory_values() -> None:
    """BaseConfig resolution materializes nested factory values."""

    class Config(BaseConfig):
        child: Factory[Child] = Factory.model_from(Child)

    resolved = Config().model_resolve()

    assert type(resolved).model_fields["child"].annotation is Child
    assert isinstance(resolved.child, Child)


def test_model_resolve_preserves_nested_model_extra_values() -> None:
    """Nested model extras survive factory resolution alongside resolved fields."""

    class Payload(BaseModel):
        model_config = ConfigDict(
            arbitrary_types_allowed=True,
            extra="allow",
        )

        child: Factory[Child]

    class Parent:
        def __init__(self, payload: Payload) -> None:
            self.payload = payload

    payload = Payload(child=Factory.model_from(Child)(value=7), label="extra")
    resolved = Factory.model_from(Parent)(payload=payload).model_resolve()

    assert isinstance(resolved.payload.child, Child)
    assert resolved.payload.child.value == 7
    assert resolved.payload.model_extra == {"label": "extra"}


def test_base_config_model_resolve_is_always_recursive() -> None:
    """BaseConfig resolution always materializes nested factories."""

    class Parent:
        def __init__(self, child: Factory[Child]) -> None:
            self.child = child

    class Config(BaseConfig):
        parent: Factory[Parent] = Factory.model_from(Parent)  # type: ignore[assignment]

    child_config = Factory.model_from(Child)(value=4)
    config = Config(parent=Factory.model_from(Parent)(child=child_config))

    resolved = config.model_resolve()

    assert isinstance(resolved.parent, Parent)
    assert isinstance(resolved.parent.child, Child)
    assert resolved.parent.child.value == 4


def test_base_config_model_resolve_without_factories_returns_shallow_copy() -> None:
    """Models without factories do not receive a generated resolved class."""

    class Config(BaseConfig):
        value: int

    config = Config(value=1)

    resolved = config.model_resolve()

    assert type(resolved) is Config
    assert resolved is not config
    assert resolved.value == 1


def test_model_resolve_resolves_nested_factory_configs() -> None:
    """Direct resolution recursively resolves nested factories."""

    class Parent:
        def __init__(
            self, child: Factory[Child], children: list[Factory[Child]]
        ) -> None:
            self.child = child
            self.children = children

    child_config = Factory.model_from(Child)
    parent = Factory.model_from(Parent)(
        child=child_config(value=1),
        children=[child_config(value=2), child_config(value=3)],
    ).model_resolve()

    assert isinstance(parent.child, Child)
    assert [child.value for child in parent.children] == [2, 3]


def test_model_resolve_resolves_nested_factories_in_containers() -> None:
    """Nested factories are resolved in mappings and immutable containers."""

    class Parent:
        def __init__(
            self,
            mapping: dict[str, Any],
            tuple_value: tuple[Any, ...],
            set_value: set[Any],
            frozenset_value: frozenset[Any],
        ) -> None:
            self.mapping = mapping
            self.tuple_value = tuple_value
            self.set_value = set_value
            self.frozenset_value = frozenset_value

    child_config = Factory.model_from(Child)
    parent = (
        Factory.model_from(Parent)
        .model_construct(
            mapping={"child": child_config(value=1)},
            tuple_value=(child_config(value=2),),
            set_value={child_config(value=3)},
            frozenset_value=frozenset({child_config(value=4)}),
        )
        .model_resolve()
    )

    assert parent.mapping["child"].value == 1
    assert parent.tuple_value[0].value == 2
    assert {child.value for child in parent.set_value} == {3}
    assert {child.value for child in parent.frozenset_value} == {4}


def test_factory_accepts_nested_factories_in_set_inputs() -> None:
    """Validated factory configs can be supplied in set-valued inputs."""

    class Parent:
        def __init__(
            self,
            children: set[Factory[Child]],
            frozen_children: frozenset[Factory[Child]],
        ) -> None:
            self.children = children
            self.frozen_children = frozen_children

    child_config = Factory.model_from(Child)
    config = Factory.model_from(Parent)(
        children={child_config(value=1)},
        frozen_children=frozenset({child_config(value=2)}),
    )

    parent = config.model_resolve()

    assert {child.value for child in parent.children} == {1}
    assert {child.value for child in parent.frozen_children} == {2}


def test_model_resolve_rejects_cyclic_values() -> None:
    """Cyclic nested values cannot be recursively resolved."""

    class Parent:
        def __init__(self, payload: Any) -> None:
            self.payload = payload

    payload: list[Any] = []
    payload.append(payload)
    config = Factory.model_from(Parent).model_construct(payload=payload)

    with pytest.raises(ValueError, match="cyclic values cannot be resolved"):
        config.model_resolve()


def test_resolution_constructs_repeated_factory_references_independently() -> None:
    """Shared factory inputs invoke their constructor at each occurrence."""
    calls: list[int] = []

    class Target:
        def __init__(self, value: int = 3) -> None:
            calls.append(value)
            self.value = value

    class Parent:
        def __init__(self, children: Any) -> None:
            self.children = children

    child = Factory.instance_from(Target)
    config = Factory.model_from(Parent).model_construct(children=[child, child])

    result = config.model_resolve()

    assert calls == [3, 3]
    assert result.children[0] is not result.children[1]


def test_resolution_reuses_model_types_only_within_each_call() -> None:
    """Repeated typed models share generated types, but not resolved values."""

    class Payload(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)
        child: Factory[Child]

    class Config(BaseConfig):
        payloads: list[Payload]

    payload = Payload(child=Factory.instance_from(Child, value=3))
    config = Config.model_construct(payloads=[payload, payload])

    first = config.model_resolve()
    second = config.model_resolve()

    assert first.payloads[0] is not first.payloads[1]
    assert type(first.payloads[0]) is type(first.payloads[1])
    assert type(first.payloads[0]) is not type(second.payloads[0])
    assert first.payloads[0].child.value == second.payloads[1].child.value == 3


@pytest.mark.parametrize("container", [dict, list, tuple, set, frozenset])
def test_resolution_normalizes_container_subclasses(container: type[Any]) -> None:
    """Traversal rebuilds builtin containers and resolves mapping keys as well."""

    class Parent:
        def __init__(self, payload: Any) -> None:
            self.payload = payload

    child_type = Factory.model_from(Child)
    subtype = type("Container", (container,), {})
    payload = subtype([(child_type, child_type)] if container is dict else [child_type])
    config = Factory.model_from(Parent).model_construct(payload=payload)

    result = config.model_resolve().payload

    assert type(result) is container
    assert all(isinstance(item, Child) for item in result)
    if container is dict:
        assert all(isinstance(item, Child) for item in result.values())


def test_resolution_without_factories_preserves_cyclic_values() -> None:
    """The shallow-copy path accepts cycles and ignores the generated name."""

    class Config(BaseConfig):
        payload: Any

    cycle: list[Any] = []
    cycle.append(cycle)
    config = Config.model_construct(payload=cycle)

    result = config.model_resolve(name="Unused")

    assert type(result) is Config
    assert result is not config
    assert result.payload is cycle


def test_resolution_preserves_field_details_without_mutating_source() -> None:
    """Annotation replacement retains field defaults, aliases, and metadata."""
    child_type = Factory.model_from(Child)

    class Config(BaseConfig):
        child: Annotated[Factory[Child], "tag"] = Field(
            default=child_type, alias="nested", description="Nested child."
        )

    original = Config.model_fields["child"]
    annotation = original.annotation
    config = Config(nested=child_type(value=3))

    result = config.model_resolve()
    resolved = type(result).model_fields["child"]

    assert result.child.value == 3
    assert resolved.annotation is Child
    assert resolved.alias == original.alias == "nested"
    assert resolved.description == original.description == "Nested child."
    assert resolved.metadata == original.metadata == ["tag"]
    assert resolved.default is original.default is child_type
    assert Config.model_fields["child"] is original
    assert original.annotation is annotation


@pytest.mark.parametrize("unchecked", ["construct", "copy"])
def test_resolution_preserves_arbitrary_objects_and_unchecked_scalars(
    unchecked: str,
) -> None:
    """Resolution forwards scalar values without another factory validation."""

    class Target:
        def __init__(self, value: int, token: Any) -> None:
            self.value = value
            self.token = token

    token = object()
    model = Factory.model_from(Target)
    config = (
        model.model_construct(value="unchecked", token=token)
        if unchecked == "construct"
        else model(value=1, token=token).model_copy(update={"value": "unchecked"})
    )

    result = config.model_resolve()

    assert result.value == "unchecked"
    assert result.token is token


def test_recursive_model_annotations_with_finite_values() -> None:
    class Node(BaseModel, arbitrary_types_allowed=True):
        child: "Node | None" = None
        target: Factory[SimpleTarget] = Factory.model_from(SimpleTarget)

    class Config(BaseConfig):
        first: Node
        second: Node

    original = Config(first=Node(child=Node()), second=Node())
    result = original.model_resolve(name="ResolvedConfig")
    assert type(result).__name__ == "ResolvedConfig"
    assert type(result.first) is type(result.second) is type(result.first.child)
    assert isinstance(result.first.target, SimpleTarget)
    assert isinstance(result.first.child.target, SimpleTarget)
    assert Node.model_fields["target"].annotation is Factory[SimpleTarget]
    assert result.first.target is not result.second.target


def test_unaffected_recursive_annotation_and_actual_cycle() -> None:
    class Node(BaseModel):
        child: "Node | None" = None

    class Config(BaseConfig):
        node: Node
        target: Factory[SimpleTarget] = Factory.model_from(SimpleTarget)

    assert Config(node=Node(child=Node())).model_resolve().node.child is not None
    node = Node()
    node.child = node
    with pytest.raises(ValueError, match="cyclic values"):
        Config.model_construct(node=node).model_resolve()


def test_mutually_recursive_model_annotations() -> None:
    class Left(BaseModel, arbitrary_types_allowed=True):
        right: "Right | None" = None
        target: Factory[SimpleTarget] = Factory.model_from(SimpleTarget)

    class Right(BaseModel):
        left: Left | None = None

    Left.model_rebuild()

    class Config(BaseConfig):
        left: Left

    result = Config(left=Left(right=Right(left=Left()))).model_resolve()
    assert isinstance(result.left.right.left.target, SimpleTarget)
    assert type(result.left) is type(result.left.right.left)


def test_recursive_resolution_keeps_distinct_same_named_types_and_metadata() -> None:
    from pydantic import ConfigDict

    from confidantic._config._factory_resolution import _ResolvedModelTypes

    first_type = create_model(
        "Node",
        __config__=ConfigDict(arbitrary_types_allowed=True),
        target=(Factory[SimpleTarget], Factory.model_from(SimpleTarget)),
    )
    second_type = create_model(
        "Node",
        __config__=ConfigDict(arbitrary_types_allowed=True),
        target=(Factory[UnrelatedTarget], Factory.model_from(UnrelatedTarget)),
    )

    class Config(BaseConfig):
        first: first_type
        second: second_type

    result = Config(first=first_type(), second=second_type()).model_resolve()
    assert type(result.first) is not type(result.second)
    assert isinstance(result.first.target, SimpleTarget)
    assert isinstance(result.second.target, UnrelatedTarget)
    annotation = Annotated[list[Factory[SimpleTarget]], Factory[UnrelatedTarget]]
    assert (
        _ResolvedModelTypes().resolve_annotation(annotation)
        == Annotated[list[SimpleTarget], Factory[UnrelatedTarget]]
    )
