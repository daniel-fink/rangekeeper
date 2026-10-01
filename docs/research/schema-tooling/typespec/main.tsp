import "@typespec/json-schema";
using TypeSpec.JsonSchema;

@jsonSchema
namespace Probe;

model ValueDeclaration { id: string; kind: "ValueDeclaration"; unit: string; }
model EntityDeclaration { id: string; kind: "EntityDeclaration"; }
union Declaration { ValueDeclaration, EntityDeclaration }

model NumericLiteral { id: string; kind: "NumericLiteral"; value: numeric; unit: string; }
model BooleanLiteral { id: string; kind: "BooleanLiteral"; value: boolean; }
model Reference { id: string; kind: "Reference"; target: string; }
model LessEqual { id: string; kind: "LessEqual"; left: string; right: string; }
union Expression { NumericLiteral, BooleanLiteral, Reference, LessEqual }
model Constraint { predicate: string; }

@doc("A small document containing project declarations, symbolic expressions and asserted predicates.")
model Model {
  declarations: Declaration[];
  expressions: Expression[];
  constraints: Constraint[];
}

model TreeLiteral { kind: "literal"; value: numeric; }
model TreeAdd { kind: "add"; left: Tree; right: Tree; }
union Tree { TreeLiteral, TreeAdd }
