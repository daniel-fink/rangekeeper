# Security policy

## Supported versions

| Version | Branch | Status |
| --- | --- | --- |
| 1.x | `develop`, then `main` | Upcoming. Pre-releases (`1.0.0a1` and later) get no security fixes. Support starts with 1.0.0. |
| 0.8.x | `support/0.8` | Supported. Bug and security fixes only, until an announced end of life. |
| < 0.8 | none | Not supported. Upgrade to the latest 0.8.x release. |

Fixes for 0.8.x are released as new 0.8.x patch versions on PyPI. They add no
features and keep the 0.8 API.

## End of life for 0.8.x

The 0.8 line stays supported for some time after 1.0.0. Before support ends:

1. A GitHub issue and the changelog announce the end-of-life date. The date
   is at least six months after the announcement.
2. This table shows the date.
3. The last 0.8.x release notes repeat the date.

After that date, `support/0.8` gets no more fixes. Its releases stay on PyPI.

## Report a vulnerability

Do not report a vulnerability in a public issue, pull request or discussion.

Use GitHub's private vulnerability reporting: on the repository's
[Security tab](https://github.com/daniel-fink/rangekeeper/security), select
**Report a vulnerability**. Include:

- the affected versions;
- the steps or a minimal example that shows the problem;
- the effect that you expect.

The maintainer acknowledges a report within 14 days. After the fix is released,
the maintainer publishes a GitHub security advisory and credits the reporter,
unless the reporter asks to stay anonymous.
