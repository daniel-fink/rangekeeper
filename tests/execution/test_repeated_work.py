"""A solve does its repeated work once and keeps its results and checks (#523)."""

from collections import Counter
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from rangekeeper.errors import UnitError
from rangekeeper.execution import bind_roles, dates, expansion, resolve_cases, validate
from rangekeeper.execution.compiler import Affine, Compiler
from rangekeeper.execution.expansion import _Expansion
from rangekeeper.execution.pipeline import Pinned
from rangekeeper.quantity import UnitSystem
from rangekeeper.schema.runtime import _decode_uuid, _decode_uuids
from rangekeeper.shared.errors import UnsupportedError
from tests.execution.test_expansion import levered
from tests.execution.test_stages import bound


def levered_binding():
    specification = levered()
    cases = resolve_cases(specification=specification, resolver=Pinned(specification))
    return bind_roles(
        validation=validate(
            composition=cases.compositions[specification.id], resolver=cases
        )
    )


def predicates(binding) -> list[object]:
    return [item.predicate.to_data() for item in binding.assertions]


def test_expand_settled_gives_what_two_expansions_give():
    binding = levered_binding()
    settled = dates.settle(binding)
    whole, remaining = expansion.expand_settled(settled, original=binding.assertions)
    separate = expansion.expand(replace(settled, assertions=binding.assertions))
    assert predicates(whole) == predicates(separate)
    assert predicates(remaining) == predicates(expansion.expand(settled))
    assert len(remaining.assertions) > 1


def test_expand_settled_expands_a_kept_assertion_once(monkeypatch):
    binding = levered_binding()
    settled = dates.settle(binding)
    seen = Counter()
    original = _Expansion.assertion

    def counting(self, item):
        if item.predicate.id in kept:
            seen[item.predicate.id] += 1
        return original(self, item)

    kept = {item.predicate.id for item in settled.assertions}
    monkeypatch.setattr(_Expansion, "assertion", counting)
    expansion.expand_settled(settled, original=binding.assertions)
    assert set(seen.values()) == {1}


def test_a_fixed_call_is_evaluated_once_for_all_of_its_periods(monkeypatch):
    binding = levered_binding()
    seen = Counter()
    original = _Expansion.evaluate

    def counting(self, node, *, probes, periods):
        if self.fixed(node):
            seen[node.id] += 1
        return original(self, node, probes=probes, periods=periods)

    monkeypatch.setattr(_Expansion, "evaluate", counting)
    expansion.expand(dates.settle(binding))
    assert seen and set(seen.values()) == {1}


def test_a_compiler_checks_each_pair_of_units_once(monkeypatch):
    _, binding = bound()
    seen = Counter()
    original = UnitSystem.convert

    def counting(self, *, quantity, to):
        seen[quantity.units, to] += 1
        return original(self, quantity=quantity, to=to)

    monkeypatch.setattr(UnitSystem, "convert", counting)
    compiler = Compiler(binding)
    for _ in range(3):
        for item in binding.assertions:
            compiler.assertion(item)
    assert seen and set(seen.values()) == {2}  # at zero and at one


def test_a_compiler_scales_by_the_factor_of_the_pair():
    _, binding = bound()
    compiler = Compiler(binding)
    id = uuid4()
    value = Affine(2.0, {id: 3.0}, "km")
    for _ in range(2):
        converted = compiler.convert(value, "m")
        assert converted.units == "m"
        assert converted.constant == 2000.0
        assert converted.coefficients == {id: 3000.0}


def test_a_compiler_checks_a_failing_pair_of_units_each_time():
    _, binding = bound()
    compiler = Compiler(binding)
    for _ in range(2):
        with pytest.raises(UnitError):
            compiler.factor("AUD", "m")


def test_a_compiler_rejects_offset_units_each_time(monkeypatch):
    _, binding = bound()
    original = UnitSystem.convert

    def offset(self, *, quantity, to):
        converted = original(self, quantity=quantity, to=to)
        return converted.replace(magnitude=converted.number + 1)

    monkeypatch.setattr(UnitSystem, "convert", offset)
    compiler = Compiler(binding)
    for _ in range(2):
        with pytest.raises(UnsupportedError, match="offset unit"):
            compiler.factor("km", "m")


def test_a_record_decodes_the_same_identity_from_any_spelling():
    identity = UUID("12345678-1234-5678-1234-567812345678")
    assert _decode_uuid(str(identity)) == identity
    assert _decode_uuid(str(identity).upper()) == identity
    assert _decode_uuid(identity) is identity
    assert _decode_uuid(None) is None
    assert _decode_uuids([str(identity), identity]) == (identity, identity)


def test_a_record_rejects_an_invalid_identity_each_time():
    for _ in range(2):
        with pytest.raises(ValueError, match="badly formed"):
            _decode_uuid("not an identity")
