"""Stores and codecs trust validated facades; data input is always validated."""

from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.io import DirectoryStore, MemoryStore
from rangekeeper.io import json as codec
from rangekeeper.model import Entity, Metadata, System
from rangekeeper.model import validation as model_validation
from rangekeeper.schema import validation


@pytest.fixture
def model():
    return rk.Model.create(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        system=System(entities=(Entity(id=uuid4(), code="A"),)),
    )


@pytest.fixture
def counted(monkeypatch):
    """Count structural and semantic validations."""
    calls: list[str] = []
    structural, semantic = validation._validate_json, model_validation._validate

    def count_structural(kind, data):
        calls.append(f"structure:{kind}")
        return structural(kind, data)

    def count_semantic(*args, **kwargs):
        calls.append("semantic:Model")
        return semantic(*args, **kwargs)

    monkeypatch.setattr(validation, "_validate_json", count_structural)
    monkeypatch.setattr(model_validation, "_validate", count_semantic)
    return calls


def test_put_and_dumps_do_not_validate_a_facade_again(model, counted, tmp_path):
    memory = MemoryStore()
    memory.put(model)
    memory.put(model)
    DirectoryStore(tmp_path / "records").put(model)
    text = codec.dumps(model)
    assert counted == []
    # A second put to a directory reads the stored file, which is untrusted.
    DirectoryStore(tmp_path / "records").put(model)
    assert counted == ["structure:Model", "semantic:Model"]
    counted.clear()
    assert codec.loads(text=text, kind=rk.Model).to_data() == model.to_data()
    assert "structure:Model" in counted and "semantic:Model" in counted


def test_a_memory_store_returns_the_validated_instance(model):
    store = MemoryStore()
    store.put(model)
    assert store.load_model(model.id) is model


def test_only_exact_facades_are_trusted(model):
    class Derived(rk.Model):
        pass

    derived = object.__new__(Derived)
    with pytest.raises(TypeError, match="kind must be"):
        MemoryStore().put(derived)
    with pytest.raises(TypeError, match="kind must be"):
        codec.dumps(model._record)  # type: ignore[arg-type]
