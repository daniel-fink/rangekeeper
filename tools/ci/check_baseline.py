"""Check that a change does not add to the structure baseline or the typing ratchet.

Usage: python tools/ci/check_baseline.py [--base REF]

The structure baseline is the set of ruff per-file ignores of the structure and
annotation rules for `src/rangekeeper` (#400). The typing ratchet is the set of
modules for which a mypy override turns off a strict check. The script reads
`pyproject.toml` at the merge base of REF (default `origin/develop`) and HEAD,
and in the working tree. It fails when the working tree:

- ignores a structure or annotation rule for a file that the base does not;
- ignores such a rule for all files, stops selecting it, or raises its limit;
- relaxes strict mypy for a module that the base does not relax.

A file renamed since the base keeps its codes. A module that a base pattern
such as `rangekeeper.flow.*` covers can stay relaxed. When the base has no
guardrails, the script checks nothing.
"""

import argparse
import subprocess
import sys
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

# The ruff rules of the structure baseline. A code in a per-file ignore matches
# a rule when one is a prefix of the other, as in "PLR09" or "ANN".
GUARDED = (
    "C901",
    "PLR0911",
    "PLR0912",
    "PLR0913",
    "PLR0915",
    "PLR0917",
    "PLC0415",
    "ANN001",
    "ANN002",
    "ANN003",
    "ANN201",
    "ANN202",
    "ANN204",
    "ANN205",
    "ANN206",
)

# The ruff limits of the guarded rules: (section, option).
LIMITS = (
    ("mccabe", "max-complexity"),
    ("pylint", "max-args"),
    ("pylint", "max-positional-args"),
    ("pylint", "max-branches"),
    ("pylint", "max-returns"),
    ("pylint", "max-statements"),
)

# mypy options that strict mode sets, with the value that relaxes each one.
RELAXED = {
    "disallow_any_generics": False,
    "disallow_subclassing_any": False,
    "disallow_untyped_calls": False,
    "disallow_untyped_defs": False,
    "disallow_incomplete_defs": False,
    "check_untyped_defs": False,
    "disallow_untyped_decorators": False,
    "warn_return_any": False,
    "implicit_reexport": True,
    "strict_equality": False,
    "warn_unused_ignores": False,
    "extra_checks": False,
    "ignore_errors": True,
}

Pairs = set[tuple[str, str]]


def git(*arguments: str) -> str:
    """Run git in the repository root and return its output."""
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def guarded(code: str) -> bool:
    """Return whether an ignored code turns off a rule of the baseline."""
    return code == "ALL" or any(
        rule.startswith(code) or code.startswith(rule) for rule in GUARDED
    )


def in_scope(pattern: str) -> bool:
    """Return whether a per-file pattern can match a file in `src/rangekeeper`."""
    if pattern.startswith("!"):
        return False
    first = pattern.split("/", 1)[0]
    return "/" not in pattern or first == "src" or any(c in first for c in "*?[")


def lint(config: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the `[tool.ruff.lint]` table."""
    return config.get("tool", {}).get("ruff", {}).get("lint", {})


def ignores(config: Mapping[str, Any]) -> Pairs:
    """Return the (pattern, code) pairs that turn off a guarded rule.

    The pattern "*" stands for all files: a global ignore, or a guarded rule
    that `select` does not contain.
    """
    table = lint(config)
    pairs = {
        (pattern, code)
        for key in ("per-file-ignores", "extend-per-file-ignores")
        for pattern, codes in table.get(key, {}).items()
        if in_scope(pattern)
        for code in codes
        if guarded(code)
    }
    pairs |= {
        ("*", code)
        for key in ("ignore", "extend-ignore")
        for code in table.get(key, ())
        if guarded(code)
    }
    selected = [*table.get("select", ()), *table.get("extend-select", ())]
    pairs |= {
        ("*", rule)
        for rule in GUARDED
        if not any(rule.startswith(code) or code == "ALL" for code in selected)
    }
    return pairs


def renames(base: str) -> dict[str, str]:
    """Return the old path of each file renamed between the base and the tree."""
    moved = {}
    for line in git("diff", "--name-status", "-M", base).splitlines():
        status, *paths = line.split("\t")
        if status.startswith("R"):
            old, new = paths
            moved[new] = old
    return moved


def check_ruff(
    base: Mapping[str, Any], head: Mapping[str, Any], moved: Mapping[str, str]
) -> list[str]:
    """Return a message for each guarded rule that the tree ignores in addition."""
    before = ignores(base)
    if all(("*", rule) in before for rule in GUARDED):
        return []
    added = [
        (pattern, code)
        for pattern, code in sorted(ignores(head))
        if (moved.get(pattern, pattern), code) not in before
    ]
    messages = [
        f"ruff: {code} is ignored for all files"
        if pattern == "*"
        else f"ruff: new per-file ignore {code} for {pattern}"
        for pattern, code in added
    ]
    for section, option in LIMITS:
        old = lint(base).get(section, {}).get(option)
        new = lint(head).get(section, {}).get(option)
        if old is not None and (new is None or new > old):
            messages.append(f"ruff: {section}.{option} is {new or 'unset'}, not {old}")
    return messages


def relaxed(config: Mapping[str, Any]) -> set[str]:
    """Return the module patterns for which mypy is less than strict.

    The pattern "*" stands for all modules: the global section is not strict.
    """
    mypy = config.get("tool", {}).get("mypy", {})
    patterns = set()
    if not mypy.get("strict", False) or relaxes(mypy):
        patterns.add("*")
    for override in mypy.get("overrides", ()):
        modules = override.get("module", ())
        modules = [modules] if isinstance(modules, str) else modules
        if relaxes(override):
            patterns |= {name for name in modules if name.startswith("rangekeeper")}
    return patterns


def relaxes(options: Mapping[str, Any]) -> bool:
    """Return whether a mypy section turns off a strict check."""
    return bool(options.get("disable_error_code")) or any(
        name in options and options[name] == value for name, value in RELAXED.items()
    )


def covered(pattern: str, patterns: Iterable[str]) -> bool:
    """Return whether one of the patterns matches every module that `pattern` does."""
    for other in patterns:
        if other in (pattern, "*"):
            return True
        if other.endswith(".*") and (
            pattern == other[:-2] or pattern.startswith(other[:-1])
        ):
            return True
    return False


def check_mypy(base: Mapping[str, Any], head: Mapping[str, Any]) -> list[str]:
    """Return a message for each module that the tree relaxes in addition."""
    before = relaxed(base)
    if "*" in before:
        return []
    return [
        "mypy: all modules are less than strict"
        if pattern == "*"
        else f"mypy: {pattern} is less than strict"
        for pattern in sorted(relaxed(head))
        if not covered(pattern, before)
    ]


def main() -> None:
    """Compare the working tree with the merge base and report each addition."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/develop")
    base_ref = git("merge-base", parser.parse_args().base, "HEAD").strip()
    base = tomllib.loads(git("show", f"{base_ref}:pyproject.toml"))
    head = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    messages = check_ruff(base, head, renames(base_ref)) + check_mypy(base, head)
    for message in messages:
        print(message)
    if messages:
        print(
            "\nThe structure baseline and the packages that are not yet strict only"
            " shrink. Fix the finding; if one line must keep a ruff finding, put"
            " `# noqa: <code>` on it with the reason. See"
            " docs/contributing/README.md#structure-baseline."
        )
        sys.exit(1)
    print(f"No additions to the baseline or the mypy override since {base_ref[:12]}")


if __name__ == "__main__":
    main()
