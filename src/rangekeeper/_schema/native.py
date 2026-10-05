# id: https://daniel-fink.github.io/rangekeeper/schema/bundle
# description:
# license: https://creativecommons.org/publicdomain/zero/1.0/

import dataclasses
import re
from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    time
)
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Union
)

from jsonasobj2 import (
    JsonObj,
    as_dict
)
from linkml_runtime.linkml_model.meta import (
    EnumDefinition,
    PermissibleValue,
    PvFormulaOptions
)
from linkml_runtime.utils.curienamespace import CurieNamespace
from linkml_runtime.utils.enumerations import EnumDefinitionImpl
from linkml_runtime.utils.formatutils import (
    camelcase,
    sfx,
    underscore
)
from linkml_runtime.utils.metamodelcore import (
    bnode,
    empty_dict,
    empty_list
)
from linkml_runtime.utils.slot import Slot
from linkml_runtime.utils.yamlutils import (
    YAMLRoot,
    extended_float,
    extended_int,
    extended_str
)
from rdflib import (
    Namespace,
    URIRef
)

from linkml_runtime.linkml_model.types import Boolean, Date, Datetime, Decimal, Integer, String
from linkml_runtime.utils.metamodelcore import Bool, Decimal, XSDDate, XSDDateTime

metamodel_version = "1.11.0"
version = None

# Namespaces
LINKML = CurieNamespace('linkml', 'https://w3id.org/linkml/')
RK = CurieNamespace('rk', 'https://daniel-fink.github.io/rangekeeper/schema/')
XSD = CurieNamespace('xsd', 'http://www.w3.org/2001/XMLSchema#')
DEFAULT_ = CurieNamespace('', 'https://daniel-fink.github.io/rangekeeper/schema/bundle/')


# Types
class Code(String):
    """ A case-sensitive name unique within its declared collection. Leading and trailing whitespace are forbidden; codes are not silently normalized. """
    type_class_uri = XSD["string"]
    type_class_curie = "xsd:string"
    type_name = "Code"
    type_model_uri = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Code")


class UUID(String):
    """ A universally unique identifier in hyphenated hexadecimal form. """
    type_class_uri = XSD["string"]
    type_class_curie = "xsd:string"
    type_name = "UUID"
    type_model_uri = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/UUID")


# Class references
class FormulationId(UUID):
    pass


class SourceId(UUID):
    pass


class EntryKey(extended_str):
    pass


class ClaimId(UUID):
    pass


class MetadataId(UUID):
    pass


class MeasureId(UUID):
    pass


class MeasurementId(UUID):
    pass


class ClassificationId(UUID):
    pass


class TaxonomyId(UUID):
    pass


class FunctionId(UUID):
    pass


class ConstraintId(UUID):
    pass


class ExpressionId(UUID):
    pass


class RelationshipId(UUID):
    pass


class EntityId(UUID):
    pass


class AssemblyId(EntityId):
    pass


class LabelId(UUID):
    pass


class ValueId(UUID):
    pass


@dataclass(repr=False)
class Model(YAMLRoot):
    """
    A self-contained snapshot of a system's declarations, mathematical formulations, and recorded content, identified
    by its Metadata.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Model"]
    class_class_curie: ClassVar[str] = "rk:Model"
    class_name: ClassVar[str] = "Model"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Model")

    metadata: Union[dict, "Metadata"] = None
    definitions: Optional[Union[dict, "Definitions"]] = None
    system: Optional[Union[dict, "System"]] = None
    provenance: Optional[Union[dict, "Provenance"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.metadata):
            self.MissingRequiredField("metadata")
        if not isinstance(self.metadata, Metadata):
            self.metadata = Metadata(**as_dict(self.metadata))

        if self.definitions is not None and not isinstance(self.definitions, Definitions):
            self.definitions = Definitions(**as_dict(self.definitions))

        if self.system is not None and not isinstance(self.system, System):
            self.system = System(**as_dict(self.system))

        if self.provenance is not None and not isinstance(self.provenance, Provenance):
            self.provenance = Provenance(**as_dict(self.provenance))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class System(YAMLRoot):
    """
    The Entities, Relationships, Assemblies, and mathematical formulations of a Model.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["System"]
    class_class_curie: ClassVar[str] = "rk:System"
    class_name: ClassVar[str] = "System"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/System")

    entities: Optional[Union[dict[Union[str, EntityId], Union[dict, "Entity"]], list[Union[dict, "Entity"]]]] = empty_dict()
    relationships: Optional[Union[dict[Union[str, RelationshipId], Union[dict, "Relationship"]], list[Union[dict, "Relationship"]]]] = empty_dict()
    assemblies: Optional[Union[dict[Union[str, AssemblyId], Union[dict, "Assembly"]], list[Union[dict, "Assembly"]]]] = empty_dict()
    formulations: Optional[Union[dict[Union[str, FormulationId], Union[dict, "Formulation"]], list[Union[dict, "Formulation"]]]] = empty_dict()

    def __post_init__(self, *_: str, **kwargs: Any):
        self._normalize_inlined_as_list(slot_name="entities", slot_type=Entity, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="relationships", slot_type=Relationship, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="assemblies", slot_type=Assembly, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="formulations", slot_type=Formulation, key_name="id", keyed=True)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Specification(YAMLRoot):
    """
    An immutable contribution of investigation requirements, a composition of such contributions, or a batch of
    separate Specifications. A concrete composition investigates one pinned Model revision.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Specification"]
    class_class_curie: ClassVar[str] = "rk:Specification"
    class_name: ClassVar[str] = "Specification"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Specification")

    metadata: Union[dict, "Metadata"] = None
    model: Optional[Union[str, MetadataId]] = None
    includes: Optional[Union[Union[str, MetadataId], list[Union[str, MetadataId]]]] = empty_list()
    cases: Optional[Union[Union[str, MetadataId], list[Union[str, MetadataId]]]] = empty_list()
    assignments: Optional[Union[Union[dict, "Assignment"], list[Union[dict, "Assignment"]]]] = empty_list()
    unknowns: Optional[Union[Union[str, ValueId], list[Union[str, ValueId]]]] = empty_list()
    estimates: Optional[Union[Union[dict, "Assignment"], list[Union[dict, "Assignment"]]]] = empty_list()
    formulations: Optional[Union[dict[Union[str, FormulationId], Union[dict, "Formulation"]], list[Union[dict, "Formulation"]]]] = empty_dict()
    objectives: Optional[Union[Union[dict, "Objective"], list[Union[dict, "Objective"]]]] = empty_list()
    settings: Optional[Union[dict, "Settings"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.metadata):
            self.MissingRequiredField("metadata")
        if not isinstance(self.metadata, Metadata):
            self.metadata = Metadata(**as_dict(self.metadata))

        if self.model is not None and not isinstance(self.model, MetadataId):
            self.model = MetadataId(self.model)

        if not isinstance(self.includes, list):
            self.includes = [self.includes] if self.includes is not None else []
        self.includes = [v if isinstance(v, MetadataId) else MetadataId(v) for v in self.includes]

        if not isinstance(self.cases, list):
            self.cases = [self.cases] if self.cases is not None else []
        self.cases = [v if isinstance(v, MetadataId) else MetadataId(v) for v in self.cases]

        if not isinstance(self.assignments, list):
            self.assignments = [self.assignments] if self.assignments is not None else []
        self.assignments = [v if isinstance(v, Assignment) else Assignment(**as_dict(v)) for v in self.assignments]

        if not isinstance(self.unknowns, list):
            self.unknowns = [self.unknowns] if self.unknowns is not None else []
        self.unknowns = [v if isinstance(v, ValueId) else ValueId(v) for v in self.unknowns]

        if not isinstance(self.estimates, list):
            self.estimates = [self.estimates] if self.estimates is not None else []
        self.estimates = [v if isinstance(v, Assignment) else Assignment(**as_dict(v)) for v in self.estimates]

        self._normalize_inlined_as_list(slot_name="formulations", slot_type=Formulation, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="objectives", slot_type=Objective, key_name="sense", keyed=False)

        if self.settings is not None and not isinstance(self.settings, Settings):
            self.settings = Settings(**as_dict(self.settings))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Assignment(YAMLRoot):
    """
    Embedded association of a numerical Value reference with a supplied Quantity.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Assignment"]
    class_class_curie: ClassVar[str] = "rk:Assignment"
    class_name: ClassVar[str] = "Assignment"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Assignment")

    value: Union[str, ValueId] = None
    quantity: Union[dict, "Quantity"] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.value):
            self.MissingRequiredField("value")
        if not isinstance(self.value, ValueId):
            self.value = ValueId(self.value)

        if self._is_empty(self.quantity):
            self.MissingRequiredField("quantity")
        if not isinstance(self.quantity, Quantity):
            self.quantity = Quantity(**as_dict(self.quantity))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Objective(YAMLRoot):
    """
    A scalar numerical Expression and the sense in which its result is preferred.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Objective"]
    class_class_curie: ClassVar[str] = "rk:Objective"
    class_name: ClassVar[str] = "Objective"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Objective")

    expression: Union[str, ExpressionId] = None
    sense: Union[str, "ObjectiveKind"] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.expression):
            self.MissingRequiredField("expression")
        if not isinstance(self.expression, ExpressionId):
            self.expression = ExpressionId(self.expression)

        if self._is_empty(self.sense):
            self.MissingRequiredField("sense")
        if not isinstance(self.sense, ObjectiveKind):
            self.sense = ObjectiveKind(self.sense)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Run(YAMLRoot):
    """
    The finalized record of one execution attempt against an exact Specification revision.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Run"]
    class_class_curie: ClassVar[str] = "rk:Run"
    class_name: ClassVar[str] = "Run"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Run")

    metadata: Union[dict, "Metadata"] = None
    specification: Union[str, MetadataId] = None
    report: Union[dict, "Report"] = None
    spawns: Optional[Union[Union[str, MetadataId], list[Union[str, MetadataId]]]] = empty_list()
    outputs: Optional[Union[Union[str, MetadataId], list[Union[str, MetadataId]]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.metadata):
            self.MissingRequiredField("metadata")
        if not isinstance(self.metadata, Metadata):
            self.metadata = Metadata(**as_dict(self.metadata))

        if self._is_empty(self.specification):
            self.MissingRequiredField("specification")
        if not isinstance(self.specification, MetadataId):
            self.specification = MetadataId(self.specification)

        if self._is_empty(self.report):
            self.MissingRequiredField("report")
        if not isinstance(self.report, Report):
            self.report = Report(**as_dict(self.report))

        if not isinstance(self.spawns, list):
            self.spawns = [self.spawns] if self.spawns is not None else []
        self.spawns = [v if isinstance(v, MetadataId) else MetadataId(v) for v in self.spawns]

        if not isinstance(self.outputs, list):
            self.outputs = [self.outputs] if self.outputs is not None else []
        self.outputs = [v if isinstance(v, MetadataId) else MetadataId(v) for v in self.outputs]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Report(YAMLRoot):
    """
    Outcome, actual runtime, findings, and ordered execution trace of a Run.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Report"]
    class_class_curie: ClassVar[str] = "rk:Report"
    class_name: ClassVar[str] = "Report"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Report")

    status: Union[dict, "Status"] = None
    runtime: Optional[Union[dict, "Runtime"]] = None
    diagnostics: Optional[Union[Union[dict, "Diagnostic"], list[Union[dict, "Diagnostic"]]]] = empty_list()
    trace: Optional[Union[Union[dict, "Step"], list[Union[dict, "Step"]]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.status):
            self.MissingRequiredField("status")
        if not isinstance(self.status, Status):
            self.status = Status(**as_dict(self.status))

        if self.runtime is not None and not isinstance(self.runtime, Runtime):
            self.runtime = Runtime(**as_dict(self.runtime))

        self._normalize_inlined_as_list(slot_name="diagnostics", slot_type=Diagnostic, key_name="severity", keyed=False)

        self._normalize_inlined_as_list(slot_name="trace", slot_type=Step, key_name="kind", keyed=False)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Status(YAMLRoot):
    """
    Execution completion and mathematical conclusion, recorded independently.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Status"]
    class_class_curie: ClassVar[str] = "rk:Status"
    class_name: ClassVar[str] = "Status"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Status")

    completion: Union[str, "CompletionStatus"] = None
    solution: Union[str, "SolutionStatus"] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.completion):
            self.MissingRequiredField("completion")
        if not isinstance(self.completion, CompletionStatus):
            self.completion = CompletionStatus(self.completion)

        if self._is_empty(self.solution):
            self.MissingRequiredField("solution")
        if not isinstance(self.solution, SolutionStatus):
            self.solution = SolutionStatus(self.solution)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Runtime(YAMLRoot):
    """
    Observed timing, implementation identities, and effective numerical settings.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Runtime"]
    class_class_curie: ClassVar[str] = "rk:Runtime"
    class_name: ClassVar[str] = "Runtime"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Runtime")

    implementations: Union[Union[dict, "Implementation"], list[Union[dict, "Implementation"]]] = None
    started_at: Optional[Union[str, XSDDateTime]] = None
    finished_at: Optional[Union[str, XSDDateTime]] = None
    settings: Optional[Union[dict, "Settings"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.implementations):
            self.MissingRequiredField("implementations")
        self._normalize_inlined_as_list(slot_name="implementations", slot_type=Implementation, key_name="kind", keyed=False)

        if self.started_at is not None and not isinstance(self.started_at, XSDDateTime):
            self.started_at = XSDDateTime(self.started_at)

        if self.finished_at is not None and not isinstance(self.finished_at, XSDDateTime):
            self.finished_at = XSDDateTime(self.finished_at)

        if self.settings is not None and not isinstance(self.settings, Settings):
            self.settings = Settings(**as_dict(self.settings))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Implementation(YAMLRoot):
    """
    An implementation role and its reproducible software identity as reported for this execution.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Implementation"]
    class_class_curie: ClassVar[str] = "rk:Implementation"
    class_name: ClassVar[str] = "Implementation"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Implementation")

    kind: Union[str, "ImplementationKind"] = None
    name: str = None
    version: str = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.kind):
            self.MissingRequiredField("kind")
        if not isinstance(self.kind, ImplementationKind):
            self.kind = ImplementationKind(self.kind)

        if self._is_empty(self.name):
            self.MissingRequiredField("name")
        if not isinstance(self.name, str):
            self.name = str(self.name)

        if self._is_empty(self.version):
            self.MissingRequiredField("version")
        if not isinstance(self.version, str):
            self.version = str(self.version)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Diagnostic(YAMLRoot):
    """
    A coded finding and optional numerical evidence, qualified by document revision.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Diagnostic"]
    class_class_curie: ClassVar[str] = "rk:Diagnostic"
    class_name: ClassVar[str] = "Diagnostic"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Diagnostic")

    severity: Union[str, "Severity"] = None
    code: Union[str, Code] = None
    message: str = None
    document: Optional[Union[str, MetadataId]] = None
    target: Optional[Union[str, UUID]] = None
    residual: Optional[Union[dict, "Quantity"]] = None
    tolerance: Optional[Union[dict, "Quantity"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.severity):
            self.MissingRequiredField("severity")
        if not isinstance(self.severity, Severity):
            self.severity = Severity(self.severity)

        if self._is_empty(self.code):
            self.MissingRequiredField("code")
        if not isinstance(self.code, Code):
            self.code = Code(self.code)

        if self._is_empty(self.message):
            self.MissingRequiredField("message")
        if not isinstance(self.message, str):
            self.message = str(self.message)

        if self.document is not None and not isinstance(self.document, MetadataId):
            self.document = MetadataId(self.document)

        if self.target is not None and not isinstance(self.target, UUID):
            self.target = UUID(self.target)

        if self.residual is not None and not isinstance(self.residual, Quantity):
            self.residual = Quantity(**as_dict(self.residual))

        if self.tolerance is not None and not isinstance(self.tolerance, Quantity):
            self.tolerance = Quantity(**as_dict(self.tolerance))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Step(YAMLRoot):
    """
    One ordered record of execution activity, without prescribing scheduling or policy logic.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Step"]
    class_class_curie: ClassVar[str] = "rk:Step"
    class_name: ClassVar[str] = "Step"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Step")

    kind: Union[str, "StepKind"] = None
    message: str = None
    at: Optional[Union[str, XSDDateTime]] = None
    document: Optional[Union[str, MetadataId]] = None
    target: Optional[Union[str, UUID]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.kind):
            self.MissingRequiredField("kind")
        if not isinstance(self.kind, StepKind):
            self.kind = StepKind(self.kind)

        if self._is_empty(self.message):
            self.MissingRequiredField("message")
        if not isinstance(self.message, str):
            self.message = str(self.message)

        if self.at is not None and not isinstance(self.at, XSDDateTime):
            self.at = XSDDateTime(self.at)

        if self.document is not None and not isinstance(self.document, MetadataId):
            self.document = MetadataId(self.document)

        if self.target is not None and not isinstance(self.target, UUID):
            self.target = UUID(self.target)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Definitions(YAMLRoot):
    """
    Reusable Taxonomies, Measures, and Functions identified by stable UUIDs within a Model.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Definitions"]
    class_class_curie: ClassVar[str] = "rk:Definitions"
    class_name: ClassVar[str] = "Definitions"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Definitions")

    taxonomies: Optional[Union[dict[Union[str, TaxonomyId], Union[dict, "Taxonomy"]], list[Union[dict, "Taxonomy"]]]] = empty_dict()
    measures: Optional[Union[dict[Union[str, MeasureId], Union[dict, "Measure"]], list[Union[dict, "Measure"]]]] = empty_dict()
    functions: Optional[Union[dict[Union[str, FunctionId], Union[dict, "Function"]], list[Union[dict, "Function"]]]] = empty_dict()

    def __post_init__(self, *_: str, **kwargs: Any):
        self._normalize_inlined_as_list(slot_name="taxonomies", slot_type=Taxonomy, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="measures", slot_type=Measure, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="functions", slot_type=Function, key_name="id", keyed=True)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Binding(YAMLRoot):
    """
    A name within a Formulation that refers to an existing Value by UUID.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Binding"]
    class_class_curie: ClassVar[str] = "rk:Binding"
    class_name: ClassVar[str] = "Binding"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Binding")

    name: Union[str, Code] = None
    value: Union[str, ValueId] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.name):
            self.MissingRequiredField("name")
        if not isinstance(self.name, Code):
            self.name = Code(self.name)

        if self._is_empty(self.value):
            self.MissingRequiredField("value")
        if not isinstance(self.value, ValueId):
            self.value = ValueId(self.value)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Formulation(YAMLRoot):
    """
    An identified mathematical container with explicit local declarations, expressions, and asserted constraints.
    Formulations may contain child Formulations and bind names to shared Values.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Formulation"]
    class_class_curie: ClassVar[str] = "rk:Formulation"
    class_name: ClassVar[str] = "Formulation"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Formulation")

    id: Union[str, FormulationId] = None
    code: Optional[Union[str, Code]] = None
    name: Optional[str] = None
    description: Optional[str] = None
    bindings: Optional[Union[Union[dict, Binding], list[Union[dict, Binding]]]] = empty_list()
    values: Optional[Union[dict[Union[str, ValueId], Union[dict, "Value"]], list[Union[dict, "Value"]]]] = empty_dict()
    expressions: Optional[Union[dict[Union[str, ExpressionId], Union[dict, "Expression"]], list[Union[dict, "Expression"]]]] = empty_dict()
    constraints: Optional[Union[dict[Union[str, ConstraintId], Union[dict, "Constraint"]], list[Union[dict, "Constraint"]]]] = empty_dict()
    formulations: Optional[Union[dict[Union[str, FormulationId], Union[dict, "Formulation"]], list[Union[dict, "Formulation"]]]] = empty_dict()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, FormulationId):
            self.id = FormulationId(self.id)

        if self.code is not None and not isinstance(self.code, Code):
            self.code = Code(self.code)

        if self.name is not None and not isinstance(self.name, str):
            self.name = str(self.name)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        self._normalize_inlined_as_list(slot_name="bindings", slot_type=Binding, key_name="name", keyed=False)

        self._normalize_inlined_as_list(slot_name="values", slot_type=Value, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="expressions", slot_type=Expression, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="constraints", slot_type=Constraint, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="formulations", slot_type=Formulation, key_name="id", keyed=True)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Provenance(YAMLRoot):
    """
    Facts connecting graph objects to supporting Claims, with the Sources and upstream Claims needed to follow their
    lineage.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Provenance"]
    class_class_curie: ClassVar[str] = "rk:Provenance"
    class_name: ClassVar[str] = "Provenance"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Provenance")

    sources: Optional[Union[dict[Union[str, SourceId], Union[dict, "Source"]], list[Union[dict, "Source"]]]] = empty_dict()
    claims: Optional[Union[dict[Union[str, ClaimId], Union[dict, "Claim"]], list[Union[dict, "Claim"]]]] = empty_dict()
    facts: Optional[Union[Union[dict, "Fact"], list[Union[dict, "Fact"]]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        self._normalize_inlined_as_list(slot_name="sources", slot_type=Source, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="claims", slot_type=Claim, key_name="id", keyed=True)

        if not isinstance(self.facts, list):
            self.facts = [self.facts] if self.facts is not None else []
        self.facts = [v if isinstance(v, Fact) else Fact(**as_dict(v)) for v in self.facts]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Source(YAMLRoot):
    """
    An identifiable edition of an external evidence artifact.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Source"]
    class_class_curie: ClassVar[str] = "rk:Source"
    class_name: ClassVar[str] = "Source"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Source")

    id: Union[str, SourceId] = None
    name: str = None
    checksum: str = None
    issued_at: Optional[Union[dict, "Content"]] = None
    received_at: Optional[Union[dict, "Content"]] = None
    author: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, SourceId):
            self.id = SourceId(self.id)

        if self._is_empty(self.name):
            self.MissingRequiredField("name")
        if not isinstance(self.name, str):
            self.name = str(self.name)

        if self._is_empty(self.checksum):
            self.MissingRequiredField("checksum")
        if not isinstance(self.checksum, str):
            self.checksum = str(self.checksum)

        if self.author is not None and not isinstance(self.author, str):
            self.author = str(self.author)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Location(YAMLRoot):
    """
    An address within a specific Source edition.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Location"]
    class_class_curie: ClassVar[str] = "rk:Location"
    class_name: ClassVar[str] = "Location"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Location")

    source: Union[str, SourceId] = None
    address: Optional[Union[dict[Union[str, EntryKey], Union[dict, "Entry"]], list[Union[dict, "Entry"]]]] = empty_dict()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.source):
            self.MissingRequiredField("source")
        if not isinstance(self.source, SourceId):
            self.source = SourceId(self.source)

        self._normalize_inlined_as_dict(slot_name="address", slot_type=Entry, key_name="key", keyed=True)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Entry(YAMLRoot):
    """
    A named text component of a source address.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Entry"]
    class_class_curie: ClassVar[str] = "rk:Entry"
    class_name: ClassVar[str] = "Entry"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Entry")

    key: Union[str, EntryKey] = None
    value: str = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.key):
            self.MissingRequiredField("key")
        if not isinstance(self.key, EntryKey):
            self.key = EntryKey(self.key)

        if self._is_empty(self.value):
            self.MissingRequiredField("value")
        if not isinstance(self.value, str):
            self.value = str(self.value)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Method(YAMLRoot):
    """
    The named process used to assert, derive, or reconcile evidence.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Method"]
    class_class_curie: ClassVar[str] = "rk:Method"
    class_name: ClassVar[str] = "Method"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Method")

    code: str = None
    version: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.code):
            self.MissingRequiredField("code")
        if not isinstance(self.code, str):
            self.code = str(self.code)

        if self.version is not None and not isinstance(self.version, str):
            self.version = str(self.version)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        super().__post_init__(**kwargs)


Content = Any

@dataclass(repr=False)
class Claim(YAMLRoot):
    """
    Sourced, asserted, or derived candidate content and its supporting lineage.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Claim"]
    class_class_curie: ClassVar[str] = "rk:Claim"
    class_name: ClassVar[str] = "Claim"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Claim")

    id: Union[str, ClaimId] = None
    content: Union[dict, Content] = None
    kind: Union[str, "ClaimKind"] = None
    sources: Optional[Union[Union[dict, Content], list[Union[dict, Content]]]] = empty_list()
    method: Optional[Union[dict, Method]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, ClaimId):
            self.id = ClaimId(self.id)

        if self._is_empty(self.kind):
            self.MissingRequiredField("kind")
        if not isinstance(self.kind, ClaimKind):
            self.kind = ClaimKind(self.kind)

        if self.method is not None and not isinstance(self.method, Method):
            self.method = Method(**as_dict(self.method))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Fact(YAMLRoot):
    """
    Supporting Claims for the recorded state of one graph object or characteristic.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Fact"]
    class_class_curie: ClassVar[str] = "rk:Fact"
    class_name: ClassVar[str] = "Fact"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Fact")

    target: Union[dict, Content] = None
    claims: Union[Union[str, ClaimId], list[Union[str, ClaimId]]] = None
    reconciliation: Optional[Union[dict, "Reconciliation"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.claims):
            self.MissingRequiredField("claims")
        if not isinstance(self.claims, list):
            self.claims = [self.claims] if self.claims is not None else []
        self.claims = [v if isinstance(v, ClaimId) else ClaimId(v) for v in self.claims]

        if self.reconciliation is not None and not isinstance(self.reconciliation, Reconciliation):
            self.reconciliation = Reconciliation(**as_dict(self.reconciliation))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Reconciliation(YAMLRoot):
    """
    Explicit selection of one supporting Claim when evidence conflicts.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Reconciliation"]
    class_class_curie: ClassVar[str] = "rk:Reconciliation"
    class_name: ClassVar[str] = "Reconciliation"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Reconciliation")

    selected: Union[str, ClaimId] = None
    status: Union[str, "ReconciliationStatus"] = None
    method: Optional[Union[dict, Method]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.selected):
            self.MissingRequiredField("selected")
        if not isinstance(self.selected, ClaimId):
            self.selected = ClaimId(self.selected)

        if self._is_empty(self.status):
            self.MissingRequiredField("status")
        if not isinstance(self.status, ReconciliationStatus):
            self.status = ReconciliationStatus(self.status)

        if self.method is not None and not isinstance(self.method, Method):
            self.method = Method(**as_dict(self.method))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Metadata(YAMLRoot):
    """
    Identity, description, and optional lineage of one immutable document revision.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Metadata"]
    class_class_curie: ClassVar[str] = "rk:Metadata"
    class_name: ClassVar[str] = "Metadata"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Metadata")

    id: Union[str, MetadataId] = None
    schema_version: Union[str, Code] = None
    name: Optional[str] = None
    description: Optional[str] = None
    previous: Optional[Union[str, MetadataId]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, MetadataId):
            self.id = MetadataId(self.id)

        if self._is_empty(self.schema_version):
            self.MissingRequiredField("schema_version")
        if not isinstance(self.schema_version, Code):
            self.schema_version = Code(self.schema_version)

        if self.name is not None and not isinstance(self.name, str):
            self.name = str(self.name)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.previous is not None and not isinstance(self.previous, MetadataId):
            self.previous = MetadataId(self.previous)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Settings(YAMLRoot):
    """
    Numerical convergence and resource settings; the containing record distinguishes requested from effective values.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Settings"]
    class_class_curie: ClassVar[str] = "rk:Settings"
    class_name: ClassVar[str] = "Settings"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Settings")

    relative_tolerance: Optional[Decimal] = None
    iteration_limit: Optional[int] = None
    time_limit: Optional[Decimal] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.relative_tolerance is not None and not isinstance(self.relative_tolerance, Decimal):
            self.relative_tolerance = Decimal(self.relative_tolerance)

        if self.iteration_limit is not None and not isinstance(self.iteration_limit, int):
            self.iteration_limit = int(self.iteration_limit)

        if self.time_limit is not None and not isinstance(self.time_limit, Decimal):
            self.time_limit = Decimal(self.time_limit)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Quantity(YAMLRoot):
    """
    Numerical content consisting of a finite magnitude and explicit units.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Quantity"]
    class_class_curie: ClassVar[str] = "rk:Quantity"
    class_name: ClassVar[str] = "Quantity"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Quantity")

    magnitude: Decimal = None
    units: str = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.magnitude):
            self.MissingRequiredField("magnitude")
        if not isinstance(self.magnitude, Decimal):
            self.magnitude = Decimal(self.magnitude)

        if self._is_empty(self.units):
            self.MissingRequiredField("units")
        if not isinstance(self.units, str):
            self.units = str(self.units)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Measure(YAMLRoot):
    """
    An identified definition of a measurable characteristic and its canonical units.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Measure"]
    class_class_curie: ClassVar[str] = "rk:Measure"
    class_name: ClassVar[str] = "Measure"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Measure")

    id: Union[str, MeasureId] = None
    code: Union[str, Code] = None
    name: str = None
    units: str = None
    definition: Optional[str] = None
    tags: Optional[Union[str, list[str]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, MeasureId):
            self.id = MeasureId(self.id)

        if self._is_empty(self.code):
            self.MissingRequiredField("code")
        if not isinstance(self.code, Code):
            self.code = Code(self.code)

        if self._is_empty(self.name):
            self.MissingRequiredField("name")
        if not isinstance(self.name, str):
            self.name = str(self.name)

        if self._is_empty(self.units):
            self.MissingRequiredField("units")
        if not isinstance(self.units, str):
            self.units = str(self.units)

        if self.definition is not None and not isinstance(self.definition, str):
            self.definition = str(self.definition)

        if not isinstance(self.tags, list):
            self.tags = [self.tags] if self.tags is not None else []
        self.tags = [v if isinstance(v, str) else str(v) for v in self.tags]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Measurement(YAMLRoot):
    """
    An identified measurable property with a Measure and an optional Quantity.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Measurement"]
    class_class_curie: ClassVar[str] = "rk:Measurement"
    class_name: ClassVar[str] = "Measurement"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Measurement")

    id: Union[str, MeasurementId] = None
    measure: Union[str, MeasureId] = None
    quantity: Optional[Union[dict, Quantity]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, MeasurementId):
            self.id = MeasurementId(self.id)

        if self._is_empty(self.measure):
            self.MissingRequiredField("measure")
        if not isinstance(self.measure, MeasureId):
            self.measure = MeasureId(self.measure)

        if self.quantity is not None and not isinstance(self.quantity, Quantity):
            self.quantity = Quantity(**as_dict(self.quantity))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Classification(YAMLRoot):
    """
    A named definition node in a taxonomy hierarchy.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Classification"]
    class_class_curie: ClassVar[str] = "rk:Classification"
    class_name: ClassVar[str] = "Classification"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Classification")

    id: Union[str, ClassificationId] = None
    code: Union[str, Code] = None
    name: str = None
    definition: Optional[str] = None
    parent: Optional[Union[str, ClassificationId]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, ClassificationId):
            self.id = ClassificationId(self.id)

        if self._is_empty(self.code):
            self.MissingRequiredField("code")
        if not isinstance(self.code, Code):
            self.code = Code(self.code)

        if self._is_empty(self.name):
            self.MissingRequiredField("name")
        if not isinstance(self.name, str):
            self.name = str(self.name)

        if self.definition is not None and not isinstance(self.definition, str):
            self.definition = str(self.definition)

        if self.parent is not None and not isinstance(self.parent, ClassificationId):
            self.parent = ClassificationId(self.parent)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Taxonomy(YAMLRoot):
    """
    A named, single-root hierarchy of Classifications.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Taxonomy"]
    class_class_curie: ClassVar[str] = "rk:Taxonomy"
    class_name: ClassVar[str] = "Taxonomy"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Taxonomy")

    id: Union[str, TaxonomyId] = None
    code: Union[str, Code] = None
    name: str = None
    classifications: Union[dict[Union[str, ClassificationId], Union[dict, Classification]], list[Union[dict, Classification]]] = empty_dict()
    definition: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, TaxonomyId):
            self.id = TaxonomyId(self.id)

        if self._is_empty(self.code):
            self.MissingRequiredField("code")
        if not isinstance(self.code, Code):
            self.code = Code(self.code)

        if self._is_empty(self.name):
            self.MissingRequiredField("name")
        if not isinstance(self.name, str):
            self.name = str(self.name)

        if self._is_empty(self.classifications):
            self.MissingRequiredField("classifications")
        self._normalize_inlined_as_list(slot_name="classifications", slot_type=Classification, key_name="id", keyed=True)

        if self.definition is not None and not isinstance(self.definition, str):
            self.definition = str(self.definition)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Domain(YAMLRoot):
    """
    The permitted content of an argument or result, including its kind, compatible units, measurement meaning, and
    collection elements where applicable.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Domain"]
    class_class_curie: ClassVar[str] = "rk:Domain"
    class_name: ClassVar[str] = "Domain"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Domain")

    kind: Union[str, "DomainKind"] = None
    units: Optional[str] = None
    measure: Optional[Union[str, MeasureId]] = None
    item_domain: Optional[Union[dict, "Domain"]] = None
    collection_kind: Optional[Union[str, "CollectionKind"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.kind):
            self.MissingRequiredField("kind")
        if not isinstance(self.kind, DomainKind):
            self.kind = DomainKind(self.kind)

        if self.units is not None and not isinstance(self.units, str):
            self.units = str(self.units)

        if self.measure is not None and not isinstance(self.measure, MeasureId):
            self.measure = MeasureId(self.measure)

        if self.item_domain is not None and not isinstance(self.item_domain, Domain):
            self.item_domain = Domain(**as_dict(self.item_domain))

        if self.collection_kind is not None and not isinstance(self.collection_kind, CollectionKind):
            self.collection_kind = CollectionKind(self.collection_kind)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Parameter(YAMLRoot):
    """
    A named argument in a Function signature. List order determines positional argument order.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Parameter"]
    class_class_curie: ClassVar[str] = "rk:Parameter"
    class_name: ClassVar[str] = "Parameter"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Parameter")

    name: Union[str, Code] = None
    domain: Union[dict, Domain] = None
    kind: Union[str, "ParameterKind"] = None
    required: Union[bool, Bool] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.name):
            self.MissingRequiredField("name")
        if not isinstance(self.name, Code):
            self.name = Code(self.name)

        if self._is_empty(self.domain):
            self.MissingRequiredField("domain")
        if not isinstance(self.domain, Domain):
            self.domain = Domain(**as_dict(self.domain))

        if self._is_empty(self.kind):
            self.MissingRequiredField("kind")
        if not isinstance(self.kind, ParameterKind):
            self.kind = ParameterKind(self.kind)

        if self._is_empty(self.required):
            self.MissingRequiredField("required")
        if not isinstance(self.required, Bool):
            self.required = Bool(self.required)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Function(YAMLRoot):
    """
    An identified, versioned contract for a pure mathematical or domain function, independent of a particular runtime
    implementation.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Function"]
    class_class_curie: ClassVar[str] = "rk:Function"
    class_name: ClassVar[str] = "Function"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Function")

    id: Union[str, FunctionId] = None
    code: Union[str, Code] = None
    name: str = None
    version: Union[str, Code] = None
    result: Union[dict, Domain] = None
    semantics: str = None
    unit_rule: str = None
    parameters: Optional[Union[Union[dict, Parameter], list[Union[dict, Parameter]]]] = empty_list()
    empty_collection: Optional[Union[str, "EmptyHandling"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, FunctionId):
            self.id = FunctionId(self.id)

        if self._is_empty(self.code):
            self.MissingRequiredField("code")
        if not isinstance(self.code, Code):
            self.code = Code(self.code)

        if self._is_empty(self.name):
            self.MissingRequiredField("name")
        if not isinstance(self.name, str):
            self.name = str(self.name)

        if self._is_empty(self.version):
            self.MissingRequiredField("version")
        if not isinstance(self.version, Code):
            self.version = Code(self.version)

        if self._is_empty(self.result):
            self.MissingRequiredField("result")
        if not isinstance(self.result, Domain):
            self.result = Domain(**as_dict(self.result))

        if self._is_empty(self.semantics):
            self.MissingRequiredField("semantics")
        if not isinstance(self.semantics, str):
            self.semantics = str(self.semantics)

        if self._is_empty(self.unit_rule):
            self.MissingRequiredField("unit_rule")
        if not isinstance(self.unit_rule, str):
            self.unit_rule = str(self.unit_rule)

        self._normalize_inlined_as_list(slot_name="parameters", slot_type=Parameter, key_name="name", keyed=False)

        if self.empty_collection is not None and not isinstance(self.empty_collection, EmptyHandling):
            self.empty_collection = EmptyHandling(self.empty_collection)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Constraint(YAMLRoot):
    """
    An identified requirement that a referenced Boolean Expression be true in the context where the Constraint is
    imposed.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Constraint"]
    class_class_curie: ClassVar[str] = "rk:Constraint"
    class_name: ClassVar[str] = "Constraint"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Constraint")

    id: Union[str, ConstraintId] = None
    predicate: Union[str, ExpressionId] = None
    code: Optional[Union[str, Code]] = None
    name: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, ConstraintId):
            self.id = ConstraintId(self.id)

        if self._is_empty(self.predicate):
            self.MissingRequiredField("predicate")
        if not isinstance(self.predicate, ExpressionId):
            self.predicate = ExpressionId(self.predicate)

        if self.code is not None and not isinstance(self.code, Code):
            self.code = Code(self.code)

        if self.name is not None and not isinstance(self.name, str):
            self.name = str(self.name)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Expression(YAMLRoot):
    """
    An identified mathematical expression. Its kind determines its content; nested expressions retain order and UUID
    references resolve in the applicable Model or composed Specification scope.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Expression"]
    class_class_curie: ClassVar[str] = "rk:Expression"
    class_name: ClassVar[str] = "Expression"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Expression")

    id: Union[str, ExpressionId] = None
    kind: Union[str, "ExpressionKind"] = None
    quantity: Optional[Union[dict, Quantity]] = None
    boolean: Optional[Union[bool, Bool]] = None
    target: Optional[Union[str, ValueId]] = None
    operator: Optional[Union[str, "Operator"]] = None
    operands: Optional[Union[dict[Union[str, ExpressionId], Union[dict, "Expression"]], list[Union[dict, "Expression"]]]] = empty_dict()
    operand: Optional[Union[dict, "Expression"]] = None
    call: Optional[Union[dict, "Call"]] = None
    selection: Optional[Union[dict, "Selection"]] = None
    query: Optional[Union[dict, "Query"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, ExpressionId):
            self.id = ExpressionId(self.id)

        if self._is_empty(self.kind):
            self.MissingRequiredField("kind")
        if not isinstance(self.kind, ExpressionKind):
            self.kind = ExpressionKind(self.kind)

        if self.quantity is not None and not isinstance(self.quantity, Quantity):
            self.quantity = Quantity(**as_dict(self.quantity))

        if self.boolean is not None and not isinstance(self.boolean, Bool):
            self.boolean = Bool(self.boolean)

        if self.target is not None and not isinstance(self.target, ValueId):
            self.target = ValueId(self.target)

        if self.operator is not None and not isinstance(self.operator, Operator):
            self.operator = Operator(self.operator)

        self._normalize_inlined_as_list(slot_name="operands", slot_type=Expression, key_name="id", keyed=True)

        if self.operand is not None and not isinstance(self.operand, Expression):
            self.operand = Expression(**as_dict(self.operand))

        if self.call is not None and not isinstance(self.call, Call):
            self.call = Call(**as_dict(self.call))

        if self.selection is not None and not isinstance(self.selection, Selection):
            self.selection = Selection(**as_dict(self.selection))

        if self.query is not None and not isinstance(self.query, Query):
            self.query = Query(**as_dict(self.query))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Call(YAMLRoot):
    """
    Application of an identified Function to positional and named expression arguments.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Call"]
    class_class_curie: ClassVar[str] = "rk:Call"
    class_name: ClassVar[str] = "Call"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Call")

    function: Union[str, FunctionId] = None
    arguments: Optional[Union[dict[Union[str, ExpressionId], Union[dict, Expression]], list[Union[dict, Expression]]]] = empty_dict()
    named_arguments: Optional[Union[Union[dict, "Argument"], list[Union[dict, "Argument"]]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.function):
            self.MissingRequiredField("function")
        if not isinstance(self.function, FunctionId):
            self.function = FunctionId(self.function)

        self._normalize_inlined_as_list(slot_name="arguments", slot_type=Expression, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="named_arguments", slot_type=Argument, key_name="name", keyed=False)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Argument(YAMLRoot):
    """
    One named expression argument in a Function call.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Argument"]
    class_class_curie: ClassVar[str] = "rk:Argument"
    class_name: ClassVar[str] = "Argument"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Argument")

    name: Union[str, Code] = None
    expression: Union[dict, Expression] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.name):
            self.MissingRequiredField("name")
        if not isinstance(self.name, Code):
            self.name = Code(self.name)

        if self._is_empty(self.expression):
            self.MissingRequiredField("expression")
        if not isinstance(self.expression, Expression):
            self.expression = Expression(**as_dict(self.expression))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Selection(YAMLRoot):
    """
    Read a declared member or indexed element from structured expression content.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Selection"]
    class_class_curie: ClassVar[str] = "rk:Selection"
    class_name: ClassVar[str] = "Selection"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Selection")

    kind: Union[str, "SelectionKind"] = None
    base: Union[dict, Expression] = None
    member: Optional[Union[str, Code]] = None
    index: Optional[Union[dict, Expression]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.kind):
            self.MissingRequiredField("kind")
        if not isinstance(self.kind, SelectionKind):
            self.kind = SelectionKind(self.kind)

        if self._is_empty(self.base):
            self.MissingRequiredField("base")
        if not isinstance(self.base, Expression):
            self.base = Expression(**as_dict(self.base))

        if self.member is not None and not isinstance(self.member, Code):
            self.member = Code(self.member)

        if self.index is not None and not isinstance(self.index, Expression):
            self.index = Expression(**as_dict(self.index))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Relationship(YAMLRoot):
    """
    An identified, directed connection from one Entity to another. Its classification describes the connection; its
    characteristics describe properties of the connection itself.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Relationship"]
    class_class_curie: ClassVar[str] = "rk:Relationship"
    class_name: ClassVar[str] = "Relationship"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Relationship")

    id: Union[str, RelationshipId] = None
    classification: Union[str, ClassificationId] = None
    source: Union[str, EntityId] = None
    target: Union[str, EntityId] = None
    characteristics: Optional[Union[dict, "Characteristics"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, RelationshipId):
            self.id = RelationshipId(self.id)

        if self._is_empty(self.classification):
            self.MissingRequiredField("classification")
        if not isinstance(self.classification, ClassificationId):
            self.classification = ClassificationId(self.classification)

        if self._is_empty(self.source):
            self.MissingRequiredField("source")
        if not isinstance(self.source, EntityId):
            self.source = EntityId(self.source)

        if self._is_empty(self.target):
            self.MissingRequiredField("target")
        if not isinstance(self.target, EntityId):
            self.target = EntityId(self.target)

        if self.characteristics is not None and not isinstance(self.characteristics, Characteristics):
            self.characteristics = Characteristics(**as_dict(self.characteristics))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Traversal(YAMLRoot):
    """
    One traversal step over domain Relationships or Assembly membership.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Traversal"]
    class_class_curie: ClassVar[str] = "rk:Traversal"
    class_name: ClassVar[str] = "Traversal"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Traversal")

    kind: Union[str, "TraversalKind"] = None
    depth: Union[str, "Depth"] = None
    classification: Optional[Union[str, ClassificationId]] = None
    direction: Optional[Union[str, "Direction"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.kind):
            self.MissingRequiredField("kind")
        if not isinstance(self.kind, TraversalKind):
            self.kind = TraversalKind(self.kind)

        if self._is_empty(self.depth):
            self.MissingRequiredField("depth")
        if not isinstance(self.depth, Depth):
            self.depth = Depth(self.depth)

        if self.classification is not None and not isinstance(self.classification, ClassificationId):
            self.classification = ClassificationId(self.classification)

        if self.direction is not None and not isinstance(self.direction, Direction):
            self.direction = Direction(self.direction)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Criterion(YAMLRoot):
    """
    Require an Entity Label with this owner-local key to include the exact Classification.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Criterion"]
    class_class_curie: ClassVar[str] = "rk:Criterion"
    class_name: ClassVar[str] = "Criterion"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Criterion")

    key: str = None
    classification: Union[str, ClassificationId] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.key):
            self.MissingRequiredField("key")
        if not isinstance(self.key, str):
            self.key = str(self.key)

        if self._is_empty(self.classification):
            self.MissingRequiredField("classification")
        if not isinstance(self.classification, ClassificationId):
            self.classification = ClassificationId(self.classification)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Filter(YAMLRoot):
    """
    Conjunctive filters over fixed Entity metadata. No numerical expression or solved amount determines membership.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Filter"]
    class_class_curie: ClassVar[str] = "rk:Filter"
    class_name: ClassVar[str] = "Filter"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Filter")

    classification: Optional[Union[str, ClassificationId]] = None
    labels: Optional[Union[Union[dict, Criterion], list[Union[dict, Criterion]]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.classification is not None and not isinstance(self.classification, ClassificationId):
            self.classification = ClassificationId(self.classification)

        self._normalize_inlined_as_list(slot_name="labels", slot_type=Criterion, key_name="key", keyed=False)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Projection(YAMLRoot):
    """
    Select Entity identities or Values belonging to each matching Entity.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Projection"]
    class_class_curie: ClassVar[str] = "rk:Projection"
    class_name: ClassVar[str] = "Projection"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Projection")

    kind: Union[str, "ProjectionKind"] = None
    key: Optional[str] = None
    measure: Optional[Union[str, MeasureId]] = None
    cardinality: Optional[Union[str, "Cardinality"]] = None
    missing: Optional[Union[str, "MissingHandling"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.kind):
            self.MissingRequiredField("kind")
        if not isinstance(self.kind, ProjectionKind):
            self.kind = ProjectionKind(self.kind)

        if self.key is not None and not isinstance(self.key, str):
            self.key = str(self.key)

        if self.measure is not None and not isinstance(self.measure, MeasureId):
            self.measure = MeasureId(self.measure)

        if self.cardinality is not None and not isinstance(self.cardinality, Cardinality):
            self.cardinality = Cardinality(self.cardinality)

        if self.missing is not None and not isinstance(self.missing, MissingHandling):
            self.missing = MissingHandling(self.missing)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Query(YAMLRoot):
    """
    A non-executing query specification returning Entity or Value identities from the containing Model revision.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Query"]
    class_class_curie: ClassVar[str] = "rk:Query"
    class_name: ClassVar[str] = "Query"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Query")

    starting_at: Union[str, EntityId] = None
    projection: Union[dict, Projection] = None
    duplicates: Union[str, "DuplicateHandling"] = None
    steps: Optional[Union[Union[dict, Traversal], list[Union[dict, Traversal]]]] = empty_list()
    filter: Optional[Union[dict, Filter]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.starting_at):
            self.MissingRequiredField("starting_at")
        if not isinstance(self.starting_at, EntityId):
            self.starting_at = EntityId(self.starting_at)

        if self._is_empty(self.projection):
            self.MissingRequiredField("projection")
        if not isinstance(self.projection, Projection):
            self.projection = Projection(**as_dict(self.projection))

        if self._is_empty(self.duplicates):
            self.MissingRequiredField("duplicates")
        if not isinstance(self.duplicates, DuplicateHandling):
            self.duplicates = DuplicateHandling(self.duplicates)

        self._normalize_inlined_as_list(slot_name="steps", slot_type=Traversal, key_name="kind", keyed=False)

        if self.filter is not None and not isinstance(self.filter, Filter):
            self.filter = Filter(**as_dict(self.filter))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Entity(YAMLRoot):
    """
    An identifiable domain object, such as an apartment, building, or actor. Its identity persists across immutable
    Model revisions. Loading its definition does not execute calculations.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Entity"]
    class_class_curie: ClassVar[str] = "rk:Entity"
    class_name: ClassVar[str] = "Entity"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Entity")

    id: Union[str, EntityId] = None
    classification: Optional[Union[str, ClassificationId]] = None
    code: Optional[Union[str, Code]] = None
    name: Optional[str] = None
    characteristics: Optional[Union[dict, "Characteristics"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, EntityId):
            self.id = EntityId(self.id)

        if self.classification is not None and not isinstance(self.classification, ClassificationId):
            self.classification = ClassificationId(self.classification)

        if self.code is not None and not isinstance(self.code, Code):
            self.code = Code(self.code)

        if self.name is not None and not isinstance(self.name, str):
            self.name = str(self.name)

        if self.characteristics is not None and not isinstance(self.characteristics, Characteristics):
            self.characteristics = Characteristics(**as_dict(self.characteristics))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Assembly(Entity):
    """
    An Entity identifying a collection of Entities and Relationships. Members are referenced by identity and may
    belong to more than one Assembly. Membership does not imply spatial containment or duplicate its members.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Assembly"]
    class_class_curie: ClassVar[str] = "rk:Assembly"
    class_name: ClassVar[str] = "Assembly"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Assembly")

    id: Union[str, AssemblyId] = None
    entities: Optional[Union[Union[str, EntityId], list[Union[str, EntityId]]]] = empty_list()
    relationships: Optional[Union[Union[str, RelationshipId], list[Union[str, RelationshipId]]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, AssemblyId):
            self.id = AssemblyId(self.id)

        if not isinstance(self.entities, list):
            self.entities = [self.entities] if self.entities is not None else []
        self.entities = [v if isinstance(v, EntityId) else EntityId(v) for v in self.entities]

        if not isinstance(self.relationships, list):
            self.relationships = [self.relationships] if self.relationships is not None else []
        self.relationships = [v if isinstance(v, RelationshipId) else RelationshipId(v) for v in self.relationships]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Characteristics(YAMLRoot):
    """
    A collection of Labels and Values belonging to an Entity or Relationship. Each Label or Value has a stable UUID
    and a key unique within its collection.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Characteristics"]
    class_class_curie: ClassVar[str] = "rk:Characteristics"
    class_name: ClassVar[str] = "Characteristics"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Characteristics")

    labels: Optional[Union[dict[Union[str, LabelId], Union[dict, "Label"]], list[Union[dict, "Label"]]]] = empty_dict()
    values: Optional[Union[dict[Union[str, ValueId], Union[dict, "Value"]], list[Union[dict, "Value"]]]] = empty_dict()

    def __post_init__(self, *_: str, **kwargs: Any):
        self._normalize_inlined_as_list(slot_name="labels", slot_type=Label, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="values", slot_type=Value, key_name="id", keyed=True)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Label(YAMLRoot):
    """
    A named set of Classifications describing an aspect of an Entity or Relationship.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Label"]
    class_class_curie: ClassVar[str] = "rk:Label"
    class_name: ClassVar[str] = "Label"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Label")

    id: Union[str, LabelId] = None
    key: str = None
    classifications: Optional[Union[Union[str, ClassificationId], list[Union[str, ClassificationId]]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, LabelId):
            self.id = LabelId(self.id)

        if self._is_empty(self.key):
            self.MissingRequiredField("key")
        if not isinstance(self.key, str):
            self.key = str(self.key)

        if not isinstance(self.classifications, list):
            self.classifications = [self.classifications] if self.classifications is not None else []
        self.classifications = [v if isinstance(v, ClassificationId) else ClassificationId(v) for v in self.classifications]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Value(YAMLRoot):
    """
    An identified, typed Value belonging to an Entity or Relationship's Characteristics, or declared locally within a
    mathematical Formulation. Its key provides a name within the owner's values collection; its UUID identifies the
    symbol independently of that name.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Value"]
    class_class_curie: ClassVar[str] = "rk:Value"
    class_name: ClassVar[str] = "Value"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Value")

    id: Union[str, ValueId] = None
    measure: Union[str, MeasureId] = None
    key: str = None
    kind: Union[str, "ValueKind"] = None
    quantity: Optional[Union[dict, Quantity]] = None
    description: Optional[str] = None
    flow: Optional[Union[dict, "Flow"]] = None
    content: Optional[Union[dict, "PropertyContent"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, ValueId):
            self.id = ValueId(self.id)

        if self._is_empty(self.measure):
            self.MissingRequiredField("measure")
        if not isinstance(self.measure, MeasureId):
            self.measure = MeasureId(self.measure)

        if self._is_empty(self.key):
            self.MissingRequiredField("key")
        if not isinstance(self.key, str):
            self.key = str(self.key)

        if self._is_empty(self.kind):
            self.MissingRequiredField("kind")
        if not isinstance(self.kind, ValueKind):
            self.kind = ValueKind(self.kind)

        if self.quantity is not None and not isinstance(self.quantity, Quantity):
            self.quantity = Quantity(**as_dict(self.quantity))

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.flow is not None and not isinstance(self.flow, Flow):
            self.flow = Flow(**as_dict(self.flow))

        if self.content is not None and not isinstance(self.content, PropertyContent):
            self.content = PropertyContent(**as_dict(self.content))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Flow(YAMLRoot):
    """
    Ordered temporal quantities owned by one Value. Dates are coordinates, not units. Empty, unresolved and zero
    movements are distinct. The overall model logic defines the meaning of the quantities and selects their
    calculations; a Flow carries no semantic kind or basis.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Flow"]
    class_class_curie: ClassVar[str] = "rk:Flow"
    class_name: ClassVar[str] = "Flow"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Flow")

    units: str = None
    movements: Union[Union[dict, "Movement"], list[Union[dict, "Movement"]]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.units):
            self.MissingRequiredField("units")
        if not isinstance(self.units, str):
            self.units = str(self.units)

        if self._is_empty(self.movements):
            self.MissingRequiredField("movements")
        self._normalize_inlined_as_list(slot_name="movements", slot_type=Movement, key_name="key", keyed=False)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Movement(YAMLRoot):
    """
    One numerical entry in a Flow, associated with a date or period. The overall model logic determines its meaning.
    At least one of date or period is required. With a period, date records an independent payment or observation date
    and need not lie inside the period. Derived boundary dates are calculated, not stored. Key is stable within its
    Flow; repeated event dates require distinct keys. Magnitude omission/null means unresolved. Claims retain source
    or derivation evidence.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Movement"]
    class_class_curie: ClassVar[str] = "rk:Movement"
    class_name: ClassVar[str] = "Movement"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Movement")

    key: str = None
    date: Optional[Union[str, XSDDate]] = None
    period: Optional[Union[dict, "Period"]] = None
    magnitude: Optional[Decimal] = None
    claims: Optional[Union[Union[str, UUID], list[Union[str, UUID]]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.key):
            self.MissingRequiredField("key")
        if not isinstance(self.key, str):
            self.key = str(self.key)

        if self.date is not None and not isinstance(self.date, XSDDate):
            self.date = XSDDate(self.date)

        if self.period is not None and not isinstance(self.period, Period):
            self.period = Period(**as_dict(self.period))

        if self.magnitude is not None and not isinstance(self.magnitude, Decimal):
            self.magnitude = Decimal(self.magnitude)

        if not isinstance(self.claims, list):
            self.claims = [self.claims] if self.claims is not None else []
        self.claims = [v if isinstance(v, UUID) else UUID(v) for v in self.claims]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class PropertyContent(YAMLRoot):
    """
    Tagged inert content. Scalar text preserves exact type and representation, including negative zero. Containers
    never instantiate arbitrary Python classes. Conditional shape and canonical scalar grammar are checked
    semantically.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["PropertyContent"]
    class_class_curie: ClassVar[str] = "rk:PropertyContent"
    class_name: ClassVar[str] = "PropertyContent"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/PropertyContent")

    kind: Union[str, "ContentKind"] = None
    text: Optional[str] = None
    zone: Optional[str] = None
    fold: Optional[int] = None
    items: Optional[Union[Union[dict, "PropertyContent"], list[Union[dict, "PropertyContent"]]]] = empty_list()
    entries: Optional[Union[Union[dict, "ContentEntry"], list[Union[dict, "ContentEntry"]]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.kind):
            self.MissingRequiredField("kind")
        if not isinstance(self.kind, ContentKind):
            self.kind = ContentKind(self.kind)

        if self.text is not None and not isinstance(self.text, str):
            self.text = str(self.text)

        if self.zone is not None and not isinstance(self.zone, str):
            self.zone = str(self.zone)

        if self.fold is not None and not isinstance(self.fold, int):
            self.fold = int(self.fold)

        self._normalize_inlined_as_list(slot_name="items", slot_type=PropertyContent, key_name="kind", keyed=False)

        if not isinstance(self.entries, list):
            self.entries = [self.entries] if self.entries is not None else []
        self.entries = [v if isinstance(v, ContentEntry) else ContentEntry(**as_dict(v)) for v in self.entries]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class ContentEntry(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["ContentEntry"]
    class_class_curie: ClassVar[str] = "rk:ContentEntry"
    class_name: ClassVar[str] = "ContentEntry"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/ContentEntry")

    key: Union[dict, PropertyContent] = None
    value: Union[dict, PropertyContent] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.key):
            self.MissingRequiredField("key")
        if not isinstance(self.key, PropertyContent):
            self.key = PropertyContent(**as_dict(self.key))

        if self._is_empty(self.value):
            self.MissingRequiredField("value")
        if not isinstance(self.value, PropertyContent):
            self.value = PropertyContent(**as_dict(self.value))

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Period(YAMLRoot):
    """
    Half-open interval [start, end). Date boundaries use the Gregorian calendar; start must precede end.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Period"]
    class_class_curie: ClassVar[str] = "rk:Period"
    class_name: ClassVar[str] = "Period"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Period")

    start: Union[str, XSDDate] = None
    end: Union[str, XSDDate] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.start):
            self.MissingRequiredField("start")
        if not isinstance(self.start, XSDDate):
            self.start = XSDDate(self.start)

        if self._is_empty(self.end):
            self.MissingRequiredField("end")
        if not isinstance(self.end, XSDDate):
            self.end = XSDDate(self.end)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Span(Period):
    """
    Named extent, using the same half-open boundary convention as Period.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = RK["Span"]
    class_class_curie: ClassVar[str] = "rk:Span"
    class_name: ClassVar[str] = "Span"
    class_model_uri: ClassVar[URIRef] = URIRef("https://daniel-fink.github.io/rangekeeper/schema/bundle/Span")

    start: Union[str, XSDDate] = None
    end: Union[str, XSDDate] = None
    name: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.name is not None and not isinstance(self.name, str):
            self.name = str(self.name)

        super().__post_init__(**kwargs)


# Enumerations
class ObjectiveKind(EnumDefinitionImpl):

    minimize = PermissibleValue(
        text="minimize",
        description="Prefer smaller results of the objective Expression.")
    maximize = PermissibleValue(
        text="maximize",
        description="Prefer larger results of the objective Expression.")

    _defn = EnumDefinition(
        name="ObjectiveKind",
    )

class CompletionStatus(EnumDefinitionImpl):

    completed = PermissibleValue(
        text="completed",
        description="The attempt completed normally; this does not imply mathematical feasibility.")
    limited = PermissibleValue(
        text="limited",
        description="An execution limit stopped the attempt.")
    partial = PermissibleValue(
        text="partial",
        description="Some direct batch cases completed and others did not.")
    failed = PermissibleValue(
        text="failed",
        description="An error or unsupported capability prevented completion.")
    cancelled = PermissibleValue(
        text="cancelled",
        description="The attempt was cancelled.")
    skipped = PermissibleValue(
        text="skipped",
        description="The attempt was not started.")

    _defn = EnumDefinition(
        name="CompletionStatus",
    )

class SolutionStatus(EnumDefinitionImpl):

    feasible = PermissibleValue(
        text="feasible",
        description="""Published output satisfies the investigation requirements under recorded checking conventions; optimality is not implied.""")
    infeasible = PermissibleValue(
        text="infeasible",
        description="The investigation was established to be infeasible by the recorded method.")
    unknown = PermissibleValue(
        text="unknown",
        description="No accepted mathematical conclusion was established.")
    not_assessed = PermissibleValue(
        text="not_assessed",
        description="Mathematical feasibility was not assessed.")
    not_applicable = PermissibleValue(
        text="not_applicable",
        description="The Run aggregates case outcomes rather than asserting one mathematical conclusion.")

    _defn = EnumDefinition(
        name="SolutionStatus",
    )

class ImplementationKind(EnumDefinitionImpl):

    evaluator = PermissibleValue(
        text="evaluator",
        description="Evaluates a supported formulation or computation.")
    compiler = PermissibleValue(
        text="compiler",
        description="Translates definitions into an executable or solver representation.")
    solver = PermissibleValue(
        text="solver",
        description="Attempts a numerical solution or optimization.")

    _defn = EnumDefinition(
        name="ImplementationKind",
    )

class Severity(EnumDefinitionImpl):

    info = PermissibleValue(
        text="info",
        description="Informational finding.")
    warning = PermissibleValue(
        text="warning",
        description="Limitation or condition affecting interpretation.")
    error = PermissibleValue(
        text="error",
        description="Failure requiring attention.")

    _defn = EnumDefinition(
        name="Severity",
    )

class StepKind(EnumDefinitionImpl):

    validation = PermissibleValue(
        text="validation",
        description="Validation of inputs, requirements, or results.")
    formulation = PermissibleValue(
        text="formulation",
        description="Construction or translation of the executable mathematics.")
    solve = PermissibleValue(
        text="solve",
        description="Execution of a numerical evaluation or solve.")
    publication = PermissibleValue(
        text="publication",
        description="Publication of an accepted output Model.")
    selection = PermissibleValue(
        text="selection",
        description="Selection of an accepted candidate, with method and basis.")

    _defn = EnumDefinition(
        name="StepKind",
    )

class ClaimKind(EnumDefinitionImpl):

    sourced = PermissibleValue(
        text="sourced",
        description="Content obtained at a source location.")
    asserted = PermissibleValue(
        text="asserted",
        description="Content supplied through a named method.")
    derived = PermissibleValue(
        text="derived",
        description="Content derived from upstream Claims through a named method.")

    _defn = EnumDefinition(
        name="ClaimKind",
    )

class ReconciliationStatus(EnumDefinitionImpl):

    provisional = PermissibleValue(
        text="provisional",
        description="The selection remains provisional.")
    confirmed = PermissibleValue(
        text="confirmed",
        description="The selection is confirmed.")

    _defn = EnumDefinition(
        name="ReconciliationStatus",
    )

class DomainKind(EnumDefinitionImpl):

    number = PermissibleValue(
        text="number",
        description="Dimensionless numerical content.")
    quantity = PermissibleValue(
        text="quantity",
        description="Numerical content with units, without a required Measure.")
    measurement = PermissibleValue(
        text="measurement",
        description="Numerical content with a Measure.")
    boolean = PermissibleValue(
        text="boolean",
        description="Boolean content.")
    string = PermissibleValue(
        text="string",
        description="Text content.")
    date = PermissibleValue(
        text="date",
        description="A calendar date.")
    span = PermissibleValue(
        text="span",
        description="A time interval with defined endpoint members.")
    flow = PermissibleValue(
        text="flow",
        description="A time-indexed flow.")
    stream = PermissibleValue(
        text="stream",
        description="A collection of flows with declared combination semantics.")
    account = PermissibleValue(
        text="account",
        description="A financial account with declared members.")
    entity = PermissibleValue(
        text="entity",
        description="An Entity identity.")
    collection = PermissibleValue(
        text="collection",
        description="A collection of elements within the specified item domain.")

    _defn = EnumDefinition(
        name="DomainKind",
    )

class CollectionKind(EnumDefinitionImpl):

    set = PermissibleValue(
        text="set",
        description="Unordered distinct elements.")
    bag = PermissibleValue(
        text="bag",
        description="Unordered elements retaining multiplicity.")
    sequence = PermissibleValue(
        text="sequence",
        description="Ordered elements retaining multiplicity.")

    _defn = EnumDefinition(
        name="CollectionKind",
    )

class ParameterKind(EnumDefinitionImpl):

    positional_or_named = PermissibleValue(
        text="positional_or_named",
        description="Supply by position or by name, but not both.")
    named_only = PermissibleValue(
        text="named_only",
        description="Supply by name only.")

    _defn = EnumDefinition(
        name="ParameterKind",
    )

class EmptyHandling(EnumDefinitionImpl):

    error = PermissibleValue(
        text="error",
        description="Reject an empty collection.")
    zero = PermissibleValue(
        text="zero",
        description="Return zero in the declared or otherwise established result units.")

    _defn = EnumDefinition(
        name="EmptyHandling",
    )

class ExpressionKind(EnumDefinitionImpl):

    quantity = PermissibleValue(
        text="quantity",
        description="A numerical literal with explicit magnitude and units.")
    boolean = PermissibleValue(
        text="boolean",
        description="A Boolean literal.")
    reference = PermissibleValue(
        text="reference",
        description="A symbolic Value reference.")
    unary = PermissibleValue(
        text="unary",
        description="A unary operation.")
    binary = PermissibleValue(
        text="binary",
        description="A binary operation with ordered operands.")
    call = PermissibleValue(
        text="call",
        description="A call to an identified Function.")
    selection = PermissibleValue(
        text="selection",
        description="Member or index selection from another expression.")
    query = PermissibleValue(
        text="query",
        description="A query returning a collection of symbolic references.")

    _defn = EnumDefinition(
        name="ExpressionKind",
    )

class Operator(EnumDefinitionImpl):

    add = PermissibleValue(
        text="add",
        description="First operand plus second operand.")
    subtract = PermissibleValue(
        text="subtract",
        description="First operand minus second operand.")
    multiply = PermissibleValue(
        text="multiply",
        description="First operand multiplied by second operand.")
    divide = PermissibleValue(
        text="divide",
        description="First operand divided by second operand.")
    equal = PermissibleValue(
        text="equal",
        description="Whether the operands are equal; this is not assignment.")
    not_equal = PermissibleValue(
        text="not_equal",
        description="Whether the operands differ.")
    less_than = PermissibleValue(
        text="less_than",
        description="Whether the first operand is less than the second.")
    less_than_or_equal = PermissibleValue(
        text="less_than_or_equal",
        description="Whether the first operand is less than or equal to the second.")
    greater_than = PermissibleValue(
        text="greater_than",
        description="Whether the first operand is greater than the second.")
    greater_than_or_equal = PermissibleValue(
        text="greater_than_or_equal",
        description="Whether the first operand is greater than or equal to the second.")
    power = PermissibleValue(
        text="power",
        description="First operand raised to the second.")
    negate = PermissibleValue(
        text="negate",
        description="Numerical negation of one operand.")
    logical_not = PermissibleValue(
        text="logical_not",
        description="Boolean negation of one operand.")
    logical_and = PermissibleValue(
        text="logical_and",
        description="Boolean conjunction, evaluated left to right with short-circuiting.")
    logical_or = PermissibleValue(
        text="logical_or",
        description="Boolean disjunction, evaluated left to right with short-circuiting.")

    _defn = EnumDefinition(
        name="Operator",
    )

class SelectionKind(EnumDefinitionImpl):

    member = PermissibleValue(
        text="member",
        description="Select one declared member.")
    index = PermissibleValue(
        text="index",
        description="Select one indexed element.")

    _defn = EnumDefinition(
        name="SelectionKind",
    )

class TraversalKind(EnumDefinitionImpl):

    relationship = PermissibleValue(
        text="relationship",
        description="Traverse classified domain Relationships.")
    membership = PermissibleValue(
        text="membership",
        description="Traverse Assembly entity membership.")

    _defn = EnumDefinition(
        name="TraversalKind",
    )

class Depth(EnumDefinitionImpl):

    direct = PermissibleValue(
        text="direct",
        description="Exactly one edge.")
    transitive = PermissibleValue(
        text="transitive",
        description="One or more edges along finite simple paths.")

    _defn = EnumDefinition(
        name="Depth",
    )

class Direction(EnumDefinitionImpl):

    outgoing = PermissibleValue(
        text="outgoing",
        description="Follow source to target.")
    incoming = PermissibleValue(
        text="incoming",
        description="Follow target to source.")

    _defn = EnumDefinition(
        name="Direction",
    )

class ProjectionKind(EnumDefinitionImpl):

    entity = PermissibleValue(
        text="entity",
        description="Return matching Entity identities.")
    value = PermissibleValue(
        text="value",
        description="Return identified Values selected from matching Entities.")

    _defn = EnumDefinition(
        name="ProjectionKind",
    )

class Cardinality(EnumDefinitionImpl):

    one = PermissibleValue(
        text="one",
        description="At most one Value per Entity; multiple matches are an error.")
    many = PermissibleValue(
        text="many",
        description="All matching Values per Entity.")

    _defn = EnumDefinition(
        name="Cardinality",
    )

class MissingHandling(EnumDefinitionImpl):

    error = PermissibleValue(
        text="error",
        description="Reject an Entity with no matching Value.")
    omit = PermissibleValue(
        text="omit",
        description="Explicitly omit an Entity with no matching Value.")

    _defn = EnumDefinition(
        name="MissingHandling",
    )

class DuplicateHandling(EnumDefinitionImpl):

    distinct = PermissibleValue(
        text="distinct",
        description="Return each projected UUID once.")
    preserve = PermissibleValue(
        text="preserve",
        description="Retain repeated projected UUIDs from distinct traversal paths.")

    _defn = EnumDefinition(
        name="DuplicateHandling",
    )

class ValueKind(EnumDefinitionImpl):
    """
    Supported kinds of Values.
    """
    measurement = PermissibleValue(
        text="measurement",
        description="A measurable property with a Measure and an optional Quantity.")
    flow = PermissibleValue(
        text="flow",
        description="Temporal quantities with a Measure and optional Flow.")
    property = PermissibleValue(
        text="property",
        description="Inert typed property content with no Measure.")

    _defn = EnumDefinition(
        name="ValueKind",
        description="Supported kinds of Values.",
    )

class ContentKind(EnumDefinitionImpl):

    null = PermissibleValue(text="null")
    boolean = PermissibleValue(text="boolean")
    integer = PermissibleValue(text="integer")
    float = PermissibleValue(text="float")
    string = PermissibleValue(text="string")
    uuid = PermissibleValue(text="uuid")
    date = PermissibleValue(text="date")
    datetime = PermissibleValue(text="datetime")
    time = PermissibleValue(text="time")
    duration = PermissibleValue(text="duration")
    list = PermissibleValue(text="list")
    tuple = PermissibleValue(text="tuple")
    set = PermissibleValue(text="set")
    frozenset = PermissibleValue(text="frozenset")
    mapping = PermissibleValue(text="mapping")
    mapping_proxy = PermissibleValue(text="mapping_proxy")

    _defn = EnumDefinition(
        name="ContentKind",
    )

# Slots
class slots:
    pass

slots.measure = Slot(uri=RK.measure, name="measure", curie=RK.curie('measure'),
                   model_uri=DEFAULT_.measure, domain=None, range=Union[str, MeasureId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.quantity = Slot(uri=RK.quantity, name="quantity", curie=RK.curie('quantity'),
                   model_uri=DEFAULT_.quantity, domain=None, range=Optional[Union[dict, Quantity]])

slots.classification = Slot(uri=RK.classification, name="classification", curie=RK.curie('classification'),
                   model_uri=DEFAULT_.classification, domain=None, range=Optional[Union[str, ClassificationId]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.model__metadata = Slot(uri=RK.metadata, name="model__metadata", curie=RK.curie('metadata'),
                   model_uri=DEFAULT_.model__metadata, domain=None, range=Union[dict, Metadata])

slots.model__definitions = Slot(uri=RK.definitions, name="model__definitions", curie=RK.curie('definitions'),
                   model_uri=DEFAULT_.model__definitions, domain=None, range=Optional[Union[dict, Definitions]])

slots.model__system = Slot(uri=RK.system, name="model__system", curie=RK.curie('system'),
                   model_uri=DEFAULT_.model__system, domain=None, range=Optional[Union[dict, System]])

slots.model__provenance = Slot(uri=RK.provenance, name="model__provenance", curie=RK.curie('provenance'),
                   model_uri=DEFAULT_.model__provenance, domain=None, range=Optional[Union[dict, Provenance]])

slots.system__entities = Slot(uri=RK.entities, name="system__entities", curie=RK.curie('entities'),
                   model_uri=DEFAULT_.system__entities, domain=None, range=Optional[Union[dict[Union[str, EntityId], Union[dict, Entity]], list[Union[dict, Entity]]]])

slots.system__relationships = Slot(uri=RK.relationships, name="system__relationships", curie=RK.curie('relationships'),
                   model_uri=DEFAULT_.system__relationships, domain=None, range=Optional[Union[dict[Union[str, RelationshipId], Union[dict, Relationship]], list[Union[dict, Relationship]]]])

slots.system__assemblies = Slot(uri=RK.assemblies, name="system__assemblies", curie=RK.curie('assemblies'),
                   model_uri=DEFAULT_.system__assemblies, domain=None, range=Optional[Union[dict[Union[str, AssemblyId], Union[dict, Assembly]], list[Union[dict, Assembly]]]])

slots.system__formulations = Slot(uri=RK.formulations, name="system__formulations", curie=RK.curie('formulations'),
                   model_uri=DEFAULT_.system__formulations, domain=None, range=Optional[Union[dict[Union[str, FormulationId], Union[dict, Formulation]], list[Union[dict, Formulation]]]])

slots.specification__metadata = Slot(uri=RK.metadata, name="specification__metadata", curie=RK.curie('metadata'),
                   model_uri=DEFAULT_.specification__metadata, domain=None, range=Union[dict, Metadata])

slots.specification__model = Slot(uri=RK.model, name="specification__model", curie=RK.curie('model'),
                   model_uri=DEFAULT_.specification__model, domain=None, range=Optional[Union[str, MetadataId]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.specification__includes = Slot(uri=RK.includes, name="specification__includes", curie=RK.curie('includes'),
                   model_uri=DEFAULT_.specification__includes, domain=None, range=Optional[Union[Union[str, MetadataId], list[Union[str, MetadataId]]]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.specification__cases = Slot(uri=RK.cases, name="specification__cases", curie=RK.curie('cases'),
                   model_uri=DEFAULT_.specification__cases, domain=None, range=Optional[Union[Union[str, MetadataId], list[Union[str, MetadataId]]]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.specification__assignments = Slot(uri=RK.assignments, name="specification__assignments", curie=RK.curie('assignments'),
                   model_uri=DEFAULT_.specification__assignments, domain=None, range=Optional[Union[Union[dict, Assignment], list[Union[dict, Assignment]]]])

slots.specification__unknowns = Slot(uri=RK.unknowns, name="specification__unknowns", curie=RK.curie('unknowns'),
                   model_uri=DEFAULT_.specification__unknowns, domain=None, range=Optional[Union[Union[str, ValueId], list[Union[str, ValueId]]]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.specification__estimates = Slot(uri=RK.estimates, name="specification__estimates", curie=RK.curie('estimates'),
                   model_uri=DEFAULT_.specification__estimates, domain=None, range=Optional[Union[Union[dict, Assignment], list[Union[dict, Assignment]]]])

slots.specification__formulations = Slot(uri=RK.formulations, name="specification__formulations", curie=RK.curie('formulations'),
                   model_uri=DEFAULT_.specification__formulations, domain=None, range=Optional[Union[dict[Union[str, FormulationId], Union[dict, Formulation]], list[Union[dict, Formulation]]]])

slots.specification__objectives = Slot(uri=RK.objectives, name="specification__objectives", curie=RK.curie('objectives'),
                   model_uri=DEFAULT_.specification__objectives, domain=None, range=Optional[Union[Union[dict, Objective], list[Union[dict, Objective]]]])

slots.specification__settings = Slot(uri=RK.settings, name="specification__settings", curie=RK.curie('settings'),
                   model_uri=DEFAULT_.specification__settings, domain=None, range=Optional[Union[dict, Settings]])

slots.assignment__value = Slot(uri=RK.value, name="assignment__value", curie=RK.curie('value'),
                   model_uri=DEFAULT_.assignment__value, domain=None, range=Union[str, ValueId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.assignment__quantity = Slot(uri=RK.quantity, name="assignment__quantity", curie=RK.curie('quantity'),
                   model_uri=DEFAULT_.assignment__quantity, domain=None, range=Union[dict, Quantity])

slots.objective__expression = Slot(uri=RK.expression, name="objective__expression", curie=RK.curie('expression'),
                   model_uri=DEFAULT_.objective__expression, domain=None, range=Union[str, ExpressionId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.objective__sense = Slot(uri=RK.sense, name="objective__sense", curie=RK.curie('sense'),
                   model_uri=DEFAULT_.objective__sense, domain=None, range=Union[str, "ObjectiveKind"])

slots.run__metadata = Slot(uri=RK.metadata, name="run__metadata", curie=RK.curie('metadata'),
                   model_uri=DEFAULT_.run__metadata, domain=None, range=Union[dict, Metadata])

slots.run__specification = Slot(uri=RK.specification, name="run__specification", curie=RK.curie('specification'),
                   model_uri=DEFAULT_.run__specification, domain=None, range=Union[str, MetadataId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.run__spawns = Slot(uri=RK.spawns, name="run__spawns", curie=RK.curie('spawns'),
                   model_uri=DEFAULT_.run__spawns, domain=None, range=Optional[Union[Union[str, MetadataId], list[Union[str, MetadataId]]]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.run__outputs = Slot(uri=RK.outputs, name="run__outputs", curie=RK.curie('outputs'),
                   model_uri=DEFAULT_.run__outputs, domain=None, range=Optional[Union[Union[str, MetadataId], list[Union[str, MetadataId]]]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.run__report = Slot(uri=RK.report, name="run__report", curie=RK.curie('report'),
                   model_uri=DEFAULT_.run__report, domain=None, range=Union[dict, Report])

slots.report__status = Slot(uri=RK.status, name="report__status", curie=RK.curie('status'),
                   model_uri=DEFAULT_.report__status, domain=None, range=Union[dict, Status])

slots.report__runtime = Slot(uri=RK.runtime, name="report__runtime", curie=RK.curie('runtime'),
                   model_uri=DEFAULT_.report__runtime, domain=None, range=Optional[Union[dict, Runtime]])

slots.report__diagnostics = Slot(uri=RK.diagnostics, name="report__diagnostics", curie=RK.curie('diagnostics'),
                   model_uri=DEFAULT_.report__diagnostics, domain=None, range=Optional[Union[Union[dict, Diagnostic], list[Union[dict, Diagnostic]]]])

slots.report__trace = Slot(uri=RK.trace, name="report__trace", curie=RK.curie('trace'),
                   model_uri=DEFAULT_.report__trace, domain=None, range=Optional[Union[Union[dict, Step], list[Union[dict, Step]]]])

slots.status__completion = Slot(uri=RK.completion, name="status__completion", curie=RK.curie('completion'),
                   model_uri=DEFAULT_.status__completion, domain=None, range=Union[str, "CompletionStatus"])

slots.status__solution = Slot(uri=RK.solution, name="status__solution", curie=RK.curie('solution'),
                   model_uri=DEFAULT_.status__solution, domain=None, range=Union[str, "SolutionStatus"])

slots.runtime__started_at = Slot(uri=RK.started_at, name="runtime__started_at", curie=RK.curie('started_at'),
                   model_uri=DEFAULT_.runtime__started_at, domain=None, range=Optional[Union[str, XSDDateTime]])

slots.runtime__finished_at = Slot(uri=RK.finished_at, name="runtime__finished_at", curie=RK.curie('finished_at'),
                   model_uri=DEFAULT_.runtime__finished_at, domain=None, range=Optional[Union[str, XSDDateTime]])

slots.runtime__implementations = Slot(uri=RK.implementations, name="runtime__implementations", curie=RK.curie('implementations'),
                   model_uri=DEFAULT_.runtime__implementations, domain=None, range=Union[Union[dict, Implementation], list[Union[dict, Implementation]]])

slots.runtime__settings = Slot(uri=RK.settings, name="runtime__settings", curie=RK.curie('settings'),
                   model_uri=DEFAULT_.runtime__settings, domain=None, range=Optional[Union[dict, Settings]])

slots.implementation__kind = Slot(uri=RK.kind, name="implementation__kind", curie=RK.curie('kind'),
                   model_uri=DEFAULT_.implementation__kind, domain=None, range=Union[str, "ImplementationKind"])

slots.implementation__name = Slot(uri=RK.name, name="implementation__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.implementation__name, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.implementation__version = Slot(uri=RK.version, name="implementation__version", curie=RK.curie('version'),
                   model_uri=DEFAULT_.implementation__version, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.diagnostic__severity = Slot(uri=RK.severity, name="diagnostic__severity", curie=RK.curie('severity'),
                   model_uri=DEFAULT_.diagnostic__severity, domain=None, range=Union[str, "Severity"])

slots.diagnostic__code = Slot(uri=RK.code, name="diagnostic__code", curie=RK.curie('code'),
                   model_uri=DEFAULT_.diagnostic__code, domain=None, range=Union[str, Code])

slots.diagnostic__message = Slot(uri=RK.message, name="diagnostic__message", curie=RK.curie('message'),
                   model_uri=DEFAULT_.diagnostic__message, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.diagnostic__document = Slot(uri=RK.document, name="diagnostic__document", curie=RK.curie('document'),
                   model_uri=DEFAULT_.diagnostic__document, domain=None, range=Optional[Union[str, MetadataId]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.diagnostic__target = Slot(uri=RK.target, name="diagnostic__target", curie=RK.curie('target'),
                   model_uri=DEFAULT_.diagnostic__target, domain=None, range=Optional[Union[str, UUID]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.diagnostic__residual = Slot(uri=RK.residual, name="diagnostic__residual", curie=RK.curie('residual'),
                   model_uri=DEFAULT_.diagnostic__residual, domain=None, range=Optional[Union[dict, Quantity]])

slots.diagnostic__tolerance = Slot(uri=RK.tolerance, name="diagnostic__tolerance", curie=RK.curie('tolerance'),
                   model_uri=DEFAULT_.diagnostic__tolerance, domain=None, range=Optional[Union[dict, Quantity]])

slots.step__kind = Slot(uri=RK.kind, name="step__kind", curie=RK.curie('kind'),
                   model_uri=DEFAULT_.step__kind, domain=None, range=Union[str, "StepKind"])

slots.step__at = Slot(uri=RK.at, name="step__at", curie=RK.curie('at'),
                   model_uri=DEFAULT_.step__at, domain=None, range=Optional[Union[str, XSDDateTime]])

slots.step__message = Slot(uri=RK.message, name="step__message", curie=RK.curie('message'),
                   model_uri=DEFAULT_.step__message, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.step__document = Slot(uri=RK.document, name="step__document", curie=RK.curie('document'),
                   model_uri=DEFAULT_.step__document, domain=None, range=Optional[Union[str, MetadataId]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.step__target = Slot(uri=RK.target, name="step__target", curie=RK.curie('target'),
                   model_uri=DEFAULT_.step__target, domain=None, range=Optional[Union[str, UUID]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.definitions__taxonomies = Slot(uri=RK.taxonomies, name="definitions__taxonomies", curie=RK.curie('taxonomies'),
                   model_uri=DEFAULT_.definitions__taxonomies, domain=None, range=Optional[Union[dict[Union[str, TaxonomyId], Union[dict, Taxonomy]], list[Union[dict, Taxonomy]]]])

slots.definitions__measures = Slot(uri=RK.measures, name="definitions__measures", curie=RK.curie('measures'),
                   model_uri=DEFAULT_.definitions__measures, domain=None, range=Optional[Union[dict[Union[str, MeasureId], Union[dict, Measure]], list[Union[dict, Measure]]]])

slots.definitions__functions = Slot(uri=RK.functions, name="definitions__functions", curie=RK.curie('functions'),
                   model_uri=DEFAULT_.definitions__functions, domain=None, range=Optional[Union[dict[Union[str, FunctionId], Union[dict, Function]], list[Union[dict, Function]]]])

slots.binding__name = Slot(uri=RK.name, name="binding__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.binding__name, domain=None, range=Union[str, Code])

slots.binding__value = Slot(uri=RK.value, name="binding__value", curie=RK.curie('value'),
                   model_uri=DEFAULT_.binding__value, domain=None, range=Union[str, ValueId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.formulation__id = Slot(uri=RK.id, name="formulation__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.formulation__id, domain=None, range=URIRef)

slots.formulation__code = Slot(uri=RK.code, name="formulation__code", curie=RK.curie('code'),
                   model_uri=DEFAULT_.formulation__code, domain=None, range=Optional[Union[str, Code]])

slots.formulation__name = Slot(uri=RK.name, name="formulation__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.formulation__name, domain=None, range=Optional[str],
                   pattern=re.compile(r'\S'))

slots.formulation__description = Slot(uri=RK.description, name="formulation__description", curie=RK.curie('description'),
                   model_uri=DEFAULT_.formulation__description, domain=None, range=Optional[str])

slots.formulation__bindings = Slot(uri=RK.bindings, name="formulation__bindings", curie=RK.curie('bindings'),
                   model_uri=DEFAULT_.formulation__bindings, domain=None, range=Optional[Union[Union[dict, Binding], list[Union[dict, Binding]]]])

slots.formulation__values = Slot(uri=RK.values, name="formulation__values", curie=RK.curie('values'),
                   model_uri=DEFAULT_.formulation__values, domain=None, range=Optional[Union[dict[Union[str, ValueId], Union[dict, Value]], list[Union[dict, Value]]]])

slots.formulation__expressions = Slot(uri=RK.expressions, name="formulation__expressions", curie=RK.curie('expressions'),
                   model_uri=DEFAULT_.formulation__expressions, domain=None, range=Optional[Union[dict[Union[str, ExpressionId], Union[dict, Expression]], list[Union[dict, Expression]]]])

slots.formulation__constraints = Slot(uri=RK.constraints, name="formulation__constraints", curie=RK.curie('constraints'),
                   model_uri=DEFAULT_.formulation__constraints, domain=None, range=Optional[Union[dict[Union[str, ConstraintId], Union[dict, Constraint]], list[Union[dict, Constraint]]]])

slots.formulation__formulations = Slot(uri=RK.formulations, name="formulation__formulations", curie=RK.curie('formulations'),
                   model_uri=DEFAULT_.formulation__formulations, domain=None, range=Optional[Union[dict[Union[str, FormulationId], Union[dict, Formulation]], list[Union[dict, Formulation]]]])

slots.provenance__sources = Slot(uri=RK.sources, name="provenance__sources", curie=RK.curie('sources'),
                   model_uri=DEFAULT_.provenance__sources, domain=None, range=Optional[Union[dict[Union[str, SourceId], Union[dict, Source]], list[Union[dict, Source]]]])

slots.provenance__claims = Slot(uri=RK.claims, name="provenance__claims", curie=RK.curie('claims'),
                   model_uri=DEFAULT_.provenance__claims, domain=None, range=Optional[Union[dict[Union[str, ClaimId], Union[dict, Claim]], list[Union[dict, Claim]]]])

slots.provenance__facts = Slot(uri=RK.facts, name="provenance__facts", curie=RK.curie('facts'),
                   model_uri=DEFAULT_.provenance__facts, domain=None, range=Optional[Union[Union[dict, Fact], list[Union[dict, Fact]]]])

slots.source__id = Slot(uri=RK.id, name="source__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.source__id, domain=None, range=URIRef)

slots.source__name = Slot(uri=RK.name, name="source__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.source__name, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.source__checksum = Slot(uri=RK.checksum, name="source__checksum", curie=RK.curie('checksum'),
                   model_uri=DEFAULT_.source__checksum, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.source__issued_at = Slot(uri=RK.issued_at, name="source__issued_at", curie=RK.curie('issued_at'),
                   model_uri=DEFAULT_.source__issued_at, domain=None, range=Optional[Union[dict, Content]])

slots.source__received_at = Slot(uri=RK.received_at, name="source__received_at", curie=RK.curie('received_at'),
                   model_uri=DEFAULT_.source__received_at, domain=None, range=Optional[Union[dict, Content]])

slots.source__author = Slot(uri=RK.author, name="source__author", curie=RK.curie('author'),
                   model_uri=DEFAULT_.source__author, domain=None, range=Optional[str],
                   pattern=re.compile(r'\S'))

slots.location__source = Slot(uri=RK.source, name="location__source", curie=RK.curie('source'),
                   model_uri=DEFAULT_.location__source, domain=None, range=Union[str, SourceId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.location__address = Slot(uri=RK.address, name="location__address", curie=RK.curie('address'),
                   model_uri=DEFAULT_.location__address, domain=None, range=Optional[Union[dict[Union[str, EntryKey], Union[dict, Entry]], list[Union[dict, Entry]]]])

slots.entry__key = Slot(uri=RK.key, name="entry__key", curie=RK.curie('key'),
                   model_uri=DEFAULT_.entry__key, domain=None, range=URIRef,
                   pattern=re.compile(r'\S'))

slots.entry__value = Slot(uri=RK.value, name="entry__value", curie=RK.curie('value'),
                   model_uri=DEFAULT_.entry__value, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.method__code = Slot(uri=RK.code, name="method__code", curie=RK.curie('code'),
                   model_uri=DEFAULT_.method__code, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.method__version = Slot(uri=RK.version, name="method__version", curie=RK.curie('version'),
                   model_uri=DEFAULT_.method__version, domain=None, range=Optional[str],
                   pattern=re.compile(r'\S'))

slots.method__description = Slot(uri=RK.description, name="method__description", curie=RK.curie('description'),
                   model_uri=DEFAULT_.method__description, domain=None, range=Optional[str],
                   pattern=re.compile(r'\S'))

slots.claim__id = Slot(uri=RK.id, name="claim__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.claim__id, domain=None, range=URIRef)

slots.claim__content = Slot(uri=RK.content, name="claim__content", curie=RK.curie('content'),
                   model_uri=DEFAULT_.claim__content, domain=None, range=Union[dict, Content])

slots.claim__kind = Slot(uri=RK.kind, name="claim__kind", curie=RK.curie('kind'),
                   model_uri=DEFAULT_.claim__kind, domain=None, range=Union[str, "ClaimKind"])

slots.claim__sources = Slot(uri=RK.sources, name="claim__sources", curie=RK.curie('sources'),
                   model_uri=DEFAULT_.claim__sources, domain=None, range=Optional[Union[Union[dict, Content], list[Union[dict, Content]]]])

slots.claim__method = Slot(uri=RK.method, name="claim__method", curie=RK.curie('method'),
                   model_uri=DEFAULT_.claim__method, domain=None, range=Optional[Union[dict, Method]])

slots.fact__target = Slot(uri=RK.target, name="fact__target", curie=RK.curie('target'),
                   model_uri=DEFAULT_.fact__target, domain=None, range=Union[dict, Content])

slots.fact__claims = Slot(uri=RK.claims, name="fact__claims", curie=RK.curie('claims'),
                   model_uri=DEFAULT_.fact__claims, domain=None, range=Union[Union[str, ClaimId], list[Union[str, ClaimId]]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.fact__reconciliation = Slot(uri=RK.reconciliation, name="fact__reconciliation", curie=RK.curie('reconciliation'),
                   model_uri=DEFAULT_.fact__reconciliation, domain=None, range=Optional[Union[dict, Reconciliation]])

slots.reconciliation__selected = Slot(uri=RK.selected, name="reconciliation__selected", curie=RK.curie('selected'),
                   model_uri=DEFAULT_.reconciliation__selected, domain=None, range=Union[str, ClaimId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.reconciliation__status = Slot(uri=RK.status, name="reconciliation__status", curie=RK.curie('status'),
                   model_uri=DEFAULT_.reconciliation__status, domain=None, range=Union[str, "ReconciliationStatus"])

slots.reconciliation__method = Slot(uri=RK.method, name="reconciliation__method", curie=RK.curie('method'),
                   model_uri=DEFAULT_.reconciliation__method, domain=None, range=Optional[Union[dict, Method]])

slots.metadata__id = Slot(uri=RK.id, name="metadata__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.metadata__id, domain=None, range=URIRef)

slots.metadata__schema_version = Slot(uri=RK.schema_version, name="metadata__schema_version", curie=RK.curie('schema_version'),
                   model_uri=DEFAULT_.metadata__schema_version, domain=None, range=Union[str, Code])

slots.metadata__name = Slot(uri=RK.name, name="metadata__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.metadata__name, domain=None, range=Optional[str],
                   pattern=re.compile(r'\S'))

slots.metadata__description = Slot(uri=RK.description, name="metadata__description", curie=RK.curie('description'),
                   model_uri=DEFAULT_.metadata__description, domain=None, range=Optional[str])

slots.metadata__previous = Slot(uri=RK.previous, name="metadata__previous", curie=RK.curie('previous'),
                   model_uri=DEFAULT_.metadata__previous, domain=None, range=Optional[Union[str, MetadataId]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.settings__relative_tolerance = Slot(uri=RK.relative_tolerance, name="settings__relative_tolerance", curie=RK.curie('relative_tolerance'),
                   model_uri=DEFAULT_.settings__relative_tolerance, domain=None, range=Optional[Decimal])

slots.settings__iteration_limit = Slot(uri=RK.iteration_limit, name="settings__iteration_limit", curie=RK.curie('iteration_limit'),
                   model_uri=DEFAULT_.settings__iteration_limit, domain=None, range=Optional[int])

slots.settings__time_limit = Slot(uri=RK.time_limit, name="settings__time_limit", curie=RK.curie('time_limit'),
                   model_uri=DEFAULT_.settings__time_limit, domain=None, range=Optional[Decimal])

slots.quantity__magnitude = Slot(uri=RK.magnitude, name="quantity__magnitude", curie=RK.curie('magnitude'),
                   model_uri=DEFAULT_.quantity__magnitude, domain=None, range=Decimal)

slots.quantity__units = Slot(uri=RK.units, name="quantity__units", curie=RK.curie('units'),
                   model_uri=DEFAULT_.quantity__units, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.measure__id = Slot(uri=RK.id, name="measure__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.measure__id, domain=None, range=URIRef)

slots.measure__code = Slot(uri=RK.code, name="measure__code", curie=RK.curie('code'),
                   model_uri=DEFAULT_.measure__code, domain=None, range=Union[str, Code])

slots.measure__name = Slot(uri=RK.name, name="measure__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.measure__name, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.measure__units = Slot(uri=RK.units, name="measure__units", curie=RK.curie('units'),
                   model_uri=DEFAULT_.measure__units, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.measure__definition = Slot(uri=RK.definition, name="measure__definition", curie=RK.curie('definition'),
                   model_uri=DEFAULT_.measure__definition, domain=None, range=Optional[str])

slots.measure__tags = Slot(uri=RK.tags, name="measure__tags", curie=RK.curie('tags'),
                   model_uri=DEFAULT_.measure__tags, domain=None, range=Optional[Union[str, list[str]]],
                   pattern=re.compile(r'\S'))

slots.measurement__id = Slot(uri=RK.id, name="measurement__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.measurement__id, domain=None, range=URIRef)

slots.classification__id = Slot(uri=RK.id, name="classification__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.classification__id, domain=None, range=URIRef)

slots.classification__code = Slot(uri=RK.code, name="classification__code", curie=RK.curie('code'),
                   model_uri=DEFAULT_.classification__code, domain=None, range=Union[str, Code])

slots.classification__name = Slot(uri=RK.name, name="classification__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.classification__name, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.classification__definition = Slot(uri=RK.definition, name="classification__definition", curie=RK.curie('definition'),
                   model_uri=DEFAULT_.classification__definition, domain=None, range=Optional[str])

slots.classification__parent = Slot(uri=RK.parent, name="classification__parent", curie=RK.curie('parent'),
                   model_uri=DEFAULT_.classification__parent, domain=None, range=Optional[Union[str, ClassificationId]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.taxonomy__id = Slot(uri=RK.id, name="taxonomy__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.taxonomy__id, domain=None, range=URIRef)

slots.taxonomy__code = Slot(uri=RK.code, name="taxonomy__code", curie=RK.curie('code'),
                   model_uri=DEFAULT_.taxonomy__code, domain=None, range=Union[str, Code])

slots.taxonomy__name = Slot(uri=RK.name, name="taxonomy__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.taxonomy__name, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.taxonomy__definition = Slot(uri=RK.definition, name="taxonomy__definition", curie=RK.curie('definition'),
                   model_uri=DEFAULT_.taxonomy__definition, domain=None, range=Optional[str])

slots.taxonomy__classifications = Slot(uri=RK.classifications, name="taxonomy__classifications", curie=RK.curie('classifications'),
                   model_uri=DEFAULT_.taxonomy__classifications, domain=None, range=Union[dict[Union[str, ClassificationId], Union[dict, Classification]], list[Union[dict, Classification]]])

slots.domain__kind = Slot(uri=RK.kind, name="domain__kind", curie=RK.curie('kind'),
                   model_uri=DEFAULT_.domain__kind, domain=None, range=Union[str, "DomainKind"])

slots.domain__units = Slot(uri=RK.units, name="domain__units", curie=RK.curie('units'),
                   model_uri=DEFAULT_.domain__units, domain=None, range=Optional[str],
                   pattern=re.compile(r'\S'))

slots.domain__measure = Slot(uri=RK.measure, name="domain__measure", curie=RK.curie('measure'),
                   model_uri=DEFAULT_.domain__measure, domain=None, range=Optional[Union[str, MeasureId]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.domain__item_domain = Slot(uri=RK.item_domain, name="domain__item_domain", curie=RK.curie('item_domain'),
                   model_uri=DEFAULT_.domain__item_domain, domain=None, range=Optional[Union[dict, Domain]])

slots.domain__collection_kind = Slot(uri=RK.collection_kind, name="domain__collection_kind", curie=RK.curie('collection_kind'),
                   model_uri=DEFAULT_.domain__collection_kind, domain=None, range=Optional[Union[str, "CollectionKind"]])

slots.parameter__name = Slot(uri=RK.name, name="parameter__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.parameter__name, domain=None, range=Union[str, Code])

slots.parameter__domain = Slot(uri=RK.domain, name="parameter__domain", curie=RK.curie('domain'),
                   model_uri=DEFAULT_.parameter__domain, domain=None, range=Union[dict, Domain])

slots.parameter__kind = Slot(uri=RK.kind, name="parameter__kind", curie=RK.curie('kind'),
                   model_uri=DEFAULT_.parameter__kind, domain=None, range=Union[str, "ParameterKind"])

slots.parameter__required = Slot(uri=RK.required, name="parameter__required", curie=RK.curie('required'),
                   model_uri=DEFAULT_.parameter__required, domain=None, range=Union[bool, Bool])

slots.function__id = Slot(uri=RK.id, name="function__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.function__id, domain=None, range=URIRef)

slots.function__code = Slot(uri=RK.code, name="function__code", curie=RK.curie('code'),
                   model_uri=DEFAULT_.function__code, domain=None, range=Union[str, Code])

slots.function__name = Slot(uri=RK.name, name="function__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.function__name, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.function__version = Slot(uri=RK.version, name="function__version", curie=RK.curie('version'),
                   model_uri=DEFAULT_.function__version, domain=None, range=Union[str, Code])

slots.function__parameters = Slot(uri=RK.parameters, name="function__parameters", curie=RK.curie('parameters'),
                   model_uri=DEFAULT_.function__parameters, domain=None, range=Optional[Union[Union[dict, Parameter], list[Union[dict, Parameter]]]])

slots.function__result = Slot(uri=RK.result, name="function__result", curie=RK.curie('result'),
                   model_uri=DEFAULT_.function__result, domain=None, range=Union[dict, Domain])

slots.function__semantics = Slot(uri=RK.semantics, name="function__semantics", curie=RK.curie('semantics'),
                   model_uri=DEFAULT_.function__semantics, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.function__unit_rule = Slot(uri=RK.unit_rule, name="function__unit_rule", curie=RK.curie('unit_rule'),
                   model_uri=DEFAULT_.function__unit_rule, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.function__empty_collection = Slot(uri=RK.empty_collection, name="function__empty_collection", curie=RK.curie('empty_collection'),
                   model_uri=DEFAULT_.function__empty_collection, domain=None, range=Optional[Union[str, "EmptyHandling"]])

slots.constraint__id = Slot(uri=RK.id, name="constraint__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.constraint__id, domain=None, range=URIRef)

slots.constraint__code = Slot(uri=RK.code, name="constraint__code", curie=RK.curie('code'),
                   model_uri=DEFAULT_.constraint__code, domain=None, range=Optional[Union[str, Code]])

slots.constraint__name = Slot(uri=RK.name, name="constraint__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.constraint__name, domain=None, range=Optional[str],
                   pattern=re.compile(r'\S'))

slots.constraint__description = Slot(uri=RK.description, name="constraint__description", curie=RK.curie('description'),
                   model_uri=DEFAULT_.constraint__description, domain=None, range=Optional[str])

slots.constraint__predicate = Slot(uri=RK.predicate, name="constraint__predicate", curie=RK.curie('predicate'),
                   model_uri=DEFAULT_.constraint__predicate, domain=None, range=Union[str, ExpressionId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.assembly__entities = Slot(uri=RK.entities, name="assembly__entities", curie=RK.curie('entities'),
                   model_uri=DEFAULT_.assembly__entities, domain=None, range=Optional[Union[Union[str, EntityId], list[Union[str, EntityId]]]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.assembly__relationships = Slot(uri=RK.relationships, name="assembly__relationships", curie=RK.curie('relationships'),
                   model_uri=DEFAULT_.assembly__relationships, domain=None, range=Optional[Union[Union[str, RelationshipId], list[Union[str, RelationshipId]]]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.expression__id = Slot(uri=RK.id, name="expression__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.expression__id, domain=None, range=URIRef)

slots.expression__kind = Slot(uri=RK.kind, name="expression__kind", curie=RK.curie('kind'),
                   model_uri=DEFAULT_.expression__kind, domain=None, range=Union[str, "ExpressionKind"])

slots.expression__quantity = Slot(uri=RK.quantity, name="expression__quantity", curie=RK.curie('quantity'),
                   model_uri=DEFAULT_.expression__quantity, domain=None, range=Optional[Union[dict, Quantity]])

slots.expression__boolean = Slot(uri=RK.boolean, name="expression__boolean", curie=RK.curie('boolean'),
                   model_uri=DEFAULT_.expression__boolean, domain=None, range=Optional[Union[bool, Bool]])

slots.expression__target = Slot(uri=RK.target, name="expression__target", curie=RK.curie('target'),
                   model_uri=DEFAULT_.expression__target, domain=None, range=Optional[Union[str, ValueId]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.expression__operator = Slot(uri=RK.operator, name="expression__operator", curie=RK.curie('operator'),
                   model_uri=DEFAULT_.expression__operator, domain=None, range=Optional[Union[str, "Operator"]])

slots.expression__operands = Slot(uri=RK.operands, name="expression__operands", curie=RK.curie('operands'),
                   model_uri=DEFAULT_.expression__operands, domain=None, range=Optional[Union[dict[Union[str, ExpressionId], Union[dict, Expression]], list[Union[dict, Expression]]]])

slots.expression__operand = Slot(uri=RK.operand, name="expression__operand", curie=RK.curie('operand'),
                   model_uri=DEFAULT_.expression__operand, domain=None, range=Optional[Union[dict, Expression]])

slots.expression__call = Slot(uri=RK.call, name="expression__call", curie=RK.curie('call'),
                   model_uri=DEFAULT_.expression__call, domain=None, range=Optional[Union[dict, Call]])

slots.expression__selection = Slot(uri=RK.selection, name="expression__selection", curie=RK.curie('selection'),
                   model_uri=DEFAULT_.expression__selection, domain=None, range=Optional[Union[dict, Selection]])

slots.expression__query = Slot(uri=RK.query, name="expression__query", curie=RK.curie('query'),
                   model_uri=DEFAULT_.expression__query, domain=None, range=Optional[Union[dict, Query]])

slots.call__function = Slot(uri=RK.function, name="call__function", curie=RK.curie('function'),
                   model_uri=DEFAULT_.call__function, domain=None, range=Union[str, FunctionId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.call__arguments = Slot(uri=RK.arguments, name="call__arguments", curie=RK.curie('arguments'),
                   model_uri=DEFAULT_.call__arguments, domain=None, range=Optional[Union[dict[Union[str, ExpressionId], Union[dict, Expression]], list[Union[dict, Expression]]]])

slots.call__named_arguments = Slot(uri=RK.named_arguments, name="call__named_arguments", curie=RK.curie('named_arguments'),
                   model_uri=DEFAULT_.call__named_arguments, domain=None, range=Optional[Union[Union[dict, Argument], list[Union[dict, Argument]]]])

slots.argument__name = Slot(uri=RK.name, name="argument__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.argument__name, domain=None, range=Union[str, Code])

slots.argument__expression = Slot(uri=RK.expression, name="argument__expression", curie=RK.curie('expression'),
                   model_uri=DEFAULT_.argument__expression, domain=None, range=Union[dict, Expression])

slots.selection__kind = Slot(uri=RK.kind, name="selection__kind", curie=RK.curie('kind'),
                   model_uri=DEFAULT_.selection__kind, domain=None, range=Union[str, "SelectionKind"])

slots.selection__base = Slot(uri=RK.base, name="selection__base", curie=RK.curie('base'),
                   model_uri=DEFAULT_.selection__base, domain=None, range=Union[dict, Expression])

slots.selection__member = Slot(uri=RK.member, name="selection__member", curie=RK.curie('member'),
                   model_uri=DEFAULT_.selection__member, domain=None, range=Optional[Union[str, Code]])

slots.selection__index = Slot(uri=RK.index, name="selection__index", curie=RK.curie('index'),
                   model_uri=DEFAULT_.selection__index, domain=None, range=Optional[Union[dict, Expression]])

slots.relationship__id = Slot(uri=RK.id, name="relationship__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.relationship__id, domain=None, range=URIRef)

slots.relationship__source = Slot(uri=RK.source, name="relationship__source", curie=RK.curie('source'),
                   model_uri=DEFAULT_.relationship__source, domain=None, range=Union[str, EntityId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.relationship__target = Slot(uri=RK.target, name="relationship__target", curie=RK.curie('target'),
                   model_uri=DEFAULT_.relationship__target, domain=None, range=Union[str, EntityId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.relationship__characteristics = Slot(uri=RK.characteristics, name="relationship__characteristics", curie=RK.curie('characteristics'),
                   model_uri=DEFAULT_.relationship__characteristics, domain=None, range=Optional[Union[dict, Characteristics]])

slots.traversal__kind = Slot(uri=RK.kind, name="traversal__kind", curie=RK.curie('kind'),
                   model_uri=DEFAULT_.traversal__kind, domain=None, range=Union[str, "TraversalKind"])

slots.traversal__depth = Slot(uri=RK.depth, name="traversal__depth", curie=RK.curie('depth'),
                   model_uri=DEFAULT_.traversal__depth, domain=None, range=Union[str, "Depth"])

slots.traversal__classification = Slot(uri=RK.classification, name="traversal__classification", curie=RK.curie('classification'),
                   model_uri=DEFAULT_.traversal__classification, domain=None, range=Optional[Union[str, ClassificationId]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.traversal__direction = Slot(uri=RK.direction, name="traversal__direction", curie=RK.curie('direction'),
                   model_uri=DEFAULT_.traversal__direction, domain=None, range=Optional[Union[str, "Direction"]])

slots.criterion__key = Slot(uri=RK.key, name="criterion__key", curie=RK.curie('key'),
                   model_uri=DEFAULT_.criterion__key, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.criterion__classification = Slot(uri=RK.classification, name="criterion__classification", curie=RK.curie('classification'),
                   model_uri=DEFAULT_.criterion__classification, domain=None, range=Union[str, ClassificationId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.filter__classification = Slot(uri=RK.classification, name="filter__classification", curie=RK.curie('classification'),
                   model_uri=DEFAULT_.filter__classification, domain=None, range=Optional[Union[str, ClassificationId]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.filter__labels = Slot(uri=RK.labels, name="filter__labels", curie=RK.curie('labels'),
                   model_uri=DEFAULT_.filter__labels, domain=None, range=Optional[Union[Union[dict, Criterion], list[Union[dict, Criterion]]]])

slots.projection__kind = Slot(uri=RK.kind, name="projection__kind", curie=RK.curie('kind'),
                   model_uri=DEFAULT_.projection__kind, domain=None, range=Union[str, "ProjectionKind"])

slots.projection__key = Slot(uri=RK.key, name="projection__key", curie=RK.curie('key'),
                   model_uri=DEFAULT_.projection__key, domain=None, range=Optional[str],
                   pattern=re.compile(r'\S'))

slots.projection__measure = Slot(uri=RK.measure, name="projection__measure", curie=RK.curie('measure'),
                   model_uri=DEFAULT_.projection__measure, domain=None, range=Optional[Union[str, MeasureId]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.projection__cardinality = Slot(uri=RK.cardinality, name="projection__cardinality", curie=RK.curie('cardinality'),
                   model_uri=DEFAULT_.projection__cardinality, domain=None, range=Optional[Union[str, "Cardinality"]])

slots.projection__missing = Slot(uri=RK.missing, name="projection__missing", curie=RK.curie('missing'),
                   model_uri=DEFAULT_.projection__missing, domain=None, range=Optional[Union[str, "MissingHandling"]])

slots.query__starting_at = Slot(uri=RK.starting_at, name="query__starting_at", curie=RK.curie('starting_at'),
                   model_uri=DEFAULT_.query__starting_at, domain=None, range=Union[str, EntityId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.query__steps = Slot(uri=RK.steps, name="query__steps", curie=RK.curie('steps'),
                   model_uri=DEFAULT_.query__steps, domain=None, range=Optional[Union[Union[dict, Traversal], list[Union[dict, Traversal]]]])

slots.query__filter = Slot(uri=RK.filter, name="query__filter", curie=RK.curie('filter'),
                   model_uri=DEFAULT_.query__filter, domain=None, range=Optional[Union[dict, Filter]])

slots.query__projection = Slot(uri=RK.projection, name="query__projection", curie=RK.curie('projection'),
                   model_uri=DEFAULT_.query__projection, domain=None, range=Union[dict, Projection])

slots.query__duplicates = Slot(uri=RK.duplicates, name="query__duplicates", curie=RK.curie('duplicates'),
                   model_uri=DEFAULT_.query__duplicates, domain=None, range=Union[str, "DuplicateHandling"])

slots.entity__id = Slot(uri=RK.id, name="entity__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.entity__id, domain=None, range=URIRef)

slots.entity__code = Slot(uri=RK.code, name="entity__code", curie=RK.curie('code'),
                   model_uri=DEFAULT_.entity__code, domain=None, range=Optional[Union[str, Code]])

slots.entity__name = Slot(uri=RK.name, name="entity__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.entity__name, domain=None, range=Optional[str],
                   pattern=re.compile(r'\S'))

slots.entity__characteristics = Slot(uri=RK.characteristics, name="entity__characteristics", curie=RK.curie('characteristics'),
                   model_uri=DEFAULT_.entity__characteristics, domain=None, range=Optional[Union[dict, Characteristics]])

slots.characteristics__labels = Slot(uri=RK.labels, name="characteristics__labels", curie=RK.curie('labels'),
                   model_uri=DEFAULT_.characteristics__labels, domain=None, range=Optional[Union[dict[Union[str, LabelId], Union[dict, Label]], list[Union[dict, Label]]]])

slots.characteristics__values = Slot(uri=RK.values, name="characteristics__values", curie=RK.curie('values'),
                   model_uri=DEFAULT_.characteristics__values, domain=None, range=Optional[Union[dict[Union[str, ValueId], Union[dict, Value]], list[Union[dict, Value]]]])

slots.label__id = Slot(uri=RK.id, name="label__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.label__id, domain=None, range=URIRef)

slots.label__key = Slot(uri=RK.key, name="label__key", curie=RK.curie('key'),
                   model_uri=DEFAULT_.label__key, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.label__classifications = Slot(uri=RK.classifications, name="label__classifications", curie=RK.curie('classifications'),
                   model_uri=DEFAULT_.label__classifications, domain=None, range=Optional[Union[Union[str, ClassificationId], list[Union[str, ClassificationId]]]],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.value__id = Slot(uri=RK.id, name="value__id", curie=RK.curie('id'),
                   model_uri=DEFAULT_.value__id, domain=None, range=URIRef)

slots.value__key = Slot(uri=RK.key, name="value__key", curie=RK.curie('key'),
                   model_uri=DEFAULT_.value__key, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.value__kind = Slot(uri=RK.kind, name="value__kind", curie=RK.curie('kind'),
                   model_uri=DEFAULT_.value__kind, domain=None, range=Union[str, "ValueKind"])

slots.value__description = Slot(uri=RK.description, name="value__description", curie=RK.curie('description'),
                   model_uri=DEFAULT_.value__description, domain=None, range=Optional[str])

slots.value__flow = Slot(uri=RK.flow, name="value__flow", curie=RK.curie('flow'),
                   model_uri=DEFAULT_.value__flow, domain=None, range=Optional[Union[dict, Flow]])

slots.value__content = Slot(uri=RK.content, name="value__content", curie=RK.curie('content'),
                   model_uri=DEFAULT_.value__content, domain=None, range=Optional[Union[dict, PropertyContent]])

slots.flow__units = Slot(uri=RK.units, name="flow__units", curie=RK.curie('units'),
                   model_uri=DEFAULT_.flow__units, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.flow__movements = Slot(uri=RK.movements, name="flow__movements", curie=RK.curie('movements'),
                   model_uri=DEFAULT_.flow__movements, domain=None, range=Union[Union[dict, Movement], list[Union[dict, Movement]]])

slots.movement__key = Slot(uri=RK.key, name="movement__key", curie=RK.curie('key'),
                   model_uri=DEFAULT_.movement__key, domain=None, range=str,
                   pattern=re.compile(r'\S'))

slots.movement__date = Slot(uri=RK.date, name="movement__date", curie=RK.curie('date'),
                   model_uri=DEFAULT_.movement__date, domain=None, range=Optional[Union[str, XSDDate]])

slots.movement__period = Slot(uri=RK.period, name="movement__period", curie=RK.curie('period'),
                   model_uri=DEFAULT_.movement__period, domain=None, range=Optional[Union[dict, Period]])

slots.movement__magnitude = Slot(uri=RK.magnitude, name="movement__magnitude", curie=RK.curie('magnitude'),
                   model_uri=DEFAULT_.movement__magnitude, domain=None, range=Optional[Decimal])

slots.movement__claims = Slot(uri=RK.claims, name="movement__claims", curie=RK.curie('claims'),
                   model_uri=DEFAULT_.movement__claims, domain=None, range=Optional[Union[Union[str, UUID], list[Union[str, UUID]]]])

slots.propertyContent__kind = Slot(uri=RK.kind, name="propertyContent__kind", curie=RK.curie('kind'),
                   model_uri=DEFAULT_.propertyContent__kind, domain=None, range=Union[str, "ContentKind"])

slots.propertyContent__text = Slot(uri=RK.text, name="propertyContent__text", curie=RK.curie('text'),
                   model_uri=DEFAULT_.propertyContent__text, domain=None, range=Optional[str])

slots.propertyContent__zone = Slot(uri=RK.zone, name="propertyContent__zone", curie=RK.curie('zone'),
                   model_uri=DEFAULT_.propertyContent__zone, domain=None, range=Optional[str])

slots.propertyContent__fold = Slot(uri=RK.fold, name="propertyContent__fold", curie=RK.curie('fold'),
                   model_uri=DEFAULT_.propertyContent__fold, domain=None, range=Optional[int])

slots.propertyContent__items = Slot(uri=RK.items, name="propertyContent__items", curie=RK.curie('items'),
                   model_uri=DEFAULT_.propertyContent__items, domain=None, range=Optional[Union[Union[dict, PropertyContent], list[Union[dict, PropertyContent]]]])

slots.propertyContent__entries = Slot(uri=RK.entries, name="propertyContent__entries", curie=RK.curie('entries'),
                   model_uri=DEFAULT_.propertyContent__entries, domain=None, range=Optional[Union[Union[dict, ContentEntry], list[Union[dict, ContentEntry]]]])

slots.contentEntry__key = Slot(uri=RK.key, name="contentEntry__key", curie=RK.curie('key'),
                   model_uri=DEFAULT_.contentEntry__key, domain=None, range=Union[dict, PropertyContent])

slots.contentEntry__value = Slot(uri=RK.value, name="contentEntry__value", curie=RK.curie('value'),
                   model_uri=DEFAULT_.contentEntry__value, domain=None, range=Union[dict, PropertyContent])

slots.period__start = Slot(uri=RK.start, name="period__start", curie=RK.curie('start'),
                   model_uri=DEFAULT_.period__start, domain=None, range=Union[str, XSDDate])

slots.period__end = Slot(uri=RK.end, name="period__end", curie=RK.curie('end'),
                   model_uri=DEFAULT_.period__end, domain=None, range=Union[str, XSDDate])

slots.span__name = Slot(uri=RK.name, name="span__name", curie=RK.curie('name'),
                   model_uri=DEFAULT_.span__name, domain=None, range=Optional[str])

slots.Relationship_classification = Slot(uri=RK.classification, name="Relationship_classification", curie=RK.curie('classification'),
                   model_uri=DEFAULT_.Relationship_classification, domain=Relationship, range=Union[str, ClassificationId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))

slots.Value_measure = Slot(uri=RK.measure, name="Value_measure", curie=RK.curie('measure'),
                   model_uri=DEFAULT_.Value_measure, domain=Value, range=Union[str, MeasureId],
                   pattern=re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'))
