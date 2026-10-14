from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping
from uuid import UUID
from typing import Any

class Unset:
    __slots__ = ()
UNSET = Unset()
def freeze(value):
    if isinstance(value, Record): return value._data
    if isinstance(value, UUID): return str(value)
    if isinstance(value, Mapping): return MappingProxyType({k:freeze(v) for k,v in value.items()})
    if isinstance(value, (list,tuple)): return tuple(freeze(v) for v in value)
    return value

def thaw(value):
    if isinstance(value, Mapping): return {k:thaw(v) for k,v in value.items()}
    if isinstance(value, tuple): return [thaw(v) for v in value]
    return value

@dataclass(frozen=True, slots=True, init=False)
class Record:
    _data: Mapping[str, Any]
    @classmethod
    def from_data(cls, data):
        value = object.__new__(cls)
        object.__setattr__(value, '_data', freeze(data))
        return value
    def to_data(self): return thaw(self._data)
    def _get(self, key, kind, many, inline):
        value = self._data.get(key)
        if value is None: return () if many and key not in self._data else None
        def cast(item):
            if item is None: return None
            if kind in OPAQUE: return item
            if kind == 'UUID' or (kind in RECORDS and not inline): return UUID(item)
            if kind in RECORDS and isinstance(item, Mapping): return RECORDS[kind].from_data(item)
            return item
        return tuple(cast(i) for i in value) if many else cast(value)

OPAQUE = {'Content'}

class Argument(Record):
    __slots__ = ()
    def __init__(self, *, name: str | None | Unset = UNSET, expression: Expression | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def name(self) -> str | None:
        return self._get('name', 'Code', False, False)
    @property
    def expression(self) -> Expression | None:
        return self._get('expression', 'Expression', False, True)

class Assembly(Record):
    __slots__ = ()
    def __init__(self, *, entities: tuple[UUID, ...] | None | Unset = UNSET, relationships: tuple[UUID, ...] | None | Unset = UNSET, classification: UUID | None | Unset = UNSET, id: UUID | None | Unset = UNSET, code: str | None | Unset = UNSET, name: str | None | Unset = UNSET, characteristics: Characteristics | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def entities(self) -> tuple[UUID, ...] | None:
        return self._get('entities', 'Entity', True, False)
    @property
    def relationships(self) -> tuple[UUID, ...] | None:
        return self._get('relationships', 'Relationship', True, False)
    @property
    def classification(self) -> UUID | None:
        return self._get('classification', 'Classification', False, False)
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def code(self) -> str | None:
        return self._get('code', 'Code', False, False)
    @property
    def name(self) -> str | None:
        return self._get('name', 'string', False, False)
    @property
    def characteristics(self) -> Characteristics | None:
        return self._get('characteristics', 'Characteristics', False, True)

class Assignment(Record):
    __slots__ = ()
    def __init__(self, *, value: UUID | None | Unset = UNSET, quantity: Quantity | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def value(self) -> UUID | None:
        return self._get('value', 'Value', False, False)
    @property
    def quantity(self) -> Quantity | None:
        return self._get('quantity', 'Quantity', False, True)

class Binding(Record):
    __slots__ = ()
    def __init__(self, *, name: str | None | Unset = UNSET, value: UUID | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def name(self) -> str | None:
        return self._get('name', 'Code', False, False)
    @property
    def value(self) -> UUID | None:
        return self._get('value', 'Value', False, False)

class Call(Record):
    __slots__ = ()
    def __init__(self, *, function: UUID | None | Unset = UNSET, arguments: tuple[Expression, ...] | None | Unset = UNSET, named_arguments: tuple[Argument, ...] | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def function(self) -> UUID | None:
        return self._get('function', 'Function', False, False)
    @property
    def arguments(self) -> tuple[Expression, ...] | None:
        return self._get('arguments', 'Expression', True, True)
    @property
    def named_arguments(self) -> tuple[Argument, ...] | None:
        return self._get('named_arguments', 'Argument', True, True)

class Characteristics(Record):
    __slots__ = ()
    def __init__(self, *, labels: tuple[Label, ...] | None | Unset = UNSET, values: tuple[Value, ...] | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def labels(self) -> tuple[Label, ...] | None:
        return self._get('labels', 'Label', True, True)
    @property
    def values(self) -> tuple[Value, ...] | None:
        return self._get('values', 'Value', True, True)

class Claim(Record):
    __slots__ = ()
    def __init__(self, *, id: UUID | None | Unset = UNSET, content: Content | None | Unset = UNSET, kind: Any | None | Unset = UNSET, sources: tuple[UUID, ...] | None | Unset = UNSET, method: Method | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def content(self) -> Content | None:
        return self._get('content', 'Content', False, True)
    @property
    def kind(self) -> Any | None:
        return self._get('kind', 'ClaimKind', False, False)
    @property
    def sources(self) -> tuple[UUID, ...] | None:
        return self._get('sources', 'Content', True, False)
    @property
    def method(self) -> Method | None:
        return self._get('method', 'Method', False, True)

class Classification(Record):
    __slots__ = ()
    def __init__(self, *, id: UUID | None | Unset = UNSET, code: str | None | Unset = UNSET, name: str | None | Unset = UNSET, definition: str | None | Unset = UNSET, parent: UUID | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def code(self) -> str | None:
        return self._get('code', 'Code', False, False)
    @property
    def name(self) -> str | None:
        return self._get('name', 'string', False, False)
    @property
    def definition(self) -> str | None:
        return self._get('definition', 'string', False, False)
    @property
    def parent(self) -> UUID | None:
        return self._get('parent', 'Classification', False, False)

class Constraint(Record):
    __slots__ = ()
    def __init__(self, *, id: UUID | None | Unset = UNSET, code: str | None | Unset = UNSET, name: str | None | Unset = UNSET, description: str | None | Unset = UNSET, predicate: UUID | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def code(self) -> str | None:
        return self._get('code', 'Code', False, False)
    @property
    def name(self) -> str | None:
        return self._get('name', 'string', False, False)
    @property
    def description(self) -> str | None:
        return self._get('description', 'string', False, False)
    @property
    def predicate(self) -> UUID | None:
        return self._get('predicate', 'Expression', False, False)

class Content(Record):
    __slots__ = ()
    pass

class Criterion(Record):
    __slots__ = ()
    def __init__(self, *, key: str | None | Unset = UNSET, classification: UUID | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def key(self) -> str | None:
        return self._get('key', 'string', False, False)
    @property
    def classification(self) -> UUID | None:
        return self._get('classification', 'Classification', False, False)

class Definitions(Record):
    __slots__ = ()
    def __init__(self, *, taxonomies: tuple[Taxonomy, ...] | None | Unset = UNSET, measures: tuple[Measure, ...] | None | Unset = UNSET, functions: tuple[Function, ...] | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def taxonomies(self) -> tuple[Taxonomy, ...] | None:
        return self._get('taxonomies', 'Taxonomy', True, True)
    @property
    def measures(self) -> tuple[Measure, ...] | None:
        return self._get('measures', 'Measure', True, True)
    @property
    def functions(self) -> tuple[Function, ...] | None:
        return self._get('functions', 'Function', True, True)

class Diagnostic(Record):
    __slots__ = ()
    def __init__(self, *, severity: Any | None | Unset = UNSET, code: str | None | Unset = UNSET, message: str | None | Unset = UNSET, document: UUID | None | Unset = UNSET, target: UUID | None | Unset = UNSET, residual: Quantity | None | Unset = UNSET, tolerance: Quantity | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def severity(self) -> Any | None:
        return self._get('severity', 'Severity', False, False)
    @property
    def code(self) -> str | None:
        return self._get('code', 'Code', False, False)
    @property
    def message(self) -> str | None:
        return self._get('message', 'string', False, False)
    @property
    def document(self) -> UUID | None:
        return self._get('document', 'Metadata', False, False)
    @property
    def target(self) -> UUID | None:
        return self._get('target', 'UUID', False, False)
    @property
    def residual(self) -> Quantity | None:
        return self._get('residual', 'Quantity', False, True)
    @property
    def tolerance(self) -> Quantity | None:
        return self._get('tolerance', 'Quantity', False, True)

class Domain(Record):
    __slots__ = ()
    def __init__(self, *, kind: Any | None | Unset = UNSET, units: str | None | Unset = UNSET, measure: UUID | None | Unset = UNSET, item_domain: Domain | None | Unset = UNSET, collection_kind: Any | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def kind(self) -> Any | None:
        return self._get('kind', 'DomainKind', False, False)
    @property
    def units(self) -> str | None:
        return self._get('units', 'string', False, False)
    @property
    def measure(self) -> UUID | None:
        return self._get('measure', 'Measure', False, False)
    @property
    def item_domain(self) -> Domain | None:
        return self._get('item_domain', 'Domain', False, True)
    @property
    def collection_kind(self) -> Any | None:
        return self._get('collection_kind', 'CollectionKind', False, False)

class Entity(Record):
    __slots__ = ()
    def __init__(self, *, classification: UUID | None | Unset = UNSET, id: UUID | None | Unset = UNSET, code: str | None | Unset = UNSET, name: str | None | Unset = UNSET, characteristics: Characteristics | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def classification(self) -> UUID | None:
        return self._get('classification', 'Classification', False, False)
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def code(self) -> str | None:
        return self._get('code', 'Code', False, False)
    @property
    def name(self) -> str | None:
        return self._get('name', 'string', False, False)
    @property
    def characteristics(self) -> Characteristics | None:
        return self._get('characteristics', 'Characteristics', False, True)

class Entry(Record):
    __slots__ = ()
    def __init__(self, *, key: str | None | Unset = UNSET, value: str | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def key(self) -> str | None:
        return self._get('key', 'string', False, False)
    @property
    def value(self) -> str | None:
        return self._get('value', 'string', False, False)

class Expression(Record):
    __slots__ = ()
    def __init__(self, *, id: UUID | None | Unset = UNSET, kind: Any | None | Unset = UNSET, quantity: Quantity | None | Unset = UNSET, boolean: bool | None | Unset = UNSET, target: UUID | None | Unset = UNSET, operator: Any | None | Unset = UNSET, operands: tuple[Expression, ...] | None | Unset = UNSET, operand: Expression | None | Unset = UNSET, call: Call | None | Unset = UNSET, selection: Selection | None | Unset = UNSET, query: Query | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def kind(self) -> Any | None:
        return self._get('kind', 'ExpressionKind', False, False)
    @property
    def quantity(self) -> Quantity | None:
        return self._get('quantity', 'Quantity', False, True)
    @property
    def boolean(self) -> bool | None:
        return self._get('boolean', 'boolean', False, False)
    @property
    def target(self) -> UUID | None:
        return self._get('target', 'Value', False, False)
    @property
    def operator(self) -> Any | None:
        return self._get('operator', 'Operator', False, False)
    @property
    def operands(self) -> tuple[Expression, ...] | None:
        return self._get('operands', 'Expression', True, True)
    @property
    def operand(self) -> Expression | None:
        return self._get('operand', 'Expression', False, True)
    @property
    def call(self) -> Call | None:
        return self._get('call', 'Call', False, True)
    @property
    def selection(self) -> Selection | None:
        return self._get('selection', 'Selection', False, True)
    @property
    def query(self) -> Query | None:
        return self._get('query', 'Query', False, True)

class Fact(Record):
    __slots__ = ()
    def __init__(self, *, target: UUID | None | Unset = UNSET, claims: tuple[UUID, ...] | None | Unset = UNSET, reconciliation: Reconciliation | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def target(self) -> UUID | None:
        return self._get('target', 'Content', False, False)
    @property
    def claims(self) -> tuple[UUID, ...] | None:
        return self._get('claims', 'Claim', True, False)
    @property
    def reconciliation(self) -> Reconciliation | None:
        return self._get('reconciliation', 'Reconciliation', False, True)

class Filter(Record):
    __slots__ = ()
    def __init__(self, *, classification: UUID | None | Unset = UNSET, labels: tuple[Criterion, ...] | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def classification(self) -> UUID | None:
        return self._get('classification', 'Classification', False, False)
    @property
    def labels(self) -> tuple[Criterion, ...] | None:
        return self._get('labels', 'Criterion', True, True)

class Formulation(Record):
    __slots__ = ()
    def __init__(self, *, id: UUID | None | Unset = UNSET, code: str | None | Unset = UNSET, name: str | None | Unset = UNSET, description: str | None | Unset = UNSET, bindings: tuple[Binding, ...] | None | Unset = UNSET, values: tuple[Value, ...] | None | Unset = UNSET, expressions: tuple[Expression, ...] | None | Unset = UNSET, constraints: tuple[Constraint, ...] | None | Unset = UNSET, formulations: tuple[Formulation, ...] | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def code(self) -> str | None:
        return self._get('code', 'Code', False, False)
    @property
    def name(self) -> str | None:
        return self._get('name', 'string', False, False)
    @property
    def description(self) -> str | None:
        return self._get('description', 'string', False, False)
    @property
    def bindings(self) -> tuple[Binding, ...] | None:
        return self._get('bindings', 'Binding', True, True)
    @property
    def values(self) -> tuple[Value, ...] | None:
        return self._get('values', 'Value', True, True)
    @property
    def expressions(self) -> tuple[Expression, ...] | None:
        return self._get('expressions', 'Expression', True, True)
    @property
    def constraints(self) -> tuple[Constraint, ...] | None:
        return self._get('constraints', 'Constraint', True, True)
    @property
    def formulations(self) -> tuple[Formulation, ...] | None:
        return self._get('formulations', 'Formulation', True, True)

class Function(Record):
    __slots__ = ()
    def __init__(self, *, id: UUID | None | Unset = UNSET, code: str | None | Unset = UNSET, name: str | None | Unset = UNSET, version: str | None | Unset = UNSET, parameters: tuple[Parameter, ...] | None | Unset = UNSET, result: Domain | None | Unset = UNSET, semantics: str | None | Unset = UNSET, unit_rule: str | None | Unset = UNSET, empty_collection: Any | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def code(self) -> str | None:
        return self._get('code', 'Code', False, False)
    @property
    def name(self) -> str | None:
        return self._get('name', 'string', False, False)
    @property
    def version(self) -> str | None:
        return self._get('version', 'Code', False, False)
    @property
    def parameters(self) -> tuple[Parameter, ...] | None:
        return self._get('parameters', 'Parameter', True, True)
    @property
    def result(self) -> Domain | None:
        return self._get('result', 'Domain', False, True)
    @property
    def semantics(self) -> str | None:
        return self._get('semantics', 'string', False, False)
    @property
    def unit_rule(self) -> str | None:
        return self._get('unit_rule', 'string', False, False)
    @property
    def empty_collection(self) -> Any | None:
        return self._get('empty_collection', 'EmptyHandling', False, False)

class Implementation(Record):
    __slots__ = ()
    def __init__(self, *, kind: Any | None | Unset = UNSET, name: str | None | Unset = UNSET, version: str | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def kind(self) -> Any | None:
        return self._get('kind', 'ImplementationKind', False, False)
    @property
    def name(self) -> str | None:
        return self._get('name', 'string', False, False)
    @property
    def version(self) -> str | None:
        return self._get('version', 'string', False, False)

class Label(Record):
    __slots__ = ()
    def __init__(self, *, id: UUID | None | Unset = UNSET, key: str | None | Unset = UNSET, classifications: tuple[UUID, ...] | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def key(self) -> str | None:
        return self._get('key', 'string', False, False)
    @property
    def classifications(self) -> tuple[UUID, ...] | None:
        return self._get('classifications', 'Classification', True, False)

class Location(Record):
    __slots__ = ()
    def __init__(self, *, source: UUID | None | Unset = UNSET, address: tuple[Entry, ...] | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def source(self) -> UUID | None:
        return self._get('source', 'Source', False, False)
    @property
    def address(self) -> tuple[Entry, ...] | None:
        return self._get('address', 'Entry', True, True)

class Measure(Record):
    __slots__ = ()
    def __init__(self, *, id: UUID | None | Unset = UNSET, code: str | None | Unset = UNSET, name: str | None | Unset = UNSET, units: str | None | Unset = UNSET, definition: str | None | Unset = UNSET, tags: tuple[str, ...] | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def code(self) -> str | None:
        return self._get('code', 'Code', False, False)
    @property
    def name(self) -> str | None:
        return self._get('name', 'string', False, False)
    @property
    def units(self) -> str | None:
        return self._get('units', 'string', False, False)
    @property
    def definition(self) -> str | None:
        return self._get('definition', 'string', False, False)
    @property
    def tags(self) -> tuple[str, ...] | None:
        return self._get('tags', 'string', True, False)

class Measurement(Record):
    __slots__ = ()
    def __init__(self, *, measure: UUID | None | Unset = UNSET, quantity: Quantity | None | Unset = UNSET, id: UUID | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def measure(self) -> UUID | None:
        return self._get('measure', 'Measure', False, False)
    @property
    def quantity(self) -> Quantity | None:
        return self._get('quantity', 'Quantity', False, True)
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)

class Metadata(Record):
    __slots__ = ()
    def __init__(self, *, id: UUID | None | Unset = UNSET, schema_version: str | None | Unset = UNSET, name: str | None | Unset = UNSET, description: str | None | Unset = UNSET, previous: UUID | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def schema_version(self) -> str | None:
        return self._get('schema_version', 'Code', False, False)
    @property
    def name(self) -> str | None:
        return self._get('name', 'string', False, False)
    @property
    def description(self) -> str | None:
        return self._get('description', 'string', False, False)
    @property
    def previous(self) -> UUID | None:
        return self._get('previous', 'Metadata', False, False)

class Method(Record):
    __slots__ = ()
    def __init__(self, *, code: str | None | Unset = UNSET, version: str | None | Unset = UNSET, description: str | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def code(self) -> str | None:
        return self._get('code', 'string', False, False)
    @property
    def version(self) -> str | None:
        return self._get('version', 'string', False, False)
    @property
    def description(self) -> str | None:
        return self._get('description', 'string', False, False)

class Model(Record):
    __slots__ = ()
    def __init__(self, *, metadata: Metadata | None | Unset = UNSET, definitions: Definitions | None | Unset = UNSET, system: System | None | Unset = UNSET, provenance: Provenance | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def metadata(self) -> Metadata | None:
        return self._get('metadata', 'Metadata', False, True)
    @property
    def definitions(self) -> Definitions | None:
        return self._get('definitions', 'Definitions', False, True)
    @property
    def system(self) -> System | None:
        return self._get('system', 'System', False, True)
    @property
    def provenance(self) -> Provenance | None:
        return self._get('provenance', 'Provenance', False, True)

class Objective(Record):
    __slots__ = ()
    def __init__(self, *, expression: UUID | None | Unset = UNSET, sense: Any | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def expression(self) -> UUID | None:
        return self._get('expression', 'Expression', False, False)
    @property
    def sense(self) -> Any | None:
        return self._get('sense', 'ObjectiveKind', False, False)

class Parameter(Record):
    __slots__ = ()
    def __init__(self, *, name: str | None | Unset = UNSET, domain: Domain | None | Unset = UNSET, kind: Any | None | Unset = UNSET, required: bool | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def name(self) -> str | None:
        return self._get('name', 'Code', False, False)
    @property
    def domain(self) -> Domain | None:
        return self._get('domain', 'Domain', False, True)
    @property
    def kind(self) -> Any | None:
        return self._get('kind', 'ParameterKind', False, False)
    @property
    def required(self) -> bool | None:
        return self._get('required', 'boolean', False, False)

class Projection(Record):
    __slots__ = ()
    def __init__(self, *, kind: Any | None | Unset = UNSET, key: str | None | Unset = UNSET, measure: UUID | None | Unset = UNSET, cardinality: Any | None | Unset = UNSET, missing: Any | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def kind(self) -> Any | None:
        return self._get('kind', 'ProjectionKind', False, False)
    @property
    def key(self) -> str | None:
        return self._get('key', 'string', False, False)
    @property
    def measure(self) -> UUID | None:
        return self._get('measure', 'Measure', False, False)
    @property
    def cardinality(self) -> Any | None:
        return self._get('cardinality', 'Cardinality', False, False)
    @property
    def missing(self) -> Any | None:
        return self._get('missing', 'MissingHandling', False, False)

class Provenance(Record):
    __slots__ = ()
    def __init__(self, *, sources: tuple[Source, ...] | None | Unset = UNSET, claims: tuple[Claim, ...] | None | Unset = UNSET, facts: tuple[Fact, ...] | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def sources(self) -> tuple[Source, ...] | None:
        return self._get('sources', 'Source', True, True)
    @property
    def claims(self) -> tuple[Claim, ...] | None:
        return self._get('claims', 'Claim', True, True)
    @property
    def facts(self) -> tuple[Fact, ...] | None:
        return self._get('facts', 'Fact', True, True)

class Quantity(Record):
    __slots__ = ()
    def __init__(self, *, magnitude: float | None | Unset = UNSET, units: str | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def magnitude(self) -> float | None:
        return self._get('magnitude', 'decimal', False, False)
    @property
    def units(self) -> str | None:
        return self._get('units', 'string', False, False)

class Query(Record):
    __slots__ = ()
    def __init__(self, *, starting_at: UUID | None | Unset = UNSET, steps: tuple[Traversal, ...] | None | Unset = UNSET, filter: Filter | None | Unset = UNSET, projection: Projection | None | Unset = UNSET, duplicates: Any | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def starting_at(self) -> UUID | None:
        return self._get('starting_at', 'Entity', False, False)
    @property
    def steps(self) -> tuple[Traversal, ...] | None:
        return self._get('steps', 'Traversal', True, True)
    @property
    def filter(self) -> Filter | None:
        return self._get('filter', 'Filter', False, True)
    @property
    def projection(self) -> Projection | None:
        return self._get('projection', 'Projection', False, True)
    @property
    def duplicates(self) -> Any | None:
        return self._get('duplicates', 'DuplicateHandling', False, False)

class Reconciliation(Record):
    __slots__ = ()
    def __init__(self, *, selected: UUID | None | Unset = UNSET, status: Any | None | Unset = UNSET, method: Method | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def selected(self) -> UUID | None:
        return self._get('selected', 'Claim', False, False)
    @property
    def status(self) -> Any | None:
        return self._get('status', 'ReconciliationStatus', False, False)
    @property
    def method(self) -> Method | None:
        return self._get('method', 'Method', False, True)

class Relationship(Record):
    __slots__ = ()
    def __init__(self, *, classification: UUID | None | Unset = UNSET, id: UUID | None | Unset = UNSET, source: UUID | None | Unset = UNSET, target: UUID | None | Unset = UNSET, characteristics: Characteristics | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def classification(self) -> UUID | None:
        return self._get('classification', 'Classification', False, False)
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def source(self) -> UUID | None:
        return self._get('source', 'Entity', False, False)
    @property
    def target(self) -> UUID | None:
        return self._get('target', 'Entity', False, False)
    @property
    def characteristics(self) -> Characteristics | None:
        return self._get('characteristics', 'Characteristics', False, True)

class Report(Record):
    __slots__ = ()
    def __init__(self, *, status: Status | None | Unset = UNSET, runtime: Runtime | None | Unset = UNSET, diagnostics: tuple[Diagnostic, ...] | None | Unset = UNSET, trace: tuple[Step, ...] | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def status(self) -> Status | None:
        return self._get('status', 'Status', False, True)
    @property
    def runtime(self) -> Runtime | None:
        return self._get('runtime', 'Runtime', False, True)
    @property
    def diagnostics(self) -> tuple[Diagnostic, ...] | None:
        return self._get('diagnostics', 'Diagnostic', True, True)
    @property
    def trace(self) -> tuple[Step, ...] | None:
        return self._get('trace', 'Step', True, True)

class Run(Record):
    __slots__ = ()
    def __init__(self, *, metadata: Metadata | None | Unset = UNSET, specification: UUID | None | Unset = UNSET, spawns: tuple[UUID, ...] | None | Unset = UNSET, outputs: tuple[UUID, ...] | None | Unset = UNSET, report: Report | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def metadata(self) -> Metadata | None:
        return self._get('metadata', 'Metadata', False, True)
    @property
    def specification(self) -> UUID | None:
        return self._get('specification', 'Metadata', False, False)
    @property
    def spawns(self) -> tuple[UUID, ...] | None:
        return self._get('spawns', 'Metadata', True, False)
    @property
    def outputs(self) -> tuple[UUID, ...] | None:
        return self._get('outputs', 'Metadata', True, False)
    @property
    def report(self) -> Report | None:
        return self._get('report', 'Report', False, True)

class Runtime(Record):
    __slots__ = ()
    def __init__(self, *, started_at: Any | None | Unset = UNSET, finished_at: Any | None | Unset = UNSET, implementations: tuple[Implementation, ...] | None | Unset = UNSET, settings: Settings | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def started_at(self) -> Any | None:
        return self._get('started_at', 'datetime', False, False)
    @property
    def finished_at(self) -> Any | None:
        return self._get('finished_at', 'datetime', False, False)
    @property
    def implementations(self) -> tuple[Implementation, ...] | None:
        return self._get('implementations', 'Implementation', True, True)
    @property
    def settings(self) -> Settings | None:
        return self._get('settings', 'Settings', False, True)

class Selection(Record):
    __slots__ = ()
    def __init__(self, *, kind: Any | None | Unset = UNSET, base: Expression | None | Unset = UNSET, member: str | None | Unset = UNSET, index: Expression | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def kind(self) -> Any | None:
        return self._get('kind', 'SelectionKind', False, False)
    @property
    def base(self) -> Expression | None:
        return self._get('base', 'Expression', False, True)
    @property
    def member(self) -> str | None:
        return self._get('member', 'Code', False, False)
    @property
    def index(self) -> Expression | None:
        return self._get('index', 'Expression', False, True)

class Settings(Record):
    __slots__ = ()
    def __init__(self, *, relative_tolerance: float | None | Unset = UNSET, iteration_limit: int | None | Unset = UNSET, time_limit: float | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def relative_tolerance(self) -> float | None:
        return self._get('relative_tolerance', 'decimal', False, False)
    @property
    def iteration_limit(self) -> int | None:
        return self._get('iteration_limit', 'integer', False, False)
    @property
    def time_limit(self) -> float | None:
        return self._get('time_limit', 'decimal', False, False)

class Source(Record):
    __slots__ = ()
    def __init__(self, *, id: UUID | None | Unset = UNSET, name: str | None | Unset = UNSET, checksum: str | None | Unset = UNSET, issued_at: UUID | None | Unset = UNSET, received_at: UUID | None | Unset = UNSET, author: str | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def name(self) -> str | None:
        return self._get('name', 'string', False, False)
    @property
    def checksum(self) -> str | None:
        return self._get('checksum', 'string', False, False)
    @property
    def issued_at(self) -> UUID | None:
        return self._get('issued_at', 'Content', False, False)
    @property
    def received_at(self) -> UUID | None:
        return self._get('received_at', 'Content', False, False)
    @property
    def author(self) -> str | None:
        return self._get('author', 'string', False, False)

class Specification(Record):
    __slots__ = ()
    def __init__(self, *, metadata: Metadata | None | Unset = UNSET, model: UUID | None | Unset = UNSET, includes: tuple[UUID, ...] | None | Unset = UNSET, cases: tuple[UUID, ...] | None | Unset = UNSET, assignments: tuple[Assignment, ...] | None | Unset = UNSET, unknowns: tuple[UUID, ...] | None | Unset = UNSET, estimates: tuple[Assignment, ...] | None | Unset = UNSET, formulations: tuple[Formulation, ...] | None | Unset = UNSET, objectives: tuple[Objective, ...] | None | Unset = UNSET, settings: Settings | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def metadata(self) -> Metadata | None:
        return self._get('metadata', 'Metadata', False, True)
    @property
    def model(self) -> UUID | None:
        return self._get('model', 'Metadata', False, False)
    @property
    def includes(self) -> tuple[UUID, ...] | None:
        return self._get('includes', 'Metadata', True, False)
    @property
    def cases(self) -> tuple[UUID, ...] | None:
        return self._get('cases', 'Metadata', True, False)
    @property
    def assignments(self) -> tuple[Assignment, ...] | None:
        return self._get('assignments', 'Assignment', True, True)
    @property
    def unknowns(self) -> tuple[UUID, ...] | None:
        return self._get('unknowns', 'Value', True, False)
    @property
    def estimates(self) -> tuple[Assignment, ...] | None:
        return self._get('estimates', 'Assignment', True, True)
    @property
    def formulations(self) -> tuple[Formulation, ...] | None:
        return self._get('formulations', 'Formulation', True, True)
    @property
    def objectives(self) -> tuple[Objective, ...] | None:
        return self._get('objectives', 'Objective', True, True)
    @property
    def settings(self) -> Settings | None:
        return self._get('settings', 'Settings', False, True)

class Status(Record):
    __slots__ = ()
    def __init__(self, *, completion: Any | None | Unset = UNSET, solution: Any | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def completion(self) -> Any | None:
        return self._get('completion', 'CompletionStatus', False, False)
    @property
    def solution(self) -> Any | None:
        return self._get('solution', 'SolutionStatus', False, False)

class Step(Record):
    __slots__ = ()
    def __init__(self, *, kind: Any | None | Unset = UNSET, at: Any | None | Unset = UNSET, message: str | None | Unset = UNSET, document: UUID | None | Unset = UNSET, target: UUID | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def kind(self) -> Any | None:
        return self._get('kind', 'StepKind', False, False)
    @property
    def at(self) -> Any | None:
        return self._get('at', 'datetime', False, False)
    @property
    def message(self) -> str | None:
        return self._get('message', 'string', False, False)
    @property
    def document(self) -> UUID | None:
        return self._get('document', 'Metadata', False, False)
    @property
    def target(self) -> UUID | None:
        return self._get('target', 'UUID', False, False)

class System(Record):
    __slots__ = ()
    def __init__(self, *, entities: tuple[Entity, ...] | None | Unset = UNSET, relationships: tuple[Relationship, ...] | None | Unset = UNSET, assemblies: tuple[Assembly, ...] | None | Unset = UNSET, formulations: tuple[Formulation, ...] | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def entities(self) -> tuple[Entity, ...] | None:
        return self._get('entities', 'Entity', True, True)
    @property
    def relationships(self) -> tuple[Relationship, ...] | None:
        return self._get('relationships', 'Relationship', True, True)
    @property
    def assemblies(self) -> tuple[Assembly, ...] | None:
        return self._get('assemblies', 'Assembly', True, True)
    @property
    def formulations(self) -> tuple[Formulation, ...] | None:
        return self._get('formulations', 'Formulation', True, True)

class Taxonomy(Record):
    __slots__ = ()
    def __init__(self, *, id: UUID | None | Unset = UNSET, code: str | None | Unset = UNSET, name: str | None | Unset = UNSET, definition: str | None | Unset = UNSET, classifications: tuple[Classification, ...] | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def code(self) -> str | None:
        return self._get('code', 'Code', False, False)
    @property
    def name(self) -> str | None:
        return self._get('name', 'string', False, False)
    @property
    def definition(self) -> str | None:
        return self._get('definition', 'string', False, False)
    @property
    def classifications(self) -> tuple[Classification, ...] | None:
        return self._get('classifications', 'Classification', True, True)

class Traversal(Record):
    __slots__ = ()
    def __init__(self, *, kind: Any | None | Unset = UNSET, depth: Any | None | Unset = UNSET, classification: UUID | None | Unset = UNSET, direction: Any | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def kind(self) -> Any | None:
        return self._get('kind', 'TraversalKind', False, False)
    @property
    def depth(self) -> Any | None:
        return self._get('depth', 'Depth', False, False)
    @property
    def classification(self) -> UUID | None:
        return self._get('classification', 'Classification', False, False)
    @property
    def direction(self) -> Any | None:
        return self._get('direction', 'Direction', False, False)

class Value(Record):
    __slots__ = ()
    def __init__(self, *, measure: UUID | None | Unset = UNSET, quantity: Quantity | None | Unset = UNSET, id: UUID | None | Unset = UNSET, key: str | None | Unset = UNSET, kind: Any | None | Unset = UNSET, description: str | None | Unset = UNSET):
        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))
    @property
    def measure(self) -> UUID | None:
        return self._get('measure', 'Measure', False, False)
    @property
    def quantity(self) -> Quantity | None:
        return self._get('quantity', 'Quantity', False, True)
    @property
    def id(self) -> UUID | None:
        return self._get('id', 'UUID', False, False)
    @property
    def key(self) -> str | None:
        return self._get('key', 'string', False, False)
    @property
    def kind(self) -> Any | None:
        return self._get('kind', 'ValueKind', False, False)
    @property
    def description(self) -> str | None:
        return self._get('description', 'string', False, False)

RECORDS = {'Argument': Argument, 'Assembly': Assembly, 'Assignment': Assignment, 'Binding': Binding, 'Call': Call, 'Characteristics': Characteristics, 'Claim': Claim, 'Classification': Classification, 'Constraint': Constraint, 'Content': Content, 'Criterion': Criterion, 'Definitions': Definitions, 'Diagnostic': Diagnostic, 'Domain': Domain, 'Entity': Entity, 'Entry': Entry, 'Expression': Expression, 'Fact': Fact, 'Filter': Filter, 'Formulation': Formulation, 'Function': Function, 'Implementation': Implementation, 'Label': Label, 'Location': Location, 'Measure': Measure, 'Measurement': Measurement, 'Metadata': Metadata, 'Method': Method, 'Model': Model, 'Objective': Objective, 'Parameter': Parameter, 'Projection': Projection, 'Provenance': Provenance, 'Quantity': Quantity, 'Query': Query, 'Reconciliation': Reconciliation, 'Relationship': Relationship, 'Report': Report, 'Run': Run, 'Runtime': Runtime, 'Selection': Selection, 'Settings': Settings, 'Source': Source, 'Specification': Specification, 'Status': Status, 'Step': Step, 'System': System, 'Taxonomy': Taxonomy, 'Traversal': Traversal, 'Value': Value}
