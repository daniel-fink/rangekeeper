# Investigation Bundle candidate, 14 October 2026

> Edited extract, 17 October 2026: external application references were removed.
> Retained RK results keep their original scope; this is not an unchanged capture.

The user agreed to deliver a Model with sufficient investigation context to understand
it and perform further investigations. The [current Bundle reference](../../reference/bundle.md)
owns `rangekeeper.bundle/2-proposal` in RK 0.10.0.dev2. Canonical record schemas and
the Parquet mapping remain unchanged. This is a local, uncommitted candidate on
develop base ffda9b8; no stable release or adoption by the primary consumer is approved.

The [check record](checks.json) reports 870 RK tests covered. In the
[full suite](rk-full.log), 869 passed and one local-display test was blocked by the
sandbox's loopback bind restriction. That exact test [passed on rerun](rk-loopback-recheck.log)
with the required permission. No product-code workaround was used.

Twelve new investigation tests cover actual execution and further investigation,
composed Specifications, unexecuted definitions, successful/failed batch children,
copy conflict preflight, required references, identity, corruption, budgets,
explicit history selection and repacking. The primary consumer's four added cases cover the
fresh-process handover, Geometry shared across Models (including a nonspatial main
Model), exact query scope and conflicting supporting identities. The primary consumer passed 470 tests.

The primary consumer pins the new wheel and verifies all 145 packaged RK files against the source
snapshot. Its installed-wheel handover repeated successfully with no originating
workspace and no source-tree imports for either product package. See
the primary consumer's review (external link omitted)
for the working review packet; this link is navigation, not a published checkpoint.

RK remains in its single checkout on develop. Existing walkthrough/data and
repository-state changes are preserved. The old dev1 wheel and 1-proposal evidence
remain in the primary consumer. Expanded format review precedes T2 adoption. Wider provider, policy,
scale, transport/UI and real-host conformance remain within their existing gates.
