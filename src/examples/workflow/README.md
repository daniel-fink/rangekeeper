# Bounded workflow examples

These synthetic examples have no project data. `accommodation` models rooms and
levels; `equipment` models assets and zones using the same operations and executor.
Both include zero, missing readings, an ambiguous label, conflicting observations,
source notes, physical blanks and an incomplete total against a reported aggregate.

From an environment with `rangekeeper[workflow]` installed:

```sh
python create_inputs.py /tmp/equipment-inputs --domain equipment
python -m rangekeeper.graph.workflow \
  --spec equipment/spec --inputs /tmp/equipment-inputs --output /tmp/equipment-review
```

Replace `equipment` with `accommodation` for the other domain. Original Claims are
retained, configuration participates in derivation lineage, and graph memberships
come from explicit relationships. The whole path includes graph JSON and shared
review export. The contract tests also exercise concatenation, bad source layouts,
wrong members with equal counts, shared memberships, missing formula caches and
business identity stability.
