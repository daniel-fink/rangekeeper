# Measurement reduction coverage

`by_measure(measure, contributors=predicate, require_measurement=True)` selects contributors independently of measurement presence. The selected View must still be an arborescence; the predicate does not turn overlapping membership into a tree or deduplicate a multi-parent topology. Restrict the View explicitly to a defensible aggregation structure.

A corridor may be excluded from apartment NSA selection. An apartment selected by the rule but without NSA is missing. `result.coverage(root)` reports selected, measured and missing UUIDs, with complete/incomplete/empty status. Required missing data makes `result[root]` and root_value unavailable. `available_value(root)` reports reduction over present inputs; `known_subtotal(root)` is restricted to SUM. An empty selected population is unavailable, not zero; a measured zero remains valid.

Omitting these options preserves the previous reducer behaviour. Measure is unchanged and continues to specify units and its permitted aggregation operation. Selection is a project/query policy, not a property of Measure. Coverage refers to recorded selected contributors; a complete result does not certify the source contains all physical components. Parent measurements should not be selected together with their contributing children. Keep independently reported parent evidence separate and reconcile compatible scopes explicitly.

`Graph.entities_in(assembly, recursive=True)` deduplicates recursive members in graph order. `Graph.containing_assemblies(entity, recursive=True)` returns all recorded ancestors. Defaults remain direct membership; `Graph.view(assembly=...)` retains its existing direct scope.
