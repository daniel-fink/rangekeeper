"""Shared lineage and explanation rules for derived Evidence.

A configuration Claim ID alone cannot identify its content. Fingerprint the
complete lineage using the established Evidence encoder, including source editions.
"""

from collections.abc import Iterable

from .evidence import Issue


def settings_inputs(settings):
    if settings is None:
        return {}
    from . import fingerprint, tabular

    evidence = tabular.from_claims(
        name="derivation settings",
        columns=("settings",),
        row_ids=(settings.id,),
        claims={("rows", str(settings.id), "settings"): settings},
    )
    return {"settings": fingerprint(evidence)}


def unique_issues(issues: Iterable[Issue]) -> tuple[Issue, ...]:
    from rangekeeper.graph.operation import _Failure

    indexed: dict[str, Issue] = {}
    for issue in issues:
        if issue.id in indexed and indexed[issue.id] != issue:
            raise _Failure(
                "conflicting_issue", "Issues with the same identity disagree"
            )
        indexed.setdefault(issue.id, issue)
    return tuple(indexed.values())
