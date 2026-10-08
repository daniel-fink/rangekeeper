"""Immutable descriptive differences; never an executable patch or merge."""

from dataclasses import dataclass
from collections.abc import Mapping
from typing import TYPE_CHECKING
from uuid import UUID

from rangekeeper.schema.runtime import comparison_data, exact_equal
from rangekeeper.schema.runtime import FrozenJSONValue, UNSET, Unset, _freeze
from rangekeeper.schema.records import Metadata

if TYPE_CHECKING:
    from rangekeeper.model.model import Model


@dataclass(frozen=True, slots=True)
class Change:
    """A JSON-pointer difference; UNSET distinguishes a missing key from null."""

    path: str
    before: FrozenJSONValue | Unset
    after: FrozenJSONValue | Unset


@dataclass(frozen=True, slots=True)
class Diff:
    """Changed declaration identities and immutable, representation-level details."""

    added: tuple[UUID, ...]
    removed: tuple[UUID, ...]
    modified: tuple[UUID, ...]
    changes: tuple[Change, ...]


def between(before: "Model", after: "Model") -> Diff:
    """Compare any two Models without requiring lineage or altering either.

    Schema-unordered collections compare independent of encounter order. Paths in
    ``changes`` refer to canonical comparison order; interchange exports retain
    original order. Ordered mathematics and opaque content are never reordered.
    """

    left = before._index.records
    right = after._index.records
    left = {
        key: value for key, value in left.items() if not isinstance(value, Metadata)
    }
    right = {
        key: value for key, value in right.items() if not isinstance(value, Metadata)
    }
    modified = tuple(
        key
        for key in left.keys() & right.keys()
        if type(left[key]) is not type(right[key])
        or not left[key].equivalent(right[key])
    )
    changes = []

    def visit(a, b, path):
        if isinstance(a, Mapping) and isinstance(b, Mapping):
            for key in sorted(a.keys() | b.keys()):
                visit(
                    a.get(key, UNSET),
                    b.get(key, UNSET),
                    path + "/" + key.replace("~", "~0").replace("/", "~1"),
                )
        elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            for index in range(max(len(a), len(b))):
                visit(
                    a[index] if index < len(a) else UNSET,
                    b[index] if index < len(b) else UNSET,
                    f"{path}/{index}",
                )
        elif not exact_equal(a, b):
            changes.append(Change(path, _freeze(a), _freeze(b)))

    visit(
        comparison_data("Model", before._record._data),
        comparison_data("Model", after._record._data),
        "",
    )
    return Diff(
        tuple(sorted(right.keys() - left.keys())),
        tuple(sorted(left.keys() - right.keys())),
        tuple(sorted(modified)),
        tuple(changes),
    )
