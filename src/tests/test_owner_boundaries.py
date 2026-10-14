"""Current public contracts do not need either Whirlwind package."""
import importlib.util
import subprocess
import sys
from uuid import uuid4
import pytest
from rangekeeper.model import Model, Metadata, Entity, System, Update
from rangekeeper.io.speckle import encode_model, decode_model, MappingError
from .test_model_graph import fixture
from rangekeeper.model.system import View

def test_current_envelope_and_associations_bind_revision():
    entity = Entity(id=uuid4(), name="Current")
    model = Model.create(metadata=Metadata(id=uuid4(), schema_version="0.7.0"), system=System(entities=(entity,)))
    associations = [{"model_revision":str(model.id),"domain_id":str(entity.id),"content_id":"retained"}]
    encoded = encode_model(model, associations=associations)
    assert decode_model(encoded).to_data() == model.to_data()
    revised = model.revise(Update(system=System(entities=(Entity(id=entity.id,name="Changed"),))))
    with pytest.raises(MappingError, match="revision"):
        encode_model(revised, associations=associations)

def test_quantity_population_preserves_zero_missing_and_scope():
    model, root, a, b, c, *_ = fixture(missing=True)
    population = View(model, entities=(a.id,b.id,c.id)).quantities("net", units="meter ** 2")
    assert any(q.magnitude == 0 for q in population.quantities)
    assert population.coverage.missing
    assert set(population.coverage.selected) == {a.id,b.id,c.id}
    assert root.id not in population.coverage.selected
    with pytest.raises(TypeError):
        population.value_ids[a.id] = uuid4()

def test_core_imports_do_not_load_other_owners_or_display_dependencies():
    subprocess.run([sys.executable,"-c", "import sys; import rangekeeper; from rangekeeper.io import speckle; assert not any(n.split('.')[0] in {'whirlwind_mcp','whirlwind_viewer','matplotlib','plotly','specklepy','openpyxl'} for n in sys.modules)"], check=True)
