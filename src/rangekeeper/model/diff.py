"""Immutable descriptive differences; never an executable patch or merge."""

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from .._comparison import canonical
from .._records import FrozenJSONValue, UNSET, Unset, _freeze
from .._schema.records import Metadata
from ._index import Index

if TYPE_CHECKING:
    from .model import Model


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
    import json
    from .._schema.records import Model as ModelRecord

    left = Index.build(ModelRecord.from_data(before.to_data())).records
    right = Index.build(ModelRecord.from_data(after.to_data())).records
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
        or canonical(left[key]._kind, left[key].to_data())
        != canonical(right[key]._kind, right[key].to_data())
    )
    changes = []

    def visit(a, b, path):
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(a.keys() | b.keys()):
                visit(
                    a.get(key, UNSET),
                    b.get(key, UNSET),
                    path + "/" + key.replace("~", "~0").replace("/", "~1"),
                )
        elif isinstance(a, list) and isinstance(b, list):
            for index in range(max(len(a), len(b))):
                visit(
                    a[index] if index < len(a) else UNSET,
                    b[index] if index < len(b) else UNSET,
                    f"{path}/{index}",
                )
        elif type(a) is not type(b) or a != b:
            changes.append(Change(path, _freeze(a), _freeze(b)))

    visit(
        json.loads(canonical("Model", before.to_data())),
        json.loads(canonical("Model", after.to_data())),
        "",
    )
    return Diff(
        tuple(sorted(right.keys() - left.keys())),
        tuple(sorted(left.keys() - right.keys())),
        tuple(sorted(modified)),
        tuple(changes),
    )
