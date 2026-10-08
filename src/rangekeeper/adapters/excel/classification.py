"""Classify physical Excel rows without reopening files or losing observations."""

import re
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from rangekeeper.workflow.operation import _Failure, _invoke
from rangekeeper.workflow.operation import fingerprint as operation_fingerprint
from rangekeeper.workflow.evidence import Evidence, fingerprint, tabular
from rangekeeper.workflow.evidence._derivation import settings_inputs

from rangekeeper.workflow.evidence import Claim, Method, locations
from rangekeeper.shared.table import Table
from rangekeeper.adapters.excel.snapshot import Workbook


@dataclass(frozen=True, slots=True, kw_only=True)
class RowClassificationSpec:
    """Declares which observations establish physical occupancy and which
    identifier pattern distinguishes records from other occupied rows.
    """

    identifier: str
    pattern: str
    output: str = "row_group"
    columns: tuple[str, ...] = ()

    def __post_init__(self):
        if any(
            type(x) is not str or not x
            for x in (self.identifier, self.pattern, self.output)
        ):
            raise ValueError("identifier, pattern and output require text")
        re.compile(self.pattern)
        if isinstance(self.columns, str) or any(
            type(x) is not str or not x for x in self.columns
        ):
            raise TypeError("columns must be names")
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("Classification columns must not repeat")
        object.__setattr__(self, "columns", tuple(self.columns))

    @classmethod
    def from_mapping(cls, value):
        return cls(**dict(value))

    def to_mapping(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def classify_rows(
    evidence,
    workbook: Workbook,
    *,
    specification: RowClassificationSpec,
    settings=None,
    name=None,
):
    """Prevents notes and uncached formulas from being mistaken for absent business
    records. Native occupancy comes from the snapshot; original extracted Claims
    and row identities remain available.
    """
    if not isinstance(evidence, Evidence) or not isinstance(evidence.data, Table):
        raise TypeError("Expected Evidence[Table]")
    if settings is not None and (
        not isinstance(settings, Claim) or type(settings.value) is not str
    ):
        raise TypeError("settings must be Claim[str]")
    if name is not None and (type(name) is not str or not name.strip()):
        raise ValueError("name must be nonempty text")
    if not isinstance(workbook, Workbook) or not isinstance(
        specification, RowClassificationSpec
    ):
        raise TypeError("Expected Workbook and RowClassificationSpec")

    def execute(operation):
        cols = specification.columns or evidence.data.columns
        if specification.identifier not in evidence.data.columns or set(cols) - set(
            evidence.data.columns
        ):
            raise _Failure(
                "missing_column", "Row classification references an absent column"
            )
        if specification.output in evidence.data.columns:
            raise _Failure("output_collision", "Classification output already exists")
        claims = dict(evidence.claims)
        for row in evidence.data.rows:
            parents = tuple(tabular.claim(evidence, row.id, c) for c in cols)
            observed = []
            for parent in parents:
                refs = [
                    loc
                    for loc in locations(parent)
                    if loc.source.id == workbook.source.id
                    and set(loc.reference) == {"sheet", "cell"}
                ]
                if len(refs) != 1:
                    raise _Failure(
                        "ambiguous_native_cell",
                        "Each classified observation must reference one native cell",
                    )
                loc = refs[0]
                observed.append(
                    workbook._require_sheet(loc.reference["sheet"]).cell(
                        loc.reference["cell"]
                    )
                )
            physical_rows = {
                (
                    c.location.reference["sheet"],
                    c.coordinate.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
                )
                for c in observed
            }
            if len(physical_rows) != 1:
                raise _Failure(
                    "inconsistent_native_row",
                    "Classified cells must belong to one physical row",
                )
            identity = tabular.claim(evidence, row.id, specification.identifier)
            group = (
                "blank"
                if not any(c.populated for c in observed)
                else (
                    "matched"
                    if type(identity.value) is str
                    and re.fullmatch(specification.pattern, identity.value)
                    else "other"
                )
            )
            key = ("rows", str(row.id), specification.output)
            parents = tuple({c.id: c for c in (*parents, identity)}.values())
            claims[key] = Claim.derived(
                group,
                from_claims=parents + (() if settings is None else (settings,)),
                method=operation.method,
                id=uuid5(NAMESPACE_URL, operation_fingerprint(operation) + repr(key)),
            )
        return tabular.from_claims(
            name=name or evidence.name,
            columns=(*evidence.data.columns, specification.output),
            row_ids=(r.id for r in evidence.data.rows),
            claims=claims,
            issues=evidence.issues,
        )

    return _invoke(
        Method(code="rk.excel.classify_rows", version="2"),
        {
            **specification.to_mapping(),
            "settings": None if settings is None else str(settings.id),
            "name": name or evidence.name,
        },
        {
            "evidence": fingerprint(evidence),
            "workbook": workbook.fingerprint,
            **settings_inputs(settings),
        },
        execute,
    )
