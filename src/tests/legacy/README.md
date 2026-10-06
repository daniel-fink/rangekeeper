# Windows-gated predecessor tests

These tests cover the held Graph, Measure and old Speckle API. The three live
tests in `test_api.py` are excluded from local acceptance and remain unverified.
The exclusion is not evidence that the Windows connector gate has passed.

Follow the [cleanup checklist](../../../docs/research/full-migration/turn4/RETIREMENT.md#cleanup-checklist-after-the-windows-gate-closes)
before removing this directory with the predecessor implementation. First retain
useful semantic assertions as canonical tests, then remove obsolete test exclusions
from current instructions. Keep the migration wire fixtures and boundary guards
outside this directory. Preserve historical commands and test results unchanged.

The [relocation record](../../../docs/LEGACY_ISOLATION.md) explains the split between
canonical tests and predecessor tests; the [move manifest](../../../docs/research/full-migration/legacy-isolation/moves.json)
records the whole-file moves.
