package probe

import "list"

#ValueDeclaration: {id!: string, kind!: "ValueDeclaration", unit!: string}
#EntityDeclaration: {id!: string, kind!: "EntityDeclaration"}
#Declaration: #ValueDeclaration | #EntityDeclaration
#NumericLiteral: {id!: string, kind!: "NumericLiteral", value!: number, unit!: string}
#BooleanLiteral: {id!: string, kind!: "BooleanLiteral", value!: bool}
#Reference: {id!: string, kind!: "Reference", target!: string}
#LessEqual: {id!: string, kind!: "LessEqual", left!: string, right!: string}
#Expression: #NumericLiteral | #BooleanLiteral | #Reference | #LessEqual
#Constraint: {predicate!: string}
#Model: {
    declarations!: [...#Declaration]
    expressions!: [...#Expression]
    constraints!: [...#Constraint]
}

// Extra rules over the whole graph, written deliberately; not automatic semantics.
#SemanticModel: #Model & {
    declarations!: _
    expressions!: _
    constraints!: _
    _declsUnique: list.UniqueItems([for d in declarations {d.id}]) & true
    _exprsUnique: list.UniqueItems([for e in expressions {e.id}]) & true
    for e in expressions if e.kind == "Reference" {
        _referenceOK: list.Contains([for d in declarations if d.kind == "ValueDeclaration" {d.id}], e.target) & true
    }
    for c in constraints {
        _predicateOK: list.Contains([for e in expressions if e.kind == "LessEqual" || e.kind == "BooleanLiteral" {e.id}], c.predicate) & true
    }
    let numericUnits = {
        for operand in expressions if operand.kind == "NumericLiteral" {
            "\(operand.id)": operand.unit
        }
        for operand in expressions if operand.kind == "Reference" {
            for d in declarations if d.id == operand.target if d.kind == "ValueDeclaration" {
                "\(operand.id)": d.unit
            }
        }
    }
    for e in expressions if e.kind == "LessEqual" {
        _unitsMatch: (numericUnits[e.left] == numericUnits[e.right]) & true
    }
}

// Recursive embedded expressions are a separate shape test.
#Tree: {kind!: "literal", value!: number} | {
    kind!: "add"
    left!: #Tree
    right!: #Tree
}
