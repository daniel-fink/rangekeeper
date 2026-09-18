"""Shared contracts and bounded document navigation."""

from dataclasses import FrozenInstanceError
from types import MappingProxyType
from uuid import NAMESPACE_URL, uuid5

import pytest

from rangekeeper.graph.adapter import document, operation
from rangekeeper.graph.adapter.document import (
    ContentItem,
    Description,
    Document,
    Inspection,
)
from rangekeeper.graph.adapter.errors import AdapterEncodingError
from rangekeeper.graph.adapter.ingestion import IssueSeverity
from rangekeeper.graph.provenance import Location, Method, Source


def invocation(spec=None, **kwargs):
    return operation.Operation(
        method=kwargs.get("method", Method(code="test", version="1")),
        specification={} if spec is None else spec,
        inputs=kwargs.get("inputs", {"source": "sha256:example"}),
    )


def test_nested_normalization_and_independent_copies():
    supplied = {"columns": [{"name": "unit"}], "options": {"flag": True}}
    result = invocation(supplied)
    diagnostic = operation.Diagnostic(
        code="layout",
        severity=IssueSeverity.ERROR,
        message="Changed",
        details=supplied,
    )
    supplied["columns"][0]["name"] = "changed"
    supplied["options"]["flag"] = False
    assert result.specification["columns"][0]["name"] == "unit"
    assert diagnostic.details["options"]["flag"] is True
    assert isinstance(result.specification, MappingProxyType)
    with pytest.raises(TypeError):
        result.specification["columns"][0]["name"] = "changed"
    with pytest.raises(FrozenInstanceError):
        result.method = Method(code="changed", version="1")


@pytest.mark.parametrize(
    "value", [object(), lambda: None, float("nan"), float("inf"), {1: "x"}]
)
def test_reject_unsupported_specification_values(value):
    with pytest.raises(AdapterEncodingError):
        invocation({"value": value})


def test_cycles_rejected_and_shared_containers_allowed():
    cyclic = []
    cyclic.append(cyclic)
    with pytest.raises(AdapterEncodingError, match="Cyclic"):
        invocation({"value": cyclic})
    shared = [1]
    assert invocation({"a": shared, "b": shared}).specification["a"] == (1,)


def test_fingerprint_type_and_order_semantics():
    fp = operation.fingerprint
    assert fp(invocation({"a": 1, "b": 2})) == fp(invocation({"b": 2, "a": 1}))
    assert fp(invocation({"a": [1, 2]})) == fp(invocation({"a": (1, 2)}))
    assert fp(invocation({"a": [1, 2]})) != fp(invocation({"a": [2, 1]}))
    assert len({fp(invocation({"value": v})) for v in [1, 1.0, True, "1"]}) == 4
    assert fp(invocation()) != fp(invocation(method=Method(code="test", version="2")))
    assert fp(invocation()) != fp(invocation(inputs={"source": None}))
    assert fp(invocation()) == fp(
        invocation(method=Method(code="test", version="1", description="Other prose"))
    )


def test_outcomes_and_method_version():
    with pytest.raises(ValueError):
        invocation(method=Method(code="test"))
    with pytest.raises(ValueError, match="diagnostic"):
        operation.Outcome(operation=invocation(), output=None)
    diagnostic = operation.Diagnostic(
        code="missing", severity=IssueSeverity.INFO, message="Missing"
    )
    assert (
        operation.Outcome(
            operation=invocation(), output=None, diagnostics=(diagnostic,)
        ).output
        is None
    )
    assert operation.Outcome(operation=invocation(), output=()).output == ()
    # Severity does not decide availability, even for an error-labelled diagnostic.
    diagnostic = operation.Diagnostic(
        code="qualified", severity=IssueSeverity.ERROR, message="Qualified"
    )
    assert (
        operation.Outcome(
            operation=invocation(), output=0, diagnostics=(diagnostic,)
        ).output
        == 0
    )


class SampleDocument(Document):
    """Non-Excel inspection backend fixture; not a production content adapter."""

    def __init__(self, key="edition"):
        self.source = Source(id=uuid5(NAMESPACE_URL, key), name="Sample", checksum=key)

    @property
    def fingerprint(self):
        return self.source.checksum

    @property
    def format(self):
        return "sample"

    @property
    def capabilities(self):
        return ("describe", "children", "inspect", "search")

    def _describe(self):
        return Description(
            source=self.source,
            format=self.format,
            capabilities=self.capabilities,
            metadata={"count": 4},
        )

    def _children(self, location):
        for index in range(4):
            yield ContentItem(
                location=Location(source=self.source, reference={"item": str(index)}),
                kind="item",
                label=f"Item {index}",
            )

    def _search(self, query, case_sensitive):
        for item in self._children(Location(source=self.source)):
            haystack, needle = (
                (item.label, query)
                if case_sensitive
                else (item.label.casefold(), query.casefold())
            )
            if needle in haystack:
                yield item

    def _inspect(self, location):
        return Inspection(
            location=location,
            kind="item",
            content=("native", location.reference.get("item")),
        )


def test_inspection_and_pagination_are_recorded():
    source = SampleDocument()
    first = document.children(source, limit=2)
    assert first.operation.method.code == "rk.document.children"
    assert len(first.output.items) == 2
    second = document.children(source, limit=2, cursor=first.output.next_cursor)
    assert [item.label for item in second.output.items] == ["Item 2", "Item 3"]
    assert second.output.next_cursor is None
    assert document.describe(source).output.metadata["count"] == 4
    assert document.inspect(source, first.output.items[0].location).output.content == (
        "native",
        "0",
    )


def test_cursor_snapshot_query_binding_and_empty_search():
    source = SampleDocument()
    first = document.search(source, "Item", limit=1)
    assert document.search(source, "missing").output.items == ()
    assert document.search(source, "item").output.items == ()
    assert len(document.search(source, "item", case_sensitive=False).output.items) == 4
    for outcome in (
        document.search(source, "different", cursor=first.output.next_cursor),
        document.search(SampleDocument("new"), "Item", cursor=first.output.next_cursor),
        document.children(source, cursor=first.output.next_cursor),
    ):
        assert outcome.output is None
        assert outcome.diagnostics[0].code == "cursor_mismatch"
    with pytest.raises(ValueError):
        document.children(source, cursor="malformed")


@pytest.mark.parametrize("limit", [0, 501, True, "50"])
def test_bad_limits_are_api_errors(limit):
    with pytest.raises(ValueError):
        document.children(SampleDocument(), limit=limit)


def test_foreign_location_and_unsupported_capability():
    source = SampleDocument()
    outcome = document.inspect(source, Location(source=SampleDocument("other").source))
    assert outcome.diagnostics[0].code == "source_mismatch"

    class DescriptionOnly(SampleDocument):
        @property
        def capabilities(self):
            return ("describe",)

    outcome = document.search(DescriptionOnly(), "Item")
    assert outcome.output is None
    assert outcome.diagnostics[0].code == "unsupported_capability"
    assert outcome.diagnostics[0].details["capability"] == "search"


def test_unexpected_backend_failure_is_not_a_diagnostic():
    class Broken(SampleDocument):
        def _describe(self):
            raise RuntimeError("bug")

    with pytest.raises(RuntimeError, match="bug"):
        document.describe(Broken())
