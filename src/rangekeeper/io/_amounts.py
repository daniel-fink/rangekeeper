"""Find the currency amounts in serialized data before it becomes records (ADR-023).

A magnitude is a currency amount when its units are one ISO 4217 code: the
``units`` of a Quantity, or of the Flow that contains a Movement. The codecs
use ``amounts`` to give a strict JSON error with the canonical text, and to
read YAML numerals from their source text.
"""

from collections.abc import Callable, Mapping

from rangekeeper.money import is_currency
from rangekeeper.schema.validation import _slot_map
from rangekeeper.shared import pointer
from rangekeeper.shared.amounts import canonical
from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.yaml import Numeral

Convert = Callable[[object, str, str], object]


def amounts(kind: str, data: object, convert: Convert, path: str = "") -> object:
    """Return ``data`` with ``convert(value, units, path)`` for each amount.

    Data that does not match the schema is returned unchanged where it does
    not match; record validation reports it later. Opaque content is not read.
    """
    if not isinstance(data, Mapping):
        return data
    slots = _slot_map(kind)
    result = dict(data)
    units = data.get("units")
    if not isinstance(units, str):
        units = ""
    if kind == "Quantity" and is_currency(units) and "magnitude" in data:
        result["magnitude"] = convert(
            data["magnitude"], units, pointer.child(path, "magnitude")
        )
    if (
        kind == "Flow"
        and is_currency(units)
        and isinstance(data.get("movements"), list)
    ):
        movements = []
        for index, movement in enumerate(data["movements"]):
            if isinstance(movement, Mapping) and movement.get("magnitude") is not None:
                location = pointer.child(path, "movements", index, "magnitude")
                movement = {
                    **movement,
                    "magnitude": convert(movement["magnitude"], units, location),
                }
            movements.append(movement)
        result["movements"] = movements
    for name, meta in slots.items():
        kinds = [
            option["kind"]
            for option in meta["options"]
            if option["category"] in ("record", "keyed")
        ]
        if not kinds or result.get(name) is None:
            continue

        def child(value, *locator, name=name, kind=kinds[0]):
            location = pointer.child(path, name, *locator)
            return amounts(kind, value, convert, location)

        value = result[name]
        if meta["mapping"] and isinstance(value, Mapping):
            result[name] = {key: child(item, key) for key, item in value.items()}
        elif meta["many"] and isinstance(value, list):
            result[name] = [child(item, index) for index, item in enumerate(value)]
        elif not meta["many"]:
            result[name] = child(value)
    return result


def strict(value: object, units: str, path: str) -> object:
    """Require the canonical text of an amount, as JSON does; return it unchanged."""
    if type(value) is str:
        expected = canonical(value)
        if expected is not None and expected != value:
            message = (
                f"currency amount {value!r} in {units} is not canonical text; "
                f"use {expected!r}"
            )
            issue = Issue(
                Code.CURRENCY_AMOUNT, message, path=path, values={"expected": expected}
            )
            ValidationReport((issue,)).raise_if_invalid()
    return value


def lenient(value: object, units: str, path: str) -> object:
    """Read an authored amount: a YAML numeral or any decimal text, made canonical."""
    if isinstance(value, Numeral):
        return canonical(value.text) or value.value
    if type(value) is int:
        return canonical(str(value))
    if type(value) is str:
        return canonical(value) or value
    return value


def detach(value: object, active: set[int] | None = None) -> object:
    """Copy YAML containers and keep their leaves; reject cyclic aliases."""
    if not isinstance(value, (Mapping, list)):
        return value
    active = set() if active is None else active
    if id(value) in active:
        raise ValueError("cyclic data is not JSON")
    active.add(id(value))
    try:
        if isinstance(value, Mapping):
            return {key: detach(child, active) for key, child in value.items()}
        return [detach(child, active) for child in value]
    finally:
        active.remove(id(value))


def numbers(value: object) -> object:
    """Return YAML data with every remaining numeral as its float."""
    if isinstance(value, Numeral):
        return value.value
    if isinstance(value, Mapping):
        return {key: numbers(child) for key, child in value.items()}
    if isinstance(value, list):
        return [numbers(child) for child in value]
    return value


__all__ = ["amounts", "detach", "lenient", "numbers", "strict"]
