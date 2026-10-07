"""Independent arithmetic for the complete design teaching model."""

from rangekeeper.run import SolutionStatus

from uuid import uuid5
import pytest
from rangekeeper.examples import design
from rangekeeper.execution import Executor
from rangekeeper.io.memory import MemoryStore
from rangekeeper.model import Update, System


def test_design_financial_components_and_provenance():
    source = design.fixture()
    root = source.find_entities(
        classification=design.classification_id(source, "property")
    )[0].id
    selected = design.select_contributors(source, root=root)
    utilities = {uid: "cores" for uid in selected if source.entity(uid).name == "cores"}
    authored = design.author(
        source, root=root, utility_kinds=utilities, contributors=(*selected, *selected)
    )
    model = design.formulate(authored)
    store = MemoryStore()
    store.put(model)
    run = Executor(store).execute(design.specify(model))
    assert run.report.status.solution == SolutionStatus.FEASIBLE, run.report
    output = store.load_model(run.record.outputs[0])
    v = design.values(output)
    assert output.provenance.sources == source.provenance.sources
    assert {c.id for c in source.provenance.claims} <= {
        c.id for c in output.provenance.claims
    }
    expected = {name: [] for name in design._COMPONENTS}
    for i in range(11):
        pgi = 1000 * 0.8 * 750 * 1.035**i
        vacancy = -pgi * 0.025
        floor_opex = -175 * 1000 * 1.035**i
        facade_opex = -50 * 120 * 3 * 1.035**i
        floor_capex = (
            -100 * 1000 * 1.035 ** ((i + 1) // 5 - 1) if (i + 1) % 5 == 0 else 0
        )
        utility_capex = (
            -100 * 20 * 1.035 ** ((i + 1) // 5 - 1) if (i + 1) % 5 == 0 else 0
        )
        row = dict(
            pgi=pgi,
            vacancy=vacancy,
            egi=pgi + vacancy,
            floor_opex=floor_opex,
            facade_opex=facade_opex,
            opex=floor_opex + facade_opex,
            floor_capex=floor_capex,
            utility_capex=utility_capex,
            capex=floor_capex + utility_capex,
            noi=pgi + vacancy + floor_opex + facade_opex,
            nacf=pgi + vacancy + floor_opex + facade_opex + floor_capex + utility_capex,
        )
        for key, amount in row.items():
            expected[key].append(amount)
    for key, amounts in expected.items():
        assert [m.magnitude for m in v[key].flow.movements] == pytest.approx(amounts)
    reversion = expected["nacf"][10] / 0.05
    total = expected["nacf"][:10]
    total[-1] += reversion
    assert [m.magnitude for m in v["total"].flow.movements] == pytest.approx(total)
    assert v["pv"].quantity.magnitude == pytest.approx(
        sum(x / 1.07 ** (i + 1) for i, x in enumerate(total))
    )
    assert [m.magnitude for m in v["reversion"].flow.movements] == pytest.approx(
        [0] * 9 + [reversion]
    )
    assert [m.date.year for m in v["capex"].flow.movements if m.magnitude] == [
        2005,
        2010,
    ]


def test_shared_spatial_paths_do_not_duplicate_contributors():
    model = design.fixture()
    root = model.find_entities(
        classification=design.classification_id(model, "property")
    )[0].id
    selected = design.select_contributors(model, root=root)
    floor = next(uid for uid in selected if model.entity(uid).name == "floor")
    data = model.system.to_data()
    data["relationships"].append(
        {
            "id": str(uuid5(root, "shared")),
            "source": str(root),
            "target": str(floor),
            "classification": str(design.classification_id(model, "spatiallyContains")),
        }
    )
    shared = model.revise(Update(system=System.from_data(data)))
    assert design.select_contributors(shared, root=root) == selected
    with pytest.raises(ValueError, match="utility"):
        design.author(shared, root=root, utility_kinds={})
