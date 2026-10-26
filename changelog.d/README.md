# Changelog fragments

Each pull request adds at least one fragment to this folder. CI checks this. At
release time, towncrier collects the fragments into
[`CHANGELOG.md`](../CHANGELOG.md) and deletes them.

Name a fragment `<issue>.<type>.md`, for example `173.feature.md`. If no issue
applies, use `+<short-name>.<type>.md`. Write one or two sentences for users of
the package: say what changed and what they must do.

| Type | Use for |
| --- | --- |
| `breaking` | A change that can break existing code, data or installations |
| `deprecation` | A name or behaviour that a later release removes |
| `removal` | A removed name, module or behaviour |
| `feature` | New behaviour |
| `bugfix` | A fixed defect |
| `packaging` | Dependencies, metadata, distributions and supported Python versions |
| `doc` | A documentation change that users must know about |
| `misc` | Engineering changes: CI, tooling, tests and repository content |

Create a fragment with:

```sh
uv run --locked towncrier create 173.feature.md --content "Describe the change."
```

A pull request with no change for users, such as a typo fix, can skip the
fragment with the `no-changelog` label.
