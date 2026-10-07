"""Independent source-layout and revision-map migration contracts, without solving."""

from copy import deepcopy
import json
from uuid import UUID, uuid5

import pytest

from rangekeeper.io import MemoryStore
from rangekeeper.migration import upgrade_model, upgrade_specification


def uid(value):
    return str(UUID(int=value))


def source_model():
    return {
        "metadata": {"id": uid(1), "schema_version": "0.5.0"},
        "definitions": {
            "measures": [
                {
                    "id": uid(2),
                    "code": "factor",
                    "name": "Factor",
                    "units": "dimensionless",
                }
            ]
        },
        "system": {
            "formulations": [
                {
                    "id": uid(3),
                    "values": [
                        {
                            "id": uid(identity),
                            "key": key,
                            "kind": "flow",
                            "measure": uid(2),
                            "flow": {
                                "units": "dimensionless",
                                "movements": [
                                    {
                                        "key": "month",
                                        "period": {
                                            "start": "2026-01-01",
                                            "end": "2026-02-01",
                                        },
                                        "date": "2026-02-05",
                                        "magnitude": magnitude,
                                    }
                                ],
                            },
                        }
                        for identity, key, magnitude in (
                            (4, "observed", 1),
                            (5, "control", None),
                        )
                    ],
                }
            ]
        },
        "provenance": {
            "claims": [
                {
                    "id": uid(6),
                    "kind": "asserted",
                    "method": {"code": "historical"},
                    "content": {
                        "points": [
                            {"period": {"start": "opaque", "end_exclusive": False}}
                        ],
                        "value": uid(4),
                        "movement": "month",
                        "absent": None,
                        "zero": 0,
                    },
                }
            ]
        },
    }


def source_policy():
    control = {"value": uid(5), "movement": "month"}
    observed = {"value": uid(4), "movement": "month"}
    return {
        "metadata": {"id": uid(10), "schema_version": "0.5.0"},
        "model": uid(1),
        "policy": {
            "id": uid(11),
            "targets": [control],
            "points": [
                {
                    "id": uid(12),
                    "at": "2026-02-05",
                    "observations": [{"name": "observed", "target": observed}],
                    "rules": [
                        {
                            "id": uid(13),
                            "condition": {
                                "id": uid(14),
                                "kind": "binary",
                                "operator": "greater_than",
                                "operands": [
                                    {
                                        "id": uid(15),
                                        "kind": "reference",
                                        "target": observed,
                                    },
                                    {
                                        "id": uid(16),
                                        "kind": "quantity",
                                        "quantity": {
                                            "magnitude": 0,
                                            "units": "dimensionless",
                                        },
                                    },
                                ],
                            },
                            "actions": [
                                {
                                    "kind": "assign",
                                    "target": control,
                                    "quantity": {
                                        "magnitude": 1,
                                        "units": "dimensionless",
                                    },
                                }
                            ],
                        }
                    ],
                    "fallback": [
                        {
                            "kind": "assign",
                            "target": control,
                            "quantity": {"magnitude": 0, "units": "dimensionless"},
                        }
                    ],
                }
            ],
        },
    }


def test_policy_source_walk_reaches_nested_conditions_and_preserves_evidence():
    old_model, old_spec = source_model(), source_policy()
    before_model, before_spec = deepcopy(old_model), deepcopy(old_spec)
    model = upgrade_model(old_model, revision_id=UUID(int=101))
    spec = upgrade_specification(old_spec, model=model.id, revision_id=UUID(int=110))
    observed = uuid5(UUID(int=4), "movement:month")
    controlled = uuid5(UUID(int=5), "movement:month")
    point = spec.record.policy.decisions[0]
    assert point.id == UUID(int=12)
    assert point.rules[0].condition.operands[0].target.target == observed
    assert point.observations[0].target.target == observed
    assert point.rules[0].actions[0].target.target == controlled
    assert point.fallback[0].target.target == controlled
    assert spec.record.policy.targets[0].target == controlled
    movement = model.movement(observed)
    assert movement.period.to_data() == {
        "start_inclusive": "2026-01-01",
        "end_exclusive": "2026-02-01",
    }
    assert movement.date.isoformat() == "2026-02-05"
    assert json.dumps(model.provenance.to_data()) == json.dumps(old_model["provenance"])
    assert model.id == UUID(int=101) and model.metadata.previous == UUID(int=1)
    assert spec.id == UUID(int=110) and spec.metadata.previous == UUID(int=10)
    assert old_model == before_model and old_spec == before_spec
    store = MemoryStore()
    store.put(model)
    spec.compose(resolver=store).validate(resolver=store).raise_if_invalid()


@pytest.mark.parametrize("field", ["includes", "cases"])
def test_external_pins_need_complete_distinct_mappings_and_keep_order(field):
    old = {
        "metadata": {"id": uid(20), "schema_version": "0.6.0"},
        "model": uid(1),
        field: [uid(22), uid(21)],
    }
    before = deepcopy(old)
    mapping = {
        UUID(int=1): UUID(int=101),
        UUID(int=21): UUID(int=121),
        UUID(int=22): UUID(int=122),
    }
    result = upgrade_specification(old, revisions=mapping, revision_id=UUID(int=120))
    assert result.record.model == UUID(int=101)
    assert getattr(result.record, field) == (UUID(int=122), UUID(int=121))
    assert result.metadata.previous == UUID(int=20) and result.id == UUID(int=120)
    assert old == before
    with pytest.raises(ValueError, match="complete"):
        upgrade_specification(old, revisions={UUID(int=1): UUID(int=101)})
    with pytest.raises(ValueError, match="conflicting"):
        upgrade_specification(old, revisions={**mapping, UUID(int=22): UUID(int=121)})
    with pytest.raises(ValueError, match="conflicting"):
        upgrade_specification(old, model=UUID(int=102), revisions=mapping)
    with pytest.raises(ValueError, match="reuse known source"):
        upgrade_specification(old, revisions={**mapping, UUID(int=21): UUID(int=22)})
    for conflict in (1, 21, 101, 121):
        with pytest.raises(ValueError, match="Specification revision UUID"):
            upgrade_specification(
                old, revisions=mapping, revision_id=UUID(int=conflict)
            )
    with pytest.raises(ValueError, match="conflicting"):
        upgrade_specification(
            old,
            model=UUID(int=121),
            revisions={
                key: value for key, value in mapping.items() if key != UUID(int=1)
            },
        )


@pytest.mark.parametrize("version", ["0.3.0", "0.4.0", "0.5.0", "0.6.0"])
def test_all_supported_model_versions_get_new_revisions(version):
    source = {"metadata": {"id": uid(30), "schema_version": version}}
    result = upgrade_model(source, revision_id=UUID(int=130))
    assert result.metadata.schema_version == "0.7.0"
    assert result.metadata.previous == UUID(int=30)
    assert result.id == UUID(int=130)


@pytest.mark.parametrize("version", ["0.4.0", "0.5.0", "0.6.0"])
def test_all_supported_specification_versions_get_new_revisions(version):
    source = {"metadata": {"id": uid(30), "schema_version": version}}
    result = upgrade_specification(source, revision_id=UUID(int=130))
    assert result.metadata.schema_version == "0.7.0"
    assert result.metadata.previous == UUID(int=30)
    assert result.id == UUID(int=130)


@pytest.mark.parametrize("version", ["0.2.0", "0.7.0", "9.0.0"])
def test_unknown_or_current_source_versions_are_not_guessed(version):
    source = {"metadata": {"id": uid(30), "schema_version": version}}
    with pytest.raises(ValueError, match="expected Model version"):
        upgrade_model(source)
    with pytest.raises(ValueError, match="expected Specification version"):
        upgrade_specification(source)


def test_mixed_period_policy_and_reference_layouts_fail_before_facade_construction(
    monkeypatch,
):
    from rangekeeper.model import Model
    from rangekeeper.specification import Specification

    def forbidden(*args, **kwargs):
        raise AssertionError("mixed source layout reached current facade")

    monkeypatch.setattr(Model, "from_data", forbidden)
    monkeypatch.setattr(Specification, "from_data", forbidden)
    old_model = source_model()
    period = old_model["system"]["formulations"][0]["values"][0]["flow"]["movements"][
        0
    ]["period"]
    period["end_exclusive"] = period["end"]
    with pytest.raises(ValueError, match="mixed source layout"):
        upgrade_model(old_model)
    old_spec = source_policy()
    old_spec["policy"]["decisions"] = []
    with pytest.raises(ValueError, match="mixed source layout"):
        upgrade_specification(old_spec, model=UUID(int=101))
    old_spec = source_policy()
    old_spec["policy"]["targets"][0]["target"] = uid(50)
    with pytest.raises(ValueError, match="mixed direct and owner/key"):
        upgrade_specification(old_spec, model=UUID(int=101))


@pytest.mark.parametrize("field", ["assignments", "estimates"])
def test_mixed_assignment_layout_fails_before_facade_construction(field, monkeypatch):
    from rangekeeper.specification import Specification

    def forbidden(*args, **kwargs):
        raise AssertionError("mixed source assignment reached current facade")

    monkeypatch.setattr(Specification, "from_data", forbidden)
    source = {
        "metadata": {"id": uid(30), "schema_version": "0.4.0"},
        field: [
            {
                "value": uid(40),
                "target": {"value": uid(40)},
                "quantity": {"magnitude": 1, "units": "dimensionless"},
            }
        ],
    }
    with pytest.raises(ValueError, match="mixed source Assignment"):
        upgrade_specification(source)


@pytest.mark.parametrize(
    "upgrade,kind", [(upgrade_model, "Model"), (upgrade_specification, "Specification")]
)
@pytest.mark.parametrize("case", ["upper", "mixed", "lower"])
@pytest.mark.parametrize("field", ["id", "previous"])
def test_migration_rejects_reused_uuid_independent_of_source_case(
    upgrade, kind, case, field, monkeypatch
):
    from rangekeeper.model import Model
    from rangekeeper.specification import Specification

    metadata = {
        "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "previous": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "schema_version": "0.6.0",
    }
    if case == "upper":
        metadata[field] = metadata[field].upper()
    elif case == "mixed":
        metadata[field] = "".join(
            c.upper() if index % 2 else c for index, c in enumerate(metadata[field])
        )
    source = {"metadata": metadata}
    before = deepcopy(source)

    def forbidden(*args, **kwargs):
        raise AssertionError("reused source UUID reached the target facade")

    monkeypatch.setattr(
        Model if kind == "Model" else Specification, "from_data", forbidden
    )
    with pytest.raises(ValueError, match="upgrade requires a new revision UUID"):
        upgrade(source, revision_id=UUID(metadata[field]))
    assert source == before


@pytest.mark.parametrize("upgrade", [upgrade_model, upgrade_specification])
def test_migration_accepts_fresh_uuid_and_canonicalizes_mixed_case_lineage(upgrade):
    source = {
        "metadata": {
            "id": "bBbBbBbB-bBbB-4BbB-8bBb-bBbBbBbBbBbB",
            "previous": "AaAaAaAa-aAaA-4aAa-8AaA-aAaAaAaAaAaA",
            "schema_version": "0.6.0",
        }
    }
    before = deepcopy(source)
    fresh = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    result = upgrade(source, revision_id=fresh)
    assert result.id == fresh
    assert result.metadata.previous == UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    assert result.metadata.to_data()["id"] == str(fresh)
    assert (
        result.metadata.to_data()["previous"] == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    )
    assert source == before


@pytest.mark.parametrize("upgrade", [upgrade_model, upgrade_specification])
@pytest.mark.parametrize("field", ["id", "previous"])
@pytest.mark.parametrize(
    "malformed", ["not-a-uuid", 123, "a" * 32, "{AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA}"]
)
def test_migration_preserves_the_strict_source_uuid_boundary(upgrade, field, malformed):
    from rangekeeper.errors import ValidationError

    source = {
        "metadata": {
            "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "schema_version": "0.6.0",
            field: malformed,
        }
    }
    before = deepcopy(source)
    with pytest.raises(ValidationError):
        upgrade(source, revision_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"))
    assert source == before
