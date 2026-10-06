# Turn 4: permitted legacy retirement

The later [legacy isolation follow-up](../legacy-isolation/README.md) moves the held
group into explicit namespaces. The raw logs, wheel hash and `final-state.json`
here describe the preceding retirement checkpoint and must not be presented as
fresh verification of later files. The retirement register has current locations.

The permitted numerical and presentation retirement is implemented and locally
accepted. The Windows connector predecessor group remains present. Full retirement
is therefore **not complete**.

Start with [the completion report](../../../FULL_MIGRATION_TURN4.md),
[baseline and acceptance](BASELINE.md), [commands](COMMANDS.md),
[behaviour mapping](BEHAVIOUR.md), and [remaining removal gates](RETIREMENT.md).

Machine-readable evidence:

- `baseline.json`: repository state, environment, 404 verification-input hashes
  and 91 protected-file hashes after the paired Turn 3 checkpoint.
- `removed-files.json`: exact removed files and their checkpoint hashes.
- `ledger.json`: current dispositions for all 671 frozen symbols and 95 consumers;
  original source evidence is marked historical.
- `imports.json`: current AST import/attribute references. The audit also rejects
  old imports in the registered active Projects Python and notebook consumers.
- `full-suite.xml` and `test-inventory-change.json`: actual results and count changes.
- `commands.jsonl`: exact commands, working directories, selected environment,
  exit status and duration. Failed setup attempts remain beside their successful retries.
- `final-state.json`: final preservation, installed-wheel equivalence and repository checks.

Private source workbooks, Models, historical design payloads and project notebook
outputs remain outside this evidence directory. No credentials are retained.
Historical research programs may still import the old API: they require their
recorded historical checkout and are not current consumers.
