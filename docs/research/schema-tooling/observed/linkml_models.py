from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.11.0"
version = "None"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )





class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'probe',
     'default_range': 'string',
     'id': 'https://example.org/rk-schema-probe',
     'imports': ['linkml:types'],
     'name': 'rk_schema_probe',
     'prefixes': {'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'probe': {'prefix_prefix': 'probe',
                            'prefix_reference': 'https://example.org/rk-schema-probe/'}},
     'source_file': '/private/tmp/rk-schema-review.2FDWet/linkml.yaml'} )


class Declaration(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True, 'from_schema': 'https://example.org/rk-schema-probe'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Declaration', 'Expression']} })
    kind: Literal["Declaration"] = Field(default="Declaration", json_schema_extra = { "linkml_meta": {'designates_type': True, 'domain_of': ['Declaration', 'Expression']} })


class ValueDeclaration(Declaration):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/rk-schema-probe',
         'slot_usage': {'kind': {'equals_string': 'ValueDeclaration', 'name': 'kind'}}})

    unit: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['ValueDeclaration', 'NumericLiteral']} })
    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Declaration', 'Expression']} })
    kind: Literal["ValueDeclaration"] = Field(default="ValueDeclaration", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['Declaration', 'Expression'],
         'equals_string': 'ValueDeclaration'} })


class EntityDeclaration(Declaration):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/rk-schema-probe',
         'slot_usage': {'kind': {'equals_string': 'EntityDeclaration', 'name': 'kind'}}})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Declaration', 'Expression']} })
    kind: Literal["EntityDeclaration"] = Field(default="EntityDeclaration", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['Declaration', 'Expression'],
         'equals_string': 'EntityDeclaration'} })


class Expression(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True, 'from_schema': 'https://example.org/rk-schema-probe'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Declaration', 'Expression']} })
    kind: Literal["Expression"] = Field(default="Expression", json_schema_extra = { "linkml_meta": {'designates_type': True, 'domain_of': ['Declaration', 'Expression']} })


class NumericLiteral(Expression):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/rk-schema-probe',
         'slot_usage': {'kind': {'equals_string': 'NumericLiteral', 'name': 'kind'}}})

    value: float = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['NumericLiteral', 'BooleanLiteral']} })
    unit: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['ValueDeclaration', 'NumericLiteral']} })
    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Declaration', 'Expression']} })
    kind: Literal["NumericLiteral"] = Field(default="NumericLiteral", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['Declaration', 'Expression'],
         'equals_string': 'NumericLiteral'} })


class BooleanLiteral(Expression):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/rk-schema-probe',
         'slot_usage': {'kind': {'equals_string': 'BooleanLiteral', 'name': 'kind'}}})

    value: bool = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['NumericLiteral', 'BooleanLiteral']} })
    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Declaration', 'Expression']} })
    kind: Literal["BooleanLiteral"] = Field(default="BooleanLiteral", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['Declaration', 'Expression'],
         'equals_string': 'BooleanLiteral'} })


class Reference(Expression):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/rk-schema-probe',
         'slot_usage': {'kind': {'equals_string': 'Reference', 'name': 'kind'}}})

    target: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Reference']} })
    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Declaration', 'Expression']} })
    kind: Literal["Reference"] = Field(default="Reference", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['Declaration', 'Expression'],
         'equals_string': 'Reference'} })


class LessEqual(Expression):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/rk-schema-probe',
         'slot_usage': {'kind': {'equals_string': 'LessEqual', 'name': 'kind'}}})

    left: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['LessEqual']} })
    right: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['LessEqual']} })
    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Declaration', 'Expression']} })
    kind: Literal["LessEqual"] = Field(default="LessEqual", json_schema_extra = { "linkml_meta": {'designates_type': True,
         'domain_of': ['Declaration', 'Expression'],
         'equals_string': 'LessEqual'} })


class Constraint(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/rk-schema-probe'})

    predicate: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Constraint']} })


class Model(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/rk-schema-probe', 'tree_root': True})

    declarations: list[Union[Declaration,ValueDeclaration,EntityDeclaration]] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Model']} })
    expressions: list[Union[Expression,NumericLiteral,BooleanLiteral,Reference,LessEqual]] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Model']} })
    constraints: list[Constraint] = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Model']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Declaration.model_rebuild()
ValueDeclaration.model_rebuild()
EntityDeclaration.model_rebuild()
Expression.model_rebuild()
NumericLiteral.model_rebuild()
BooleanLiteral.model_rebuild()
Reference.model_rebuild()
LessEqual.model_rebuild()
Constraint.model_rebuild()
Model.model_rebuild()
