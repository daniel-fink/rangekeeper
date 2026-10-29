"""Every extension point uses one registry pattern (ADR-013)."""

import sys
import threading
from importlib import metadata
from typing import Protocol, runtime_checkable

import pytest

from rangekeeper.errors import (
    Code,
    ExtensionConflictError,
    RangekeeperError,
    UnknownExtensionError,
)
from rangekeeper.shared.registry import FORMAT, Registry, fingerprint


@runtime_checkable
class Greeter(Protocol):
    def greet(self) -> str: ...


class Hello:
    def greet(self) -> str:
        return "hello"


class Other:
    def greet(self) -> str:
        return "other"


HELLO = Hello()


def declare(monkeypatch, group, **names):
    """Make ``metadata.entry_points`` declare names in one group."""
    entries = [metadata.EntryPoint(name, value, group) for name, value in names.items()]
    original = metadata.entry_points

    def entry_points(**selection):
        if selection.get("group") == group:
            return metadata.EntryPoints(entries)
        return original(**selection)

    monkeypatch.setattr(metadata, "entry_points", entry_points)


def test_registered_implementation_is_found_by_name():
    registry: Registry[Greeter] = Registry("greeters", Greeter)
    registration = registry.register(name="hello", implementation=HELLO)
    assert registry.get("hello") is HELLO
    assert registry.registration("hello") is registration
    assert registry.names() == ("hello",)
    assert "hello" in registry and "other" not in registry
    assert registry.group == "rangekeeper.greeters"
    assert registration.qualified_name == "rangekeeper.greeters:hello"
    assert registration.fingerprint.startswith(FORMAT + ":")


def test_registration_checks_the_protocol_and_the_name():
    registry: Registry[Greeter] = Registry("greeters", Greeter)
    with pytest.raises(TypeError, match="must be Greeter"):
        registry.register(name="text", implementation="not a greeter")
    for name in ("", "Hello", "1st", "a b", "a--b", "trailing-"):
        with pytest.raises(ValueError, match="invalid greeters name"):
            registry.register(name=name, implementation=HELLO)
    for name in ("pyomo-highs", "imperial_us", "speckle.v2", "a1"):
        registry.register(name=name, implementation=HELLO)


def test_protocols_must_be_runtime_checkable():
    class Plain(Protocol):
        def greet(self) -> str: ...

    with pytest.raises(TypeError, match="runtime_checkable"):
        Registry("greeters", Plain)
    with pytest.raises(ValueError, match="extension point name"):
        Registry("Greeters", Greeter)


def test_a_used_name_needs_an_explicit_replacement():
    registry: Registry[Greeter] = Registry("greeters", Greeter)
    first = registry.register(name="hello", implementation=HELLO)
    assert registry.register(name="hello", implementation=HELLO) is first
    other = Other()
    with pytest.raises(ExtensionConflictError, match="replace=True"):
        registry.register(name="hello", implementation=other)
    assert registry.get("hello") is HELLO
    registry.register(name="hello", implementation=other, replace=True)
    assert registry.get("hello") is other


def test_unknown_names_fail_with_suggestions():
    registry: Registry[Greeter] = Registry("greeters", Greeter)
    registry.register(name="pyomo-highs", implementation=HELLO)
    with pytest.raises(UnknownExtensionError, match="did you mean") as error:
        registry.get("pyomo-hghs")
    assert error.value.suggestions == ("pyomo-highs",)
    assert isinstance(error.value, LookupError)
    assert isinstance(error.value, RangekeeperError)
    assert error.value.code is Code.EXTENSION_UNKNOWN
    assert ExtensionConflictError("x").code is Code.EXTENSION_CONFLICT


def test_entry_points_load_on_first_lookup(monkeypatch):
    module = type(sys)("greeter_plugin")
    module.greeter = Other()
    monkeypatch.setitem(sys.modules, "greeter_plugin", module)
    declare(monkeypatch, "rangekeeper.greeters", other="greeter_plugin:greeter")
    registry: Registry[Greeter] = Registry("greeters", Greeter)
    registry.register(name="hello", implementation=HELLO)
    assert registry.names() == ("hello", "other")
    assert registry.get("other") is module.greeter
    assert registry.registration("other").qualified_name == (
        "rangekeeper.greeters:other"
    )


def test_entry_points_cannot_replace_a_registered_name(monkeypatch):
    module = type(sys)("greeter_plugin")
    module.greeter = Other()
    monkeypatch.setitem(sys.modules, "greeter_plugin", module)
    declare(monkeypatch, "rangekeeper.greeters", hello="greeter_plugin:greeter")
    registry: Registry[Greeter] = Registry("greeters", Greeter)
    registry.register(name="hello", implementation=HELLO)
    assert registry.get("hello") is HELLO


def test_broken_or_ambiguous_entry_points_fail_explicitly(monkeypatch):
    declare(monkeypatch, "rangekeeper.greeters", broken="missing_greeter_module:x")
    registry: Registry[Greeter] = Registry("greeters", Greeter)
    with pytest.raises(ImportError, match="'broken' in rangekeeper.greeters"):
        registry.get("broken")

    entries = metadata.EntryPoints(
        [
            metadata.EntryPoint("twice", "a:b", "rangekeeper.twice"),
            metadata.EntryPoint("twice", "c:d", "rangekeeper.twice"),
        ]
    )
    monkeypatch.setattr(metadata, "entry_points", lambda **selection: entries)
    with pytest.raises(ExtensionConflictError, match="several distributions"):
        Registry("twice", Greeter).get("twice")


def test_entry_points_must_satisfy_the_protocol(monkeypatch):
    module = type(sys)("greeter_plugin")
    module.greeter = object()
    monkeypatch.setitem(sys.modules, "greeter_plugin", module)
    declare(monkeypatch, "rangekeeper.greeters", odd="greeter_plugin:greeter")
    with pytest.raises(TypeError, match="must be Greeter"):
        Registry("greeters", Greeter).get("odd")


def test_describe_names_registered_and_unregistered_implementations():
    registry: Registry[Greeter] = Registry("greeters", Greeter)
    registry.register(name="hello", implementation=HELLO)
    assert registry.describe(HELLO).qualified_name == "rangekeeper.greeters:hello"
    other = registry.describe(Other())
    assert not other.registered
    assert other.qualified_name == f"{__name__}:Other"
    assert other.fingerprint == fingerprint(Other())
    with pytest.raises(TypeError):
        registry.describe(object())


def test_state_fingerprints_come_from_the_registry():
    registry: Registry[Greeter] = Registry(
        "greeters", Greeter, fingerprint=lambda item: "state:" + item.greet()
    )
    assert (
        registry.register(name="hello", implementation=HELLO).fingerprint
        == "state:hello"
    )
    assert (
        registry.register(
            name="x", implementation=Other(), fingerprint="given"
        ).fingerprint
        == "given"
    )


def test_fingerprints_are_lazy_and_follow_the_source(monkeypatch):
    calls = []
    registry: Registry[Greeter] = Registry(
        "greeters", Greeter, fingerprint=lambda item: calls.append(item) or "f"
    )
    registration = registry.register(name="hello", implementation=HELLO)
    assert calls == []
    assert registration.fingerprint == registration.fingerprint == "f"
    assert calls == [HELLO]

    assert fingerprint(HELLO) == fingerprint(Hello) == fingerprint(Hello())
    assert fingerprint(HELLO) != fingerprint(Other())
    assert fingerprint(HELLO, modules=("rangekeeper.shared.registry",)) != (
        fingerprint(HELLO)
    )


def test_fingerprints_cover_code_without_a_module_file():
    for module in ("__main__", "rk_unimported_script"):
        namespace: dict = {"__name__": module}
        exec("class Script:\n    def greet(self):\n        return 'x'\n", namespace)
        # exec leaves no source to read; the fingerprint still names the class.
        assert fingerprint(namespace["Script"]()).startswith(FORMAT + ":")


def test_registration_is_thread_safe():
    registry: Registry[Greeter] = Registry("greeters", Greeter)
    found = []

    def register():
        found.append(registry.register(name="hello", implementation=HELLO))

    threads = [threading.Thread(target=register) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len({id(item) for item in found}) == 1


def test_each_extension_point_has_one_registry():
    import rangekeeper.execution.backends as backends
    import rangekeeper.io as io
    import rangekeeper.quantity as quantity

    points = {
        backends.registry.point: backends.registry,
        quantity.unit_systems.point: quantity.unit_systems,
        io.geometry_providers.point: io.geometry_providers,
    }
    assert set(points) == {"backends", "unit_systems", "geometry_providers"}
    assert all(isinstance(item, Registry) for item in points.values())
    assert backends.registry.get("pyomo-highs").__class__ is backends.PyomoHighs
    assert quantity.unit_systems.get("default") is quantity.default_units


def test_bundles_fall_back_to_registered_geometry_providers(monkeypatch):
    from rangekeeper.io import GeometryProvider, geometry
    from rangekeeper.io.geometry import find

    class Provider:
        def validate(self, *, path, geometry):
            return None

    registry: Registry[GeometryProvider] = Registry(
        "geometry_providers", GeometryProvider
    )
    provider = registry.register(
        name="speckle", implementation=Provider()
    ).implementation
    monkeypatch.setattr(geometry, "geometry_providers", registry)
    assert find("speckle") is provider
    assert find("Speckle") is None
    assert find("other") is None
