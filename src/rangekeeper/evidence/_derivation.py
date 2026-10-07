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
    from rangekeeper.operation import _Failure

    indexed: dict[str, Issue] = {}
    for issue in issues:
        if issue.id in indexed and indexed[issue.id] != issue:
            raise _Failure(
                "conflicting_issue", "Issues with the same identity disagree"
            )
        indexed.setdefault(issue.id, issue)
    return tuple(indexed.values())


def derive_cell(
    *,
    claims,
    issues,
    key,
    value,
    upstream,
    settings,
    method,
    identifier,
    explanations=(),
    rule_id=None,
    reason=None,
    message=None,
):
    """Record one derived cell with shared support and explanation mechanics."""
    from dataclasses import replace
    from . import Claim, Severity

    # Reusing the exact object is safe. Distinct instances with one UUID must
    # reach the canonical identity validator, including a conflicting setting.
    parents = {id(claim): claim for claim in upstream}
    if settings is not None:
        parents.setdefault(id(settings), settings)
    claims[key] = Claim.derived(
        value, from_claims=tuple(parents.values()), method=method, id=identifier
    )
    issues.extend(replace(issue, at=(key,)) for issue in explanations)
    if reason is not None:
        issues.append(
            Issue(
                rule_id=rule_id,
                code=reason,
                severity=Severity.WARNING,
                message=message,
                at=(key,),
                related_claims=tuple(upstream),
            )
        )
