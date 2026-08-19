from __future__ import annotations

import datetime
import math
from collections.abc import Mapping
from numbers import Integral, Real

import pint

from .errors import SnapshotError, UnsupportedValueError
from .fields import Fields


_TYPE_KEY = "__rangekeeper_type__"


def encode(value: object, *, path: str) -> object:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        number = float(value)
        if not math.isfinite(number):
            raise UnsupportedValueError(
                f"{path} contains non-finite numeric value {number!r}"
            )
        return number
    if isinstance(value, datetime.datetime):
        return {_TYPE_KEY: "datetime", "value": value.isoformat()}
    if isinstance(value, datetime.date):
        return {_TYPE_KEY: "date", "value": value.isoformat()}
    if isinstance(value, pint.Quantity):
        return {
            _TYPE_KEY: "quantity",
            "magnitude": encode(value.magnitude, path=f"{path} magnitude"),
            "units": str(value.units),
        }
    if isinstance(value, tuple):
        return {
            _TYPE_KEY: "tuple",
            "items": tuple(
                encode(item, path=f"{path}[{index}]")
                for index, item in enumerate(value)
            ),
        }
    if isinstance(value, list):
        return {
            _TYPE_KEY: "list",
            "items": tuple(
                encode(item, path=f"{path}[{index}]")
                for index, item in enumerate(value)
            ),
        }
    if isinstance(value, Mapping):
        items = []
        for key, item in value.items():
            if not isinstance(key, str):
                raise UnsupportedValueError(
                    f"{path} contains unsupported mapping key type "
                    f"{type(key).__name__}"
                )
            items.append((key, encode(item, path=f"{path}[{key!r}]")))
        return {_TYPE_KEY: "mapping", "items": tuple(items)}
    raise UnsupportedValueError(
        f"{path} has unsupported value type {type(value).__name__}"
    )


def decode(
    value: object,
    *,
    registry: pint.UnitRegistry,
    path: str,
) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if not isinstance(value, Mapping):
        raise SnapshotError(f"{path} contains an invalid encoded value")
    fields = Fields(value, path)
    value_type = fields.get(_TYPE_KEY)
    if value_type == "datetime":
        try:
            return datetime.datetime.fromisoformat(fields.text("value"))
        except ValueError as error:
            raise SnapshotError(f"{path} contains an invalid datetime") from error
    if value_type == "date":
        try:
            return datetime.date.fromisoformat(fields.text("value"))
        except ValueError as error:
            raise SnapshotError(f"{path} contains an invalid date") from error
    if value_type == "quantity":
        units = registry.parse_units(fields.text("units"))
        magnitude = decode(
            fields.required("magnitude"),
            registry=registry,
            path=f"{path} magnitude",
        )
        return magnitude * units
    if value_type in ("tuple", "list"):
        items = fields.sequence("items")
        decoded = [
            decode(item, registry=registry, path=f"{path}[{index}]")
            for index, item in enumerate(items)
        ]
        return tuple(decoded) if value_type == "tuple" else decoded
    if value_type == "mapping":
        decoded: dict[str, object] = {}
        for index, pair in enumerate(fields.sequence("items")):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise SnapshotError(f"{path} mapping item {index} is invalid")
            key, item = pair
            if not isinstance(key, str):
                raise SnapshotError(f"{path} mapping key must be a string")
            if key in decoded:
                raise SnapshotError(f"{path} contains duplicate mapping key {key!r}")
            decoded[key] = decode(
                item,
                registry=registry,
                path=f"{path}[{key!r}]",
            )
        return decoded
    raise SnapshotError(f"{path} contains unknown encoded value type {value_type!r}")
