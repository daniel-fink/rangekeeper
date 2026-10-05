# Bounded workflow examples

These synthetic examples have no project data. `accommodation` models rooms and
levels; `equipment` models assets and zones using the same operations and executor.
Both include zero, missing readings, an ambiguous label, conflicting observations,
source notes, physical blanks and an incomplete total against a reported aggregate.

From an environment with `rangekeeper[workflow]` installed:

```sh
python create_inputs.py /tmp/equipment-inputs --domain equipment
python -m rangekeeper.workflow \
  --spec equipment/spec --inputs /tmp/equipment-inputs --output /tmp/equipment-review
```

Replace `equipment` with `accommodation` for the other domain. Original Claims are
retained, configuration participates in derivation lineage, and graph memberships
come from explicit relationships. The whole path includes canonical Model JSON and shared
review export. Both specifications use version 2, explicit Value keys and property
Values with source Claim/Fact evidence. The contract tests also exercise concatenation, bad source layouts,
wrong members with equal counts, shared memberships, missing formula caches and
business identity stability.

The equipment specification demonstrates named `equipment_sizes` numeric policies
and `equipment_readings` measurement bindings. The accommodation example retains
the inline form. Both resolve to ordinary RK requests; no external generator or
project runtime is needed. The shared-declaration tests additionally exercise
multiple consumers, explicit total contexts, isolation between uses and strict
validation of unused definitions.
