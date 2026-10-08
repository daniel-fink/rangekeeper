// Generated from resolved LinkML. Do not edit.
using System.Text.Json.Nodes;
using Rangekeeper.Serialization;
namespace Rangekeeper.Records;

/// <summary>Schema-derived Action wire record. Exports and nested reads are detached.</summary>
public sealed class Action : WireRecord
{
    public Action() { }
    public Action(JsonObject data) : base(data) { }

    /// <summary>Wire field kind; missing and null remain distinct.</summary>
    public string Kind
    {
        get => Read<string>("kind");
        init => Write("kind", value);
    }
    /// <summary>Wire field quantity; missing and null remain distinct.</summary>
    public Optional<Quantity> Quantity
    {
        get => ReadOptional<Quantity>("quantity");
        init => WriteOptional("quantity", value);
    }
    /// <summary>Wire field target; missing and null remain distinct.</summary>
    public Optional<Reference> Target
    {
        get => ReadOptional<Reference>("target");
        init => WriteOptional("target", value);
    }
}

/// <summary>Schema-derived Argument wire record. Exports and nested reads are detached.</summary>
public sealed class Argument : WireRecord
{
    public Argument() { }
    public Argument(JsonObject data) : base(data) { }

    /// <summary>Wire field expression; missing and null remain distinct.</summary>
    public Expression Expression
    {
        get => Read<Expression>("expression");
        init => Write("expression", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
}

/// <summary>Schema-derived Assembly wire record. Exports and nested reads are detached.</summary>
public sealed class Assembly : WireRecord
{
    public Assembly() { }
    public Assembly(JsonObject data) : base(data) { }

    /// <summary>Wire field characteristics; missing and null remain distinct.</summary>
    public Optional<Characteristics> Characteristics
    {
        get => ReadOptional<Characteristics>("characteristics");
        init => WriteOptional("characteristics", value);
    }
    /// <summary>Wire field classification; missing and null remain distinct.</summary>
    public Optional<Guid> Classification
    {
        get => ReadOptional<Guid>("classification");
        init => WriteOptional("classification", value);
    }
    /// <summary>Wire field code; missing and null remain distinct.</summary>
    public Optional<string> Code
    {
        get => ReadOptional<string>("code");
        init => WriteOptional("code", value);
    }
    /// <summary>Wire field entities; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Guid>> Entities
    {
        get => ReadOptional<IReadOnlyList<Guid>>("entities");
        init => WriteOptional("entities", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public Optional<string> Name
    {
        get => ReadOptional<string>("name");
        init => WriteOptional("name", value);
    }
    /// <summary>Wire field relationships; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Guid>> Relationships
    {
        get => ReadOptional<IReadOnlyList<Guid>>("relationships");
        init => WriteOptional("relationships", value);
    }
}

/// <summary>Schema-derived Assignment wire record. Exports and nested reads are detached.</summary>
public sealed class Assignment : WireRecord
{
    public Assignment() { }
    public Assignment(JsonObject data) : base(data) { }

    /// <summary>Wire field quantity; missing and null remain distinct.</summary>
    public Quantity Quantity
    {
        get => Read<Quantity>("quantity");
        init => Write("quantity", value);
    }
    /// <summary>Wire field target; missing and null remain distinct.</summary>
    public Reference Target
    {
        get => Read<Reference>("target");
        init => Write("target", value);
    }
}

/// <summary>Schema-derived Binding wire record. Exports and nested reads are detached.</summary>
public sealed class Binding : WireRecord
{
    public Binding() { }
    public Binding(JsonObject data) : base(data) { }

    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
    /// <summary>Wire field value; missing and null remain distinct.</summary>
    public Guid Value
    {
        get => Read<Guid>("value");
        init => Write("value", value);
    }
}

/// <summary>Schema-derived CalculationProvenance wire record. Exports and nested reads are detached.</summary>
public sealed class CalculationProvenance : WireRecord
{
    public CalculationProvenance() { }
    public CalculationProvenance(JsonObject data) : base(data) { }

    /// <summary>Wire field fingerprint; missing and null remain distinct.</summary>
    public string Fingerprint
    {
        get => Read<string>("fingerprint");
        init => Write("fingerprint", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
    /// <summary>Wire field versions; missing and null remain distinct.</summary>
    public IReadOnlyList<LibraryVersion> Versions
    {
        get => Read<IReadOnlyList<LibraryVersion>>("versions");
        init => Write("versions", value);
    }
}

/// <summary>Schema-derived Call wire record. Exports and nested reads are detached.</summary>
public sealed class Call : WireRecord
{
    public Call() { }
    public Call(JsonObject data) : base(data) { }

    /// <summary>Wire field arguments; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Expression>> Arguments
    {
        get => ReadOptional<IReadOnlyList<Expression>>("arguments");
        init => WriteOptional("arguments", value);
    }
    /// <summary>Wire field function; missing and null remain distinct.</summary>
    public Guid Function
    {
        get => Read<Guid>("function");
        init => Write("function", value);
    }
    /// <summary>Wire field named_arguments; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Argument>> NamedArguments
    {
        get => ReadOptional<IReadOnlyList<Argument>>("named_arguments");
        init => WriteOptional("named_arguments", value);
    }
}

/// <summary>Schema-derived Characteristics wire record. Exports and nested reads are detached.</summary>
public sealed class Characteristics : WireRecord
{
    public Characteristics() { }
    public Characteristics(JsonObject data) : base(data) { }

    /// <summary>Wire field labels; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Label>> Labels
    {
        get => ReadOptional<IReadOnlyList<Label>>("labels");
        init => WriteOptional("labels", value);
    }
    /// <summary>Wire field values; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Value>> Values
    {
        get => ReadOptional<IReadOnlyList<Value>>("values");
        init => WriteOptional("values", value);
    }
}

/// <summary>Schema-derived Claim wire record. Exports and nested reads are detached.</summary>
public sealed class Claim : WireRecord
{
    public Claim() { }
    public Claim(JsonObject data) : base(data) { }

    /// <summary>Wire field content; missing and null remain distinct.</summary>
    public Optional<JsonNode> Content
    {
        get => ReadOptional<JsonNode>("content");
        init => WriteOptional("content", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field kind; missing and null remain distinct.</summary>
    public string Kind
    {
        get => Read<string>("kind");
        init => Write("kind", value);
    }
    /// <summary>Wire field method; missing and null remain distinct.</summary>
    public Optional<Method> Method
    {
        get => ReadOptional<Method>("method");
        init => WriteOptional("method", value);
    }
    /// <summary>Wire field sources; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<JsonNode>> Sources
    {
        get => ReadOptional<IReadOnlyList<JsonNode>>("sources");
        init => WriteOptional("sources", value);
    }
}

/// <summary>Schema-derived Classification wire record. Exports and nested reads are detached.</summary>
public sealed class Classification : WireRecord
{
    public Classification() { }
    public Classification(JsonObject data) : base(data) { }

    /// <summary>Wire field code; missing and null remain distinct.</summary>
    public string Code
    {
        get => Read<string>("code");
        init => Write("code", value);
    }
    /// <summary>Wire field definition; missing and null remain distinct.</summary>
    public Optional<string> Definition
    {
        get => ReadOptional<string>("definition");
        init => WriteOptional("definition", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
    /// <summary>Wire field parent; missing and null remain distinct.</summary>
    public Optional<Guid> Parent
    {
        get => ReadOptional<Guid>("parent");
        init => WriteOptional("parent", value);
    }
}

/// <summary>Schema-derived Constraint wire record. Exports and nested reads are detached.</summary>
public sealed class Constraint : WireRecord
{
    public Constraint() { }
    public Constraint(JsonObject data) : base(data) { }

    /// <summary>Wire field code; missing and null remain distinct.</summary>
    public Optional<string> Code
    {
        get => ReadOptional<string>("code");
        init => WriteOptional("code", value);
    }
    /// <summary>Wire field description; missing and null remain distinct.</summary>
    public Optional<string> Description
    {
        get => ReadOptional<string>("description");
        init => WriteOptional("description", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public Optional<string> Name
    {
        get => ReadOptional<string>("name");
        init => WriteOptional("name", value);
    }
    /// <summary>Wire field predicate; missing and null remain distinct.</summary>
    public Guid Predicate
    {
        get => Read<Guid>("predicate");
        init => Write("predicate", value);
    }
}

/// <summary>Schema-derived Content wire record. Exports and nested reads are detached.</summary>
public sealed class Content : WireRecord
{
    public Content() { }
    public Content(JsonObject data) : base(data) { }

}

/// <summary>Schema-derived ContentEntry wire record. Exports and nested reads are detached.</summary>
public sealed class ContentEntry : WireRecord
{
    public ContentEntry() { }
    public ContentEntry(JsonObject data) : base(data) { }

    /// <summary>Wire field key; missing and null remain distinct.</summary>
    public PropertyContent Key
    {
        get => Read<PropertyContent>("key");
        init => Write("key", value);
    }
    /// <summary>Wire field value; missing and null remain distinct.</summary>
    public PropertyContent Value
    {
        get => Read<PropertyContent>("value");
        init => Write("value", value);
    }
}

/// <summary>Schema-derived Criterion wire record. Exports and nested reads are detached.</summary>
public sealed class Criterion : WireRecord
{
    public Criterion() { }
    public Criterion(JsonObject data) : base(data) { }

    /// <summary>Wire field classification; missing and null remain distinct.</summary>
    public Guid Classification
    {
        get => Read<Guid>("classification");
        init => Write("classification", value);
    }
    /// <summary>Wire field key; missing and null remain distinct.</summary>
    public string Key
    {
        get => Read<string>("key");
        init => Write("key", value);
    }
}

/// <summary>Schema-derived Decision wire record. Exports and nested reads are detached.</summary>
public sealed class Decision : WireRecord
{
    public Decision() { }
    public Decision(JsonObject data) : base(data) { }

    /// <summary>Wire field at; missing and null remain distinct.</summary>
    public DateOnly At
    {
        get => Read<DateOnly>("at");
        init => Write("at", value);
    }
    /// <summary>Wire field fallback; missing and null remain distinct.</summary>
    public IReadOnlyList<Action> Fallback
    {
        get => Read<IReadOnlyList<Action>>("fallback");
        init => Write("fallback", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field observations; missing and null remain distinct.</summary>
    public IReadOnlyList<ObservationBinding> Observations
    {
        get => Read<IReadOnlyList<ObservationBinding>>("observations");
        init => Write("observations", value);
    }
    /// <summary>Wire field rules; missing and null remain distinct.</summary>
    public IReadOnlyList<Rule> Rules
    {
        get => Read<IReadOnlyList<Rule>>("rules");
        init => Write("rules", value);
    }
}

/// <summary>Schema-derived DecisionOutcome wire record. Exports and nested reads are detached.</summary>
public sealed class DecisionOutcome : WireRecord
{
    public DecisionOutcome() { }
    public DecisionOutcome(JsonObject data) : base(data) { }

    /// <summary>Wire field assignments; missing and null remain distinct.</summary>
    public IReadOnlyList<Assignment> Assignments
    {
        get => Read<IReadOnlyList<Assignment>>("assignments");
        init => Write("assignments", value);
    }
    /// <summary>Wire field at; missing and null remain distinct.</summary>
    public DateOnly At
    {
        get => Read<DateOnly>("at");
        init => Write("at", value);
    }
    /// <summary>Wire field decision; missing and null remain distinct.</summary>
    public Guid Decision
    {
        get => Read<Guid>("decision");
        init => Write("decision", value);
    }
    /// <summary>Wire field observations; missing and null remain distinct.</summary>
    public IReadOnlyList<ObservedQuantity> Observations
    {
        get => Read<IReadOnlyList<ObservedQuantity>>("observations");
        init => Write("observations", value);
    }
    /// <summary>Wire field rule; missing and null remain distinct.</summary>
    public Optional<Guid> Rule
    {
        get => ReadOptional<Guid>("rule");
        init => WriteOptional("rule", value);
    }
    /// <summary>Wire field terminated; missing and null remain distinct.</summary>
    public bool Terminated
    {
        get => Read<bool>("terminated");
        init => Write("terminated", value);
    }
    /// <summary>Wire field termination_reason; missing and null remain distinct.</summary>
    public Optional<string> TerminationReason
    {
        get => ReadOptional<string>("termination_reason");
        init => WriteOptional("termination_reason", value);
    }
}

/// <summary>Schema-derived Definitions wire record. Exports and nested reads are detached.</summary>
public sealed class Definitions : WireRecord
{
    public Definitions() { }
    public Definitions(JsonObject data) : base(data) { }

    /// <summary>Wire field functions; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Function>> Functions
    {
        get => ReadOptional<IReadOnlyList<Function>>("functions");
        init => WriteOptional("functions", value);
    }
    /// <summary>Wire field measures; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Measure>> Measures
    {
        get => ReadOptional<IReadOnlyList<Measure>>("measures");
        init => WriteOptional("measures", value);
    }
    /// <summary>Wire field taxonomies; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Taxonomy>> Taxonomies
    {
        get => ReadOptional<IReadOnlyList<Taxonomy>>("taxonomies");
        init => WriteOptional("taxonomies", value);
    }
}

/// <summary>Schema-derived Diagnostic wire record. Exports and nested reads are detached.</summary>
public sealed class Diagnostic : WireRecord
{
    public Diagnostic() { }
    public Diagnostic(JsonObject data) : base(data) { }

    /// <summary>Wire field code; missing and null remain distinct.</summary>
    public string Code
    {
        get => Read<string>("code");
        init => Write("code", value);
    }
    /// <summary>Wire field document; missing and null remain distinct.</summary>
    public Optional<Guid> Document
    {
        get => ReadOptional<Guid>("document");
        init => WriteOptional("document", value);
    }
    /// <summary>Wire field message; missing and null remain distinct.</summary>
    public string Message
    {
        get => Read<string>("message");
        init => Write("message", value);
    }
    /// <summary>Wire field references; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Reference>> References
    {
        get => ReadOptional<IReadOnlyList<Reference>>("references");
        init => WriteOptional("references", value);
    }
    /// <summary>Wire field residual; missing and null remain distinct.</summary>
    public Optional<Quantity> Residual
    {
        get => ReadOptional<Quantity>("residual");
        init => WriteOptional("residual", value);
    }
    /// <summary>Wire field severity; missing and null remain distinct.</summary>
    public string Severity
    {
        get => Read<string>("severity");
        init => Write("severity", value);
    }
    /// <summary>Wire field target; missing and null remain distinct.</summary>
    public Optional<Guid> Target
    {
        get => ReadOptional<Guid>("target");
        init => WriteOptional("target", value);
    }
    /// <summary>Wire field tolerance; missing and null remain distinct.</summary>
    public Optional<Quantity> Tolerance
    {
        get => ReadOptional<Quantity>("tolerance");
        init => WriteOptional("tolerance", value);
    }
}

/// <summary>Schema-derived Distribution wire record. Exports and nested reads are detached.</summary>
public sealed class Distribution : WireRecord
{
    public Distribution() { }
    public Distribution(JsonObject data) : base(data) { }

    /// <summary>Wire field kind; missing and null remain distinct.</summary>
    public string Kind
    {
        get => Read<string>("kind");
        init => Write("kind", value);
    }
    /// <summary>Wire field lower; missing and null remain distinct.</summary>
    public double Lower
    {
        get => Read<double>("lower");
        init => Write("lower", value);
    }
    /// <summary>Wire field mode; missing and null remain distinct.</summary>
    public Optional<double> Mode
    {
        get => ReadOptional<double>("mode");
        init => WriteOptional("mode", value);
    }
    /// <summary>Wire field units; missing and null remain distinct.</summary>
    public string Units
    {
        get => Read<string>("units");
        init => Write("units", value);
    }
    /// <summary>Wire field upper; missing and null remain distinct.</summary>
    public double Upper
    {
        get => Read<double>("upper");
        init => Write("upper", value);
    }
    /// <summary>Wire field weighting; missing and null remain distinct.</summary>
    public Optional<double> Weighting
    {
        get => ReadOptional<double>("weighting");
        init => WriteOptional("weighting", value);
    }
}

/// <summary>Schema-derived Domain wire record. Exports and nested reads are detached.</summary>
public sealed class Domain : WireRecord
{
    public Domain() { }
    public Domain(JsonObject data) : base(data) { }

    /// <summary>Wire field collection_kind; missing and null remain distinct.</summary>
    public Optional<string> CollectionKind
    {
        get => ReadOptional<string>("collection_kind");
        init => WriteOptional("collection_kind", value);
    }
    /// <summary>Wire field item_domain; missing and null remain distinct.</summary>
    public Optional<Domain> ItemDomain
    {
        get => ReadOptional<Domain>("item_domain");
        init => WriteOptional("item_domain", value);
    }
    /// <summary>Wire field kind; missing and null remain distinct.</summary>
    public string Kind
    {
        get => Read<string>("kind");
        init => Write("kind", value);
    }
    /// <summary>Wire field measure; missing and null remain distinct.</summary>
    public Optional<Guid> Measure
    {
        get => ReadOptional<Guid>("measure");
        init => WriteOptional("measure", value);
    }
    /// <summary>Wire field units; missing and null remain distinct.</summary>
    public Optional<string> Units
    {
        get => ReadOptional<string>("units");
        init => WriteOptional("units", value);
    }
}

/// <summary>Schema-derived Entity wire record. Exports and nested reads are detached.</summary>
public sealed class Entity : WireRecord
{
    public Entity() { }
    public Entity(JsonObject data) : base(data) { }

    /// <summary>Wire field characteristics; missing and null remain distinct.</summary>
    public Optional<Characteristics> Characteristics
    {
        get => ReadOptional<Characteristics>("characteristics");
        init => WriteOptional("characteristics", value);
    }
    /// <summary>Wire field classification; missing and null remain distinct.</summary>
    public Optional<Guid> Classification
    {
        get => ReadOptional<Guid>("classification");
        init => WriteOptional("classification", value);
    }
    /// <summary>Wire field code; missing and null remain distinct.</summary>
    public Optional<string> Code
    {
        get => ReadOptional<string>("code");
        init => WriteOptional("code", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public Optional<string> Name
    {
        get => ReadOptional<string>("name");
        init => WriteOptional("name", value);
    }
}

/// <summary>Schema-derived Entry wire record. Exports and nested reads are detached.</summary>
public sealed class Entry : WireRecord
{
    public Entry() { }
    public Entry(JsonObject data) : base(data) { }

    /// <summary>Wire field key; missing and null remain distinct.</summary>
    public string Key
    {
        get => Read<string>("key");
        init => Write("key", value);
    }
    /// <summary>Wire field value; missing and null remain distinct.</summary>
    public string Value
    {
        get => Read<string>("value");
        init => Write("value", value);
    }
}

/// <summary>Schema-derived Expression wire record. Exports and nested reads are detached.</summary>
public sealed class Expression : WireRecord
{
    public Expression() { }
    public Expression(JsonObject data) : base(data) { }

    /// <summary>Wire field boolean; missing and null remain distinct.</summary>
    public Optional<bool> Boolean
    {
        get => ReadOptional<bool>("boolean");
        init => WriteOptional("boolean", value);
    }
    /// <summary>Wire field call; missing and null remain distinct.</summary>
    public Optional<Call> Call
    {
        get => ReadOptional<Call>("call");
        init => WriteOptional("call", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field kind; missing and null remain distinct.</summary>
    public string Kind
    {
        get => Read<string>("kind");
        init => Write("kind", value);
    }
    /// <summary>Wire field operand; missing and null remain distinct.</summary>
    public Optional<Expression> Operand
    {
        get => ReadOptional<Expression>("operand");
        init => WriteOptional("operand", value);
    }
    /// <summary>Wire field operands; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Expression>> Operands
    {
        get => ReadOptional<IReadOnlyList<Expression>>("operands");
        init => WriteOptional("operands", value);
    }
    /// <summary>Wire field operator; missing and null remain distinct.</summary>
    public Optional<string> Operator
    {
        get => ReadOptional<string>("operator");
        init => WriteOptional("operator", value);
    }
    /// <summary>Wire field quantity; missing and null remain distinct.</summary>
    public Optional<Quantity> Quantity
    {
        get => ReadOptional<Quantity>("quantity");
        init => WriteOptional("quantity", value);
    }
    /// <summary>Wire field query; missing and null remain distinct.</summary>
    public Optional<Query> Query
    {
        get => ReadOptional<Query>("query");
        init => WriteOptional("query", value);
    }
    /// <summary>Wire field selection; missing and null remain distinct.</summary>
    public Optional<Selection> Selection
    {
        get => ReadOptional<Selection>("selection");
        init => WriteOptional("selection", value);
    }
    /// <summary>Wire field target; missing and null remain distinct.</summary>
    public Optional<Reference> Target
    {
        get => ReadOptional<Reference>("target");
        init => WriteOptional("target", value);
    }
}

/// <summary>Schema-derived Fact wire record. Exports and nested reads are detached.</summary>
public sealed class Fact : WireRecord
{
    public Fact() { }
    public Fact(JsonObject data) : base(data) { }

    /// <summary>Wire field claims; missing and null remain distinct.</summary>
    public IReadOnlyList<Guid> Claims
    {
        get => Read<IReadOnlyList<Guid>>("claims");
        init => Write("claims", value);
    }
    /// <summary>Wire field reconciliation; missing and null remain distinct.</summary>
    public Optional<Reconciliation> Reconciliation
    {
        get => ReadOptional<Reconciliation>("reconciliation");
        init => WriteOptional("reconciliation", value);
    }
    /// <summary>Wire field target; missing and null remain distinct.</summary>
    public JsonNode Target
    {
        get => Read<JsonNode>("target");
        init => Write("target", value);
    }
}

/// <summary>Schema-derived Filter wire record. Exports and nested reads are detached.</summary>
public sealed class Filter : WireRecord
{
    public Filter() { }
    public Filter(JsonObject data) : base(data) { }

    /// <summary>Wire field classification; missing and null remain distinct.</summary>
    public Optional<Guid> Classification
    {
        get => ReadOptional<Guid>("classification");
        init => WriteOptional("classification", value);
    }
    /// <summary>Wire field labels; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Criterion>> Labels
    {
        get => ReadOptional<IReadOnlyList<Criterion>>("labels");
        init => WriteOptional("labels", value);
    }
}

/// <summary>Schema-derived Flow wire record. Exports and nested reads are detached.</summary>
public sealed class Flow : WireRecord
{
    public Flow() { }
    public Flow(JsonObject data) : base(data) { }

    /// <summary>Wire field movements; missing and null remain distinct.</summary>
    public IReadOnlyList<Movement> Movements
    {
        get => Read<IReadOnlyList<Movement>>("movements");
        init => Write("movements", value);
    }
    /// <summary>Wire field units; missing and null remain distinct.</summary>
    public string Units
    {
        get => Read<string>("units");
        init => Write("units", value);
    }
}

/// <summary>Schema-derived Formulation wire record. Exports and nested reads are detached.</summary>
public sealed class Formulation : WireRecord
{
    public Formulation() { }
    public Formulation(JsonObject data) : base(data) { }

    /// <summary>Wire field bindings; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Binding>> Bindings
    {
        get => ReadOptional<IReadOnlyList<Binding>>("bindings");
        init => WriteOptional("bindings", value);
    }
    /// <summary>Wire field code; missing and null remain distinct.</summary>
    public Optional<string> Code
    {
        get => ReadOptional<string>("code");
        init => WriteOptional("code", value);
    }
    /// <summary>Wire field constraints; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Constraint>> Constraints
    {
        get => ReadOptional<IReadOnlyList<Constraint>>("constraints");
        init => WriteOptional("constraints", value);
    }
    /// <summary>Wire field description; missing and null remain distinct.</summary>
    public Optional<string> Description
    {
        get => ReadOptional<string>("description");
        init => WriteOptional("description", value);
    }
    /// <summary>Wire field expressions; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Expression>> Expressions
    {
        get => ReadOptional<IReadOnlyList<Expression>>("expressions");
        init => WriteOptional("expressions", value);
    }
    /// <summary>Wire field formulations; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Formulation>> Formulations
    {
        get => ReadOptional<IReadOnlyList<Formulation>>("formulations");
        init => WriteOptional("formulations", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public Optional<string> Name
    {
        get => ReadOptional<string>("name");
        init => WriteOptional("name", value);
    }
    /// <summary>Wire field values; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Value>> Values
    {
        get => ReadOptional<IReadOnlyList<Value>>("values");
        init => WriteOptional("values", value);
    }
}

/// <summary>Schema-derived Function wire record. Exports and nested reads are detached.</summary>
public sealed class Function : WireRecord
{
    public Function() { }
    public Function(JsonObject data) : base(data) { }

    /// <summary>Wire field code; missing and null remain distinct.</summary>
    public string Code
    {
        get => Read<string>("code");
        init => Write("code", value);
    }
    /// <summary>Wire field empty_collection; missing and null remain distinct.</summary>
    public Optional<string> EmptyCollection
    {
        get => ReadOptional<string>("empty_collection");
        init => WriteOptional("empty_collection", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
    /// <summary>Wire field parameters; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Parameter>> Parameters
    {
        get => ReadOptional<IReadOnlyList<Parameter>>("parameters");
        init => WriteOptional("parameters", value);
    }
    /// <summary>Wire field result; missing and null remain distinct.</summary>
    public Domain Result
    {
        get => Read<Domain>("result");
        init => Write("result", value);
    }
    /// <summary>Wire field semantics; missing and null remain distinct.</summary>
    public string Semantics
    {
        get => Read<string>("semantics");
        init => Write("semantics", value);
    }
    /// <summary>Wire field unit_rule; missing and null remain distinct.</summary>
    public string UnitRule
    {
        get => Read<string>("unit_rule");
        init => Write("unit_rule", value);
    }
    /// <summary>Wire field version; missing and null remain distinct.</summary>
    public string Version
    {
        get => Read<string>("version");
        init => Write("version", value);
    }
}

/// <summary>Schema-derived Implementation wire record. Exports and nested reads are detached.</summary>
public sealed class Implementation : WireRecord
{
    public Implementation() { }
    public Implementation(JsonObject data) : base(data) { }

    /// <summary>Wire field kind; missing and null remain distinct.</summary>
    public string Kind
    {
        get => Read<string>("kind");
        init => Write("kind", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
    /// <summary>Wire field version; missing and null remain distinct.</summary>
    public string Version
    {
        get => Read<string>("version");
        init => Write("version", value);
    }
}

/// <summary>Schema-derived Label wire record. Exports and nested reads are detached.</summary>
public sealed class Label : WireRecord
{
    public Label() { }
    public Label(JsonObject data) : base(data) { }

    /// <summary>Wire field classifications; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Guid>> Classifications
    {
        get => ReadOptional<IReadOnlyList<Guid>>("classifications");
        init => WriteOptional("classifications", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field key; missing and null remain distinct.</summary>
    public string Key
    {
        get => Read<string>("key");
        init => Write("key", value);
    }
}

/// <summary>Schema-derived LibraryVersion wire record. Exports and nested reads are detached.</summary>
public sealed class LibraryVersion : WireRecord
{
    public LibraryVersion() { }
    public LibraryVersion(JsonObject data) : base(data) { }

    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
    /// <summary>Wire field version; missing and null remain distinct.</summary>
    public string Version
    {
        get => Read<string>("version");
        init => Write("version", value);
    }
}

/// <summary>Schema-derived Location wire record. Exports and nested reads are detached.</summary>
public sealed class Location : WireRecord
{
    public Location() { }
    public Location(JsonObject data) : base(data) { }

    /// <summary>Wire field address; missing and null remain distinct.</summary>
    public Optional<JsonObject> Address
    {
        get => ReadOptional<JsonObject>("address");
        init => WriteOptional("address", value);
    }
    /// <summary>Wire field source; missing and null remain distinct.</summary>
    public Guid Source
    {
        get => Read<Guid>("source");
        init => Write("source", value);
    }
}

/// <summary>Schema-derived Measure wire record. Exports and nested reads are detached.</summary>
public sealed class Measure : WireRecord
{
    public Measure() { }
    public Measure(JsonObject data) : base(data) { }

    /// <summary>Wire field code; missing and null remain distinct.</summary>
    public string Code
    {
        get => Read<string>("code");
        init => Write("code", value);
    }
    /// <summary>Wire field definition; missing and null remain distinct.</summary>
    public Optional<string> Definition
    {
        get => ReadOptional<string>("definition");
        init => WriteOptional("definition", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
    /// <summary>Wire field tags; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<string>> Tags
    {
        get => ReadOptional<IReadOnlyList<string>>("tags");
        init => WriteOptional("tags", value);
    }
    /// <summary>Wire field units; missing and null remain distinct.</summary>
    public string Units
    {
        get => Read<string>("units");
        init => Write("units", value);
    }
}

/// <summary>Schema-derived Measurement wire record. Exports and nested reads are detached.</summary>
public sealed class Measurement : WireRecord
{
    public Measurement() { }
    public Measurement(JsonObject data) : base(data) { }

    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field measure; missing and null remain distinct.</summary>
    public Guid Measure
    {
        get => Read<Guid>("measure");
        init => Write("measure", value);
    }
    /// <summary>Wire field quantity; missing and null remain distinct.</summary>
    public Optional<Quantity> Quantity
    {
        get => ReadOptional<Quantity>("quantity");
        init => WriteOptional("quantity", value);
    }
}

/// <summary>Schema-derived Metadata wire record. Exports and nested reads are detached.</summary>
public sealed class Metadata : WireRecord
{
    public Metadata() { }
    public Metadata(JsonObject data) : base(data) { }

    /// <summary>Wire field description; missing and null remain distinct.</summary>
    public Optional<string> Description
    {
        get => ReadOptional<string>("description");
        init => WriteOptional("description", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public Optional<string> Name
    {
        get => ReadOptional<string>("name");
        init => WriteOptional("name", value);
    }
    /// <summary>Wire field previous; missing and null remain distinct.</summary>
    public Optional<Guid> Previous
    {
        get => ReadOptional<Guid>("previous");
        init => WriteOptional("previous", value);
    }
    /// <summary>Wire field schema_version; missing and null remain distinct.</summary>
    public string SchemaVersion
    {
        get => Read<string>("schema_version");
        init => Write("schema_version", value);
    }
}

/// <summary>Schema-derived Method wire record. Exports and nested reads are detached.</summary>
public sealed class Method : WireRecord
{
    public Method() { }
    public Method(JsonObject data) : base(data) { }

    /// <summary>Wire field code; missing and null remain distinct.</summary>
    public string Code
    {
        get => Read<string>("code");
        init => Write("code", value);
    }
    /// <summary>Wire field description; missing and null remain distinct.</summary>
    public Optional<string> Description
    {
        get => ReadOptional<string>("description");
        init => WriteOptional("description", value);
    }
    /// <summary>Wire field version; missing and null remain distinct.</summary>
    public Optional<string> Version
    {
        get => ReadOptional<string>("version");
        init => WriteOptional("version", value);
    }
}

/// <summary>Schema-derived Model wire record. Exports and nested reads are detached.</summary>
public sealed class Model : WireRecord
{
    public Model() { }
    public Model(JsonObject data) : base(data) { }

    /// <summary>Wire field definitions; missing and null remain distinct.</summary>
    public Optional<Definitions> Definitions
    {
        get => ReadOptional<Definitions>("definitions");
        init => WriteOptional("definitions", value);
    }
    /// <summary>Wire field metadata; missing and null remain distinct.</summary>
    public Metadata Metadata
    {
        get => Read<Metadata>("metadata");
        init => Write("metadata", value);
    }
    /// <summary>Wire field provenance; missing and null remain distinct.</summary>
    public Optional<Provenance> Provenance
    {
        get => ReadOptional<Provenance>("provenance");
        init => WriteOptional("provenance", value);
    }
    /// <summary>Wire field system; missing and null remain distinct.</summary>
    public Optional<System> System
    {
        get => ReadOptional<System>("system");
        init => WriteOptional("system", value);
    }
}

/// <summary>Schema-derived Movement wire record. Exports and nested reads are detached.</summary>
public sealed class Movement : WireRecord
{
    public Movement() { }
    public Movement(JsonObject data) : base(data) { }

    /// <summary>Wire field claims; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Guid>> Claims
    {
        get => ReadOptional<IReadOnlyList<Guid>>("claims");
        init => WriteOptional("claims", value);
    }
    /// <summary>Wire field date; missing and null remain distinct.</summary>
    public Optional<DateOnly> Date
    {
        get => ReadOptional<DateOnly>("date");
        init => WriteOptional("date", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field key; missing and null remain distinct.</summary>
    public Optional<string> Key
    {
        get => ReadOptional<string>("key");
        init => WriteOptional("key", value);
    }
    /// <summary>Wire field magnitude; missing and null remain distinct.</summary>
    public Optional<decimal> Magnitude
    {
        get => ReadOptional<decimal>("magnitude");
        init => WriteOptional("magnitude", value);
    }
    /// <summary>Wire field period; missing and null remain distinct.</summary>
    public Optional<Period> Period
    {
        get => ReadOptional<Period>("period");
        init => WriteOptional("period", value);
    }
}

/// <summary>Schema-derived Objective wire record. Exports and nested reads are detached.</summary>
public sealed class Objective : WireRecord
{
    public Objective() { }
    public Objective(JsonObject data) : base(data) { }

    /// <summary>Wire field expression; missing and null remain distinct.</summary>
    public Guid Expression
    {
        get => Read<Guid>("expression");
        init => Write("expression", value);
    }
    /// <summary>Wire field sense; missing and null remain distinct.</summary>
    public string Sense
    {
        get => Read<string>("sense");
        init => Write("sense", value);
    }
}

/// <summary>Schema-derived ObservationAvailability wire record. Exports and nested reads are detached.</summary>
public sealed class ObservationAvailability : WireRecord
{
    public ObservationAvailability() { }
    public ObservationAvailability(JsonObject data) : base(data) { }

    /// <summary>Wire field available_at; missing and null remain distinct.</summary>
    public DateOnly AvailableAt
    {
        get => Read<DateOnly>("available_at");
        init => Write("available_at", value);
    }
    /// <summary>Wire field target; missing and null remain distinct.</summary>
    public Reference Target
    {
        get => Read<Reference>("target");
        init => Write("target", value);
    }
}

/// <summary>Schema-derived ObservationBinding wire record. Exports and nested reads are detached.</summary>
public sealed class ObservationBinding : WireRecord
{
    public ObservationBinding() { }
    public ObservationBinding(JsonObject data) : base(data) { }

    /// <summary>Wire field available_at; missing and null remain distinct.</summary>
    public Optional<DateOnly> AvailableAt
    {
        get => ReadOptional<DateOnly>("available_at");
        init => WriteOptional("available_at", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
    /// <summary>Wire field target; missing and null remain distinct.</summary>
    public Reference Target
    {
        get => Read<Reference>("target");
        init => Write("target", value);
    }
}

/// <summary>Schema-derived ObservedQuantity wire record. Exports and nested reads are detached.</summary>
public sealed class ObservedQuantity : WireRecord
{
    public ObservedQuantity() { }
    public ObservedQuantity(JsonObject data) : base(data) { }

    /// <summary>Wire field available_at; missing and null remain distinct.</summary>
    public DateOnly AvailableAt
    {
        get => Read<DateOnly>("available_at");
        init => Write("available_at", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
    /// <summary>Wire field quantity; missing and null remain distinct.</summary>
    public Quantity Quantity
    {
        get => Read<Quantity>("quantity");
        init => Write("quantity", value);
    }
    /// <summary>Wire field target; missing and null remain distinct.</summary>
    public Reference Target
    {
        get => Read<Reference>("target");
        init => Write("target", value);
    }
}

/// <summary>Schema-derived Parameter wire record. Exports and nested reads are detached.</summary>
public sealed class Parameter : WireRecord
{
    public Parameter() { }
    public Parameter(JsonObject data) : base(data) { }

    /// <summary>Wire field domain; missing and null remain distinct.</summary>
    public Domain Domain
    {
        get => Read<Domain>("domain");
        init => Write("domain", value);
    }
    /// <summary>Wire field kind; missing and null remain distinct.</summary>
    public string Kind
    {
        get => Read<string>("kind");
        init => Write("kind", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
    /// <summary>Wire field required; missing and null remain distinct.</summary>
    public bool Required
    {
        get => Read<bool>("required");
        init => Write("required", value);
    }
}

/// <summary>Schema-derived Period wire record. Exports and nested reads are detached.</summary>
public sealed class Period : WireRecord
{
    public Period() { }
    public Period(JsonObject data) : base(data) { }

    /// <summary>Wire field end_exclusive; missing and null remain distinct.</summary>
    public DateOnly EndExclusive
    {
        get => Read<DateOnly>("end_exclusive");
        init => Write("end_exclusive", value);
    }
    /// <summary>Wire field start_inclusive; missing and null remain distinct.</summary>
    public DateOnly StartInclusive
    {
        get => Read<DateOnly>("start_inclusive");
        init => Write("start_inclusive", value);
    }
}

/// <summary>Schema-derived Policy wire record. Exports and nested reads are detached.</summary>
public sealed class Policy : WireRecord
{
    public Policy() { }
    public Policy(JsonObject data) : base(data) { }

    /// <summary>Wire field decisions; missing and null remain distinct.</summary>
    public IReadOnlyList<Decision> Decisions
    {
        get => Read<IReadOnlyList<Decision>>("decisions");
        init => Write("decisions", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field targets; missing and null remain distinct.</summary>
    public IReadOnlyList<Reference> Targets
    {
        get => Read<IReadOnlyList<Reference>>("targets");
        init => Write("targets", value);
    }
}

/// <summary>Schema-derived Projection wire record. Exports and nested reads are detached.</summary>
public sealed class Projection : WireRecord
{
    public Projection() { }
    public Projection(JsonObject data) : base(data) { }

    /// <summary>Wire field cardinality; missing and null remain distinct.</summary>
    public Optional<string> Cardinality
    {
        get => ReadOptional<string>("cardinality");
        init => WriteOptional("cardinality", value);
    }
    /// <summary>Wire field key; missing and null remain distinct.</summary>
    public Optional<string> Key
    {
        get => ReadOptional<string>("key");
        init => WriteOptional("key", value);
    }
    /// <summary>Wire field kind; missing and null remain distinct.</summary>
    public string Kind
    {
        get => Read<string>("kind");
        init => Write("kind", value);
    }
    /// <summary>Wire field measure; missing and null remain distinct.</summary>
    public Optional<Guid> Measure
    {
        get => ReadOptional<Guid>("measure");
        init => WriteOptional("measure", value);
    }
    /// <summary>Wire field missing; missing and null remain distinct.</summary>
    public Optional<string> Missing
    {
        get => ReadOptional<string>("missing");
        init => WriteOptional("missing", value);
    }
}

/// <summary>Schema-derived PropertyContent wire record. Exports and nested reads are detached.</summary>
public sealed class PropertyContent : WireRecord
{
    public PropertyContent() { }
    public PropertyContent(JsonObject data) : base(data) { }

    /// <summary>Wire field entries; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<ContentEntry>> Entries
    {
        get => ReadOptional<IReadOnlyList<ContentEntry>>("entries");
        init => WriteOptional("entries", value);
    }
    /// <summary>Wire field fold; missing and null remain distinct.</summary>
    public Optional<global::System.Numerics.BigInteger> Fold
    {
        get => ReadOptional<global::System.Numerics.BigInteger>("fold");
        init => WriteOptional("fold", value);
    }
    /// <summary>Wire field items; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<PropertyContent>> Items
    {
        get => ReadOptional<IReadOnlyList<PropertyContent>>("items");
        init => WriteOptional("items", value);
    }
    /// <summary>Wire field kind; missing and null remain distinct.</summary>
    public string Kind
    {
        get => Read<string>("kind");
        init => Write("kind", value);
    }
    /// <summary>Wire field text; missing and null remain distinct.</summary>
    public Optional<string> Text
    {
        get => ReadOptional<string>("text");
        init => WriteOptional("text", value);
    }
    /// <summary>Wire field zone; missing and null remain distinct.</summary>
    public Optional<string> Zone
    {
        get => ReadOptional<string>("zone");
        init => WriteOptional("zone", value);
    }
}

/// <summary>Schema-derived Provenance wire record. Exports and nested reads are detached.</summary>
public sealed class Provenance : WireRecord
{
    public Provenance() { }
    public Provenance(JsonObject data) : base(data) { }

    /// <summary>Wire field claims; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Claim>> Claims
    {
        get => ReadOptional<IReadOnlyList<Claim>>("claims");
        init => WriteOptional("claims", value);
    }
    /// <summary>Wire field facts; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Fact>> Facts
    {
        get => ReadOptional<IReadOnlyList<Fact>>("facts");
        init => WriteOptional("facts", value);
    }
    /// <summary>Wire field scenarios; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<ScenarioRealization>> Scenarios
    {
        get => ReadOptional<IReadOnlyList<ScenarioRealization>>("scenarios");
        init => WriteOptional("scenarios", value);
    }
    /// <summary>Wire field sources; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Source>> Sources
    {
        get => ReadOptional<IReadOnlyList<Source>>("sources");
        init => WriteOptional("sources", value);
    }
}

/// <summary>Schema-derived Quantity wire record. Exports and nested reads are detached.</summary>
public sealed class Quantity : WireRecord
{
    public Quantity() { }
    public Quantity(JsonObject data) : base(data) { }

    /// <summary>Wire field magnitude; missing and null remain distinct.</summary>
    public decimal Magnitude
    {
        get => Read<decimal>("magnitude");
        init => Write("magnitude", value);
    }
    /// <summary>Wire field units; missing and null remain distinct.</summary>
    public string Units
    {
        get => Read<string>("units");
        init => Write("units", value);
    }
}

/// <summary>Schema-derived Query wire record. Exports and nested reads are detached.</summary>
public sealed class Query : WireRecord
{
    public Query() { }
    public Query(JsonObject data) : base(data) { }

    /// <summary>Wire field duplicates; missing and null remain distinct.</summary>
    public string Duplicates
    {
        get => Read<string>("duplicates");
        init => Write("duplicates", value);
    }
    /// <summary>Wire field filter; missing and null remain distinct.</summary>
    public Optional<Filter> Filter
    {
        get => ReadOptional<Filter>("filter");
        init => WriteOptional("filter", value);
    }
    /// <summary>Wire field projection; missing and null remain distinct.</summary>
    public Projection Projection
    {
        get => Read<Projection>("projection");
        init => Write("projection", value);
    }
    /// <summary>Wire field starting_at; missing and null remain distinct.</summary>
    public Guid StartingAt
    {
        get => Read<Guid>("starting_at");
        init => Write("starting_at", value);
    }
    /// <summary>Wire field steps; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Traversal>> Steps
    {
        get => ReadOptional<IReadOnlyList<Traversal>>("steps");
        init => WriteOptional("steps", value);
    }
}

/// <summary>Schema-derived RandomStream wire record. Exports and nested reads are detached.</summary>
public sealed class RandomStream : WireRecord
{
    public RandomStream() { }
    public RandomStream(JsonObject data) : base(data) { }

    /// <summary>Wire field identifier; missing and null remain distinct.</summary>
    public string Identifier
    {
        get => Read<string>("identifier");
        init => Write("identifier", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
}

/// <summary>Schema-derived Reconciliation wire record. Exports and nested reads are detached.</summary>
public sealed class Reconciliation : WireRecord
{
    public Reconciliation() { }
    public Reconciliation(JsonObject data) : base(data) { }

    /// <summary>Wire field method; missing and null remain distinct.</summary>
    public Optional<Method> Method
    {
        get => ReadOptional<Method>("method");
        init => WriteOptional("method", value);
    }
    /// <summary>Wire field selected; missing and null remain distinct.</summary>
    public Guid Selected
    {
        get => Read<Guid>("selected");
        init => Write("selected", value);
    }
    /// <summary>Wire field status; missing and null remain distinct.</summary>
    public string Status
    {
        get => Read<string>("status");
        init => Write("status", value);
    }
}

/// <summary>Schema-derived Reference wire record. Exports and nested reads are detached.</summary>
public sealed class Reference : WireRecord
{
    public Reference() { }
    public Reference(JsonObject data) : base(data) { }

    /// <summary>Wire field target; missing and null remain distinct.</summary>
    public Guid Target
    {
        get => Read<Guid>("target");
        init => Write("target", value);
    }
}

/// <summary>Schema-derived Relationship wire record. Exports and nested reads are detached.</summary>
public sealed class Relationship : WireRecord
{
    public Relationship() { }
    public Relationship(JsonObject data) : base(data) { }

    /// <summary>Wire field characteristics; missing and null remain distinct.</summary>
    public Optional<Characteristics> Characteristics
    {
        get => ReadOptional<Characteristics>("characteristics");
        init => WriteOptional("characteristics", value);
    }
    /// <summary>Wire field classification; missing and null remain distinct.</summary>
    public Guid Classification
    {
        get => Read<Guid>("classification");
        init => Write("classification", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field source; missing and null remain distinct.</summary>
    public Guid Source
    {
        get => Read<Guid>("source");
        init => Write("source", value);
    }
    /// <summary>Wire field target; missing and null remain distinct.</summary>
    public Guid Target
    {
        get => Read<Guid>("target");
        init => Write("target", value);
    }
}

/// <summary>Schema-derived Report wire record. Exports and nested reads are detached.</summary>
public sealed class Report : WireRecord
{
    public Report() { }
    public Report(JsonObject data) : base(data) { }

    /// <summary>Wire field diagnostics; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Diagnostic>> Diagnostics
    {
        get => ReadOptional<IReadOnlyList<Diagnostic>>("diagnostics");
        init => WriteOptional("diagnostics", value);
    }
    /// <summary>Wire field outcomes; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<DecisionOutcome>> Outcomes
    {
        get => ReadOptional<IReadOnlyList<DecisionOutcome>>("outcomes");
        init => WriteOptional("outcomes", value);
    }
    /// <summary>Wire field runtime; missing and null remain distinct.</summary>
    public Optional<Runtime> Runtime
    {
        get => ReadOptional<Runtime>("runtime");
        init => WriteOptional("runtime", value);
    }
    /// <summary>Wire field status; missing and null remain distinct.</summary>
    public Status Status
    {
        get => Read<Status>("status");
        init => Write("status", value);
    }
    /// <summary>Wire field trace; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Step>> Trace
    {
        get => ReadOptional<IReadOnlyList<Step>>("trace");
        init => WriteOptional("trace", value);
    }
}

/// <summary>Schema-derived Rule wire record. Exports and nested reads are detached.</summary>
public sealed class Rule : WireRecord
{
    public Rule() { }
    public Rule(JsonObject data) : base(data) { }

    /// <summary>Wire field actions; missing and null remain distinct.</summary>
    public IReadOnlyList<Action> Actions
    {
        get => Read<IReadOnlyList<Action>>("actions");
        init => Write("actions", value);
    }
    /// <summary>Wire field condition; missing and null remain distinct.</summary>
    public Expression Condition
    {
        get => Read<Expression>("condition");
        init => Write("condition", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
}

/// <summary>Schema-derived Run wire record. Exports and nested reads are detached.</summary>
public sealed class Run : WireRecord
{
    public Run() { }
    public Run(JsonObject data) : base(data) { }

    /// <summary>Wire field metadata; missing and null remain distinct.</summary>
    public Metadata Metadata
    {
        get => Read<Metadata>("metadata");
        init => Write("metadata", value);
    }
    /// <summary>Wire field outputs; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Guid>> Outputs
    {
        get => ReadOptional<IReadOnlyList<Guid>>("outputs");
        init => WriteOptional("outputs", value);
    }
    /// <summary>Wire field report; missing and null remain distinct.</summary>
    public Report Report
    {
        get => Read<Report>("report");
        init => Write("report", value);
    }
    /// <summary>Wire field spawns; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Guid>> Spawns
    {
        get => ReadOptional<IReadOnlyList<Guid>>("spawns");
        init => WriteOptional("spawns", value);
    }
    /// <summary>Wire field specification; missing and null remain distinct.</summary>
    public Guid Specification
    {
        get => Read<Guid>("specification");
        init => Write("specification", value);
    }
}

/// <summary>Schema-derived Runtime wire record. Exports and nested reads are detached.</summary>
public sealed class Runtime : WireRecord
{
    public Runtime() { }
    public Runtime(JsonObject data) : base(data) { }

    /// <summary>Wire field finished_at; missing and null remain distinct.</summary>
    public Optional<DateTimeOffset> FinishedAt
    {
        get => ReadOptional<DateTimeOffset>("finished_at");
        init => WriteOptional("finished_at", value);
    }
    /// <summary>Wire field implementations; missing and null remain distinct.</summary>
    public IReadOnlyList<Implementation> Implementations
    {
        get => Read<IReadOnlyList<Implementation>>("implementations");
        init => Write("implementations", value);
    }
    /// <summary>Wire field settings; missing and null remain distinct.</summary>
    public Optional<Settings> Settings
    {
        get => ReadOptional<Settings>("settings");
        init => WriteOptional("settings", value);
    }
    /// <summary>Wire field started_at; missing and null remain distinct.</summary>
    public Optional<DateTimeOffset> StartedAt
    {
        get => ReadOptional<DateTimeOffset>("started_at");
        init => WriteOptional("started_at", value);
    }
}

/// <summary>Schema-derived ScenarioParameter wire record. Exports and nested reads are detached.</summary>
public sealed class ScenarioParameter : WireRecord
{
    public ScenarioParameter() { }
    public ScenarioParameter(JsonObject data) : base(data) { }

    /// <summary>Wire field distribution; missing and null remain distinct.</summary>
    public Optional<Distribution> Distribution
    {
        get => ReadOptional<Distribution>("distribution");
        init => WriteOptional("distribution", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
    /// <summary>Wire field quantity; missing and null remain distinct.</summary>
    public Optional<Quantity> Quantity
    {
        get => ReadOptional<Quantity>("quantity");
        init => WriteOptional("quantity", value);
    }
}

/// <summary>Schema-derived ScenarioPlan wire record. Exports and nested reads are detached.</summary>
public sealed class ScenarioPlan : WireRecord
{
    public ScenarioPlan() { }
    public ScenarioPlan(JsonObject data) : base(data) { }

    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field method; missing and null remain distinct.</summary>
    public string Method
    {
        get => Read<string>("method");
        init => Write("method", value);
    }
    /// <summary>Wire field parameters; missing and null remain distinct.</summary>
    public IReadOnlyList<ScenarioParameter> Parameters
    {
        get => Read<IReadOnlyList<ScenarioParameter>>("parameters");
        init => Write("parameters", value);
    }
    /// <summary>Wire field periods; missing and null remain distinct.</summary>
    public IReadOnlyList<Period> Periods
    {
        get => Read<IReadOnlyList<Period>>("periods");
        init => Write("periods", value);
    }
    /// <summary>Wire field seed; missing and null remain distinct.</summary>
    public global::System.Numerics.BigInteger Seed
    {
        get => Read<global::System.Numerics.BigInteger>("seed");
        init => Write("seed", value);
    }
}

/// <summary>Schema-derived ScenarioRealization wire record. Exports and nested reads are detached.</summary>
public sealed class ScenarioRealization : WireRecord
{
    public ScenarioRealization() { }
    public ScenarioRealization(JsonObject data) : base(data) { }

    /// <summary>Wire field availability; missing and null remain distinct.</summary>
    public IReadOnlyList<ObservationAvailability> Availability
    {
        get => Read<IReadOnlyList<ObservationAvailability>>("availability");
        init => Write("availability", value);
    }
    /// <summary>Wire field calculation; missing and null remain distinct.</summary>
    public Optional<CalculationProvenance> Calculation
    {
        get => ReadOptional<CalculationProvenance>("calculation");
        init => WriteOptional("calculation", value);
    }
    /// <summary>Wire field generator; missing and null remain distinct.</summary>
    public string Generator
    {
        get => Read<string>("generator");
        init => Write("generator", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field inputs; missing and null remain distinct.</summary>
    public IReadOnlyList<Binding> Inputs
    {
        get => Read<IReadOnlyList<Binding>>("inputs");
        init => Write("inputs", value);
    }
    /// <summary>Wire field key; missing and null remain distinct.</summary>
    public string Key
    {
        get => Read<string>("key");
        init => Write("key", value);
    }
    /// <summary>Wire field outputs; missing and null remain distinct.</summary>
    public IReadOnlyList<Binding> Outputs
    {
        get => Read<IReadOnlyList<Binding>>("outputs");
        init => Write("outputs", value);
    }
    /// <summary>Wire field plan; missing and null remain distinct.</summary>
    public ScenarioPlan Plan
    {
        get => Read<ScenarioPlan>("plan");
        init => Write("plan", value);
    }
    /// <summary>Wire field streams; missing and null remain distinct.</summary>
    public IReadOnlyList<RandomStream> Streams
    {
        get => Read<IReadOnlyList<RandomStream>>("streams");
        init => Write("streams", value);
    }
    /// <summary>Wire field versions; missing and null remain distinct.</summary>
    public IReadOnlyList<LibraryVersion> Versions
    {
        get => Read<IReadOnlyList<LibraryVersion>>("versions");
        init => Write("versions", value);
    }
}

/// <summary>Schema-derived Selection wire record. Exports and nested reads are detached.</summary>
public sealed class Selection : WireRecord
{
    public Selection() { }
    public Selection(JsonObject data) : base(data) { }

    /// <summary>Wire field base; missing and null remain distinct.</summary>
    public Expression Base
    {
        get => Read<Expression>("base");
        init => Write("base", value);
    }
    /// <summary>Wire field index; missing and null remain distinct.</summary>
    public Optional<Expression> Index
    {
        get => ReadOptional<Expression>("index");
        init => WriteOptional("index", value);
    }
    /// <summary>Wire field kind; missing and null remain distinct.</summary>
    public string Kind
    {
        get => Read<string>("kind");
        init => Write("kind", value);
    }
    /// <summary>Wire field member; missing and null remain distinct.</summary>
    public Optional<string> Member
    {
        get => ReadOptional<string>("member");
        init => WriteOptional("member", value);
    }
}

/// <summary>Schema-derived Settings wire record. Exports and nested reads are detached.</summary>
public sealed class Settings : WireRecord
{
    public Settings() { }
    public Settings(JsonObject data) : base(data) { }

    /// <summary>Wire field constraint_limit; missing and null remain distinct.</summary>
    public Optional<global::System.Numerics.BigInteger> ConstraintLimit
    {
        get => ReadOptional<global::System.Numerics.BigInteger>("constraint_limit");
        init => WriteOptional("constraint_limit", value);
    }
    /// <summary>Wire field iteration_limit; missing and null remain distinct.</summary>
    public Optional<global::System.Numerics.BigInteger> IterationLimit
    {
        get => ReadOptional<global::System.Numerics.BigInteger>("iteration_limit");
        init => WriteOptional("iteration_limit", value);
    }
    /// <summary>Wire field relative_tolerance; missing and null remain distinct.</summary>
    public Optional<decimal> RelativeTolerance
    {
        get => ReadOptional<decimal>("relative_tolerance");
        init => WriteOptional("relative_tolerance", value);
    }
    /// <summary>Wire field symbol_limit; missing and null remain distinct.</summary>
    public Optional<global::System.Numerics.BigInteger> SymbolLimit
    {
        get => ReadOptional<global::System.Numerics.BigInteger>("symbol_limit");
        init => WriteOptional("symbol_limit", value);
    }
    /// <summary>Wire field time_limit; missing and null remain distinct.</summary>
    public Optional<decimal> TimeLimit
    {
        get => ReadOptional<decimal>("time_limit");
        init => WriteOptional("time_limit", value);
    }
}

/// <summary>Schema-derived Source wire record. Exports and nested reads are detached.</summary>
public sealed class Source : WireRecord
{
    public Source() { }
    public Source(JsonObject data) : base(data) { }

    /// <summary>Wire field author; missing and null remain distinct.</summary>
    public Optional<string> Author
    {
        get => ReadOptional<string>("author");
        init => WriteOptional("author", value);
    }
    /// <summary>Wire field checksum; missing and null remain distinct.</summary>
    public string Checksum
    {
        get => Read<string>("checksum");
        init => Write("checksum", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field issued_at; missing and null remain distinct.</summary>
    public Optional<JsonNode> IssuedAt
    {
        get => ReadOptional<JsonNode>("issued_at");
        init => WriteOptional("issued_at", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
    /// <summary>Wire field received_at; missing and null remain distinct.</summary>
    public Optional<JsonNode> ReceivedAt
    {
        get => ReadOptional<JsonNode>("received_at");
        init => WriteOptional("received_at", value);
    }
}

/// <summary>Schema-derived Span wire record. Exports and nested reads are detached.</summary>
public sealed class Span : WireRecord
{
    public Span() { }
    public Span(JsonObject data) : base(data) { }

    /// <summary>Wire field end_exclusive; missing and null remain distinct.</summary>
    public DateOnly EndExclusive
    {
        get => Read<DateOnly>("end_exclusive");
        init => Write("end_exclusive", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public Optional<string> Name
    {
        get => ReadOptional<string>("name");
        init => WriteOptional("name", value);
    }
    /// <summary>Wire field start_inclusive; missing and null remain distinct.</summary>
    public DateOnly StartInclusive
    {
        get => Read<DateOnly>("start_inclusive");
        init => Write("start_inclusive", value);
    }
}

/// <summary>Schema-derived Specification wire record. Exports and nested reads are detached.</summary>
public sealed class Specification : WireRecord
{
    public Specification() { }
    public Specification(JsonObject data) : base(data) { }

    /// <summary>Wire field assignments; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Assignment>> Assignments
    {
        get => ReadOptional<IReadOnlyList<Assignment>>("assignments");
        init => WriteOptional("assignments", value);
    }
    /// <summary>Wire field cases; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Guid>> Cases
    {
        get => ReadOptional<IReadOnlyList<Guid>>("cases");
        init => WriteOptional("cases", value);
    }
    /// <summary>Wire field estimates; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Assignment>> Estimates
    {
        get => ReadOptional<IReadOnlyList<Assignment>>("estimates");
        init => WriteOptional("estimates", value);
    }
    /// <summary>Wire field formulations; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Formulation>> Formulations
    {
        get => ReadOptional<IReadOnlyList<Formulation>>("formulations");
        init => WriteOptional("formulations", value);
    }
    /// <summary>Wire field includes; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Guid>> Includes
    {
        get => ReadOptional<IReadOnlyList<Guid>>("includes");
        init => WriteOptional("includes", value);
    }
    /// <summary>Wire field metadata; missing and null remain distinct.</summary>
    public Metadata Metadata
    {
        get => Read<Metadata>("metadata");
        init => Write("metadata", value);
    }
    /// <summary>Wire field model; missing and null remain distinct.</summary>
    public Optional<Guid> Model
    {
        get => ReadOptional<Guid>("model");
        init => WriteOptional("model", value);
    }
    /// <summary>Wire field objectives; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Objective>> Objectives
    {
        get => ReadOptional<IReadOnlyList<Objective>>("objectives");
        init => WriteOptional("objectives", value);
    }
    /// <summary>Wire field policy; missing and null remain distinct.</summary>
    public Optional<Policy> Policy
    {
        get => ReadOptional<Policy>("policy");
        init => WriteOptional("policy", value);
    }
    /// <summary>Wire field settings; missing and null remain distinct.</summary>
    public Optional<Settings> Settings
    {
        get => ReadOptional<Settings>("settings");
        init => WriteOptional("settings", value);
    }
    /// <summary>Wire field unknowns; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Reference>> Unknowns
    {
        get => ReadOptional<IReadOnlyList<Reference>>("unknowns");
        init => WriteOptional("unknowns", value);
    }
}

/// <summary>Schema-derived Status wire record. Exports and nested reads are detached.</summary>
public sealed class Status : WireRecord
{
    public Status() { }
    public Status(JsonObject data) : base(data) { }

    /// <summary>Wire field completion; missing and null remain distinct.</summary>
    public string Completion
    {
        get => Read<string>("completion");
        init => Write("completion", value);
    }
    /// <summary>Wire field solution; missing and null remain distinct.</summary>
    public string Solution
    {
        get => Read<string>("solution");
        init => Write("solution", value);
    }
}

/// <summary>Schema-derived Step wire record. Exports and nested reads are detached.</summary>
public sealed class Step : WireRecord
{
    public Step() { }
    public Step(JsonObject data) : base(data) { }

    /// <summary>Wire field at; missing and null remain distinct.</summary>
    public Optional<DateTimeOffset> At
    {
        get => ReadOptional<DateTimeOffset>("at");
        init => WriteOptional("at", value);
    }
    /// <summary>Wire field document; missing and null remain distinct.</summary>
    public Optional<Guid> Document
    {
        get => ReadOptional<Guid>("document");
        init => WriteOptional("document", value);
    }
    /// <summary>Wire field kind; missing and null remain distinct.</summary>
    public string Kind
    {
        get => Read<string>("kind");
        init => Write("kind", value);
    }
    /// <summary>Wire field message; missing and null remain distinct.</summary>
    public string Message
    {
        get => Read<string>("message");
        init => Write("message", value);
    }
    /// <summary>Wire field target; missing and null remain distinct.</summary>
    public Optional<Guid> Target
    {
        get => ReadOptional<Guid>("target");
        init => WriteOptional("target", value);
    }
}

/// <summary>Schema-derived System wire record. Exports and nested reads are detached.</summary>
public sealed class System : WireRecord
{
    public System() { }
    public System(JsonObject data) : base(data) { }

    /// <summary>Wire field assemblies; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Assembly>> Assemblies
    {
        get => ReadOptional<IReadOnlyList<Assembly>>("assemblies");
        init => WriteOptional("assemblies", value);
    }
    /// <summary>Wire field entities; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Entity>> Entities
    {
        get => ReadOptional<IReadOnlyList<Entity>>("entities");
        init => WriteOptional("entities", value);
    }
    /// <summary>Wire field formulations; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Formulation>> Formulations
    {
        get => ReadOptional<IReadOnlyList<Formulation>>("formulations");
        init => WriteOptional("formulations", value);
    }
    /// <summary>Wire field relationships; missing and null remain distinct.</summary>
    public Optional<IReadOnlyList<Relationship>> Relationships
    {
        get => ReadOptional<IReadOnlyList<Relationship>>("relationships");
        init => WriteOptional("relationships", value);
    }
}

/// <summary>Schema-derived Taxonomy wire record. Exports and nested reads are detached.</summary>
public sealed class Taxonomy : WireRecord
{
    public Taxonomy() { }
    public Taxonomy(JsonObject data) : base(data) { }

    /// <summary>Wire field classifications; missing and null remain distinct.</summary>
    public IReadOnlyList<Classification> Classifications
    {
        get => Read<IReadOnlyList<Classification>>("classifications");
        init => Write("classifications", value);
    }
    /// <summary>Wire field code; missing and null remain distinct.</summary>
    public string Code
    {
        get => Read<string>("code");
        init => Write("code", value);
    }
    /// <summary>Wire field definition; missing and null remain distinct.</summary>
    public Optional<string> Definition
    {
        get => ReadOptional<string>("definition");
        init => WriteOptional("definition", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field name; missing and null remain distinct.</summary>
    public string Name
    {
        get => Read<string>("name");
        init => Write("name", value);
    }
}

/// <summary>Schema-derived Traversal wire record. Exports and nested reads are detached.</summary>
public sealed class Traversal : WireRecord
{
    public Traversal() { }
    public Traversal(JsonObject data) : base(data) { }

    /// <summary>Wire field classification; missing and null remain distinct.</summary>
    public Optional<Guid> Classification
    {
        get => ReadOptional<Guid>("classification");
        init => WriteOptional("classification", value);
    }
    /// <summary>Wire field depth; missing and null remain distinct.</summary>
    public string Depth
    {
        get => Read<string>("depth");
        init => Write("depth", value);
    }
    /// <summary>Wire field direction; missing and null remain distinct.</summary>
    public Optional<string> Direction
    {
        get => ReadOptional<string>("direction");
        init => WriteOptional("direction", value);
    }
    /// <summary>Wire field kind; missing and null remain distinct.</summary>
    public string Kind
    {
        get => Read<string>("kind");
        init => Write("kind", value);
    }
}

/// <summary>Schema-derived Value wire record. Exports and nested reads are detached.</summary>
public sealed class Value : WireRecord
{
    public Value() { }
    public Value(JsonObject data) : base(data) { }

    /// <summary>Wire field content; missing and null remain distinct.</summary>
    public Optional<PropertyContent> Content
    {
        get => ReadOptional<PropertyContent>("content");
        init => WriteOptional("content", value);
    }
    /// <summary>Wire field description; missing and null remain distinct.</summary>
    public Optional<string> Description
    {
        get => ReadOptional<string>("description");
        init => WriteOptional("description", value);
    }
    /// <summary>Wire field flow; missing and null remain distinct.</summary>
    public Optional<Flow> Flow
    {
        get => ReadOptional<Flow>("flow");
        init => WriteOptional("flow", value);
    }
    /// <summary>Wire field id; missing and null remain distinct.</summary>
    public Guid Id
    {
        get => Read<Guid>("id");
        init => Write("id", value);
    }
    /// <summary>Wire field key; missing and null remain distinct.</summary>
    public string Key
    {
        get => Read<string>("key");
        init => Write("key", value);
    }
    /// <summary>Wire field kind; missing and null remain distinct.</summary>
    public string Kind
    {
        get => Read<string>("kind");
        init => Write("kind", value);
    }
    /// <summary>Wire field measure; missing and null remain distinct.</summary>
    public Optional<Guid> Measure
    {
        get => ReadOptional<Guid>("measure");
        init => WriteOptional("measure", value);
    }
    /// <summary>Wire field quantity; missing and null remain distinct.</summary>
    public Optional<Quantity> Quantity
    {
        get => ReadOptional<Quantity>("quantity");
        init => WriteOptional("quantity", value);
    }
}
