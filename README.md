<img src="https://github.com/daniel-fink/rangekeeper/blob/v0.2.0/walkthrough/resources/rangekeeper.jpg?raw=true" width="300">

Current consumer API: [Model tables, adapters, and source workflows](docs/CONSUMER_MIGRATION.md) (Step 6C/6D).
Use `rangekeeper.adapters`, `rangekeeper.workflow`, and `WorkflowResult.model`.

# Rangekeeper
Rangekeeper is an open-source library for financial modelling in real estate 
asset & development planning, decision-making, cashflow forecasting, and 
scenario analysis.

Rangekeeper enables real estate valuation at all stages and resolutions of 
description — from early-stage ‘back-of-the-envelope’ models to detailed 
commercial assessments, and can be completely synchronised with 3D design, 
engineering, and logistics modelling.

It decomposes elements of the Discounted Cash Flow (DCF) Proforma modelling 
approach into recomposable code functions that can be wired together to form a 
full model. More elaborate and worked-through examples of these classes and 
functions can be found in the [walkthrough documentation](https://daniel-fink.github.io/rangekeeper/).

Development of the library follows the rigorous methodology established by 
Profs Geltner and de Neufville in their book [Flexibility and Real Estate Valuation under Uncertainty: A Practical Guide for Developers](https://doi.org/10.1002/9781119106470).


## Structure

This repository is comprised of three separate, but inter-dependent projects:
1. Rangekeeper library source (in Python) 
2. Walkthrough documentation (a Jupyter Book)
3. McNeel Rhinoceros 3D Grasshopper components (to assist the creation of Rangekeeper-compliant objects from 3D models, in C#)

Each project has its own readme to assist setup and dependency resolution.

## Design notes

- [Implemented domain core and revision storage](docs/RUN_AND_STORAGE.md):
  public Model/Specification/Run roots, strict codecs and immutable stores.
  [Scalar execution](docs/SCALAR_EXECUTION.md) now solves declared affine equations
  with Pyomo/HiGHS and publishes independently accepted outputs. These branch changes
  have not been released. [Model-backed views and reductions](docs/GRAPH_MODEL.md)
  now implement Step 6A/6B; tables and presentation adapters are next.

- [Documentation index and current work plan](docs/README.md):
  accepted decisions, current state, next steps, and historical-document scope.
- [Library architecture and migration plan](docs/LIBRARY_ARCHITECTURE.md):
  agreed schema, domain-model, mathematical-library, compiler, and execution
  boundaries; target repository layout and staged route to the scalar checkpoint.
- [Graph LinkML schema drafts](schema/README.md):
  Definitions, Entities, Relationships, Assemblies, Characteristics, and Provenance, with a
  shared structural example and conformance checks.
- [Schema tooling evaluation](docs/SCHEMA_TOOLING_EVALUATION.md):
  historical comparisons and executed probes; the current decision retains LinkML.
- [Model, Specification, and Run object model](docs/MODEL_SPECIFICATION_RUN.md):
  current object-model decisions, proposed child schemas, requirements, and staged
  acceptance examples.
- [Project definitions, execution, and policy optimization](docs/PROJECT_DEFINITION_AND_POLICY_EXAMPLE.md):
  the two-pad redevelopment example, illustrative assumptions, and references for
  a subsequent executable test.
