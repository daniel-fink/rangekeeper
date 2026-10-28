"""Static import closures cover the modules that each fingerprinted computation runs."""

import importlib.util
import sys
from pathlib import Path

import pytest

import rangekeeper
from rangekeeper.shared.fingerprints import import_closure

PACKAGE = Path(rangekeeper.__file__).resolve().parent


def write(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def test_closure_follows_static_lazy_and_relative_imports(tmp_path):
    write(
        tmp_path,
        {
            "__init__.py": "from .core import Model\n",
            "core.py": "from . import helpers\n\nclass Model:\n    pass\n",
            "helpers.py": "def helper():\n    from pkg.deep.leaf import value\n",
            "entry.py": "from pkg import Model\nfrom pkg.lazy import Lazy, Typed\n",
            "deep/__init__.py": "",
            "deep/leaf.py": "value = 1\n",
            "lazy/__init__.py": (
                "from importlib import import_module\n"
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                "    from .typed import Typed as Typed\n"
                "def __getattr__(name):\n"
                "    return getattr(import_module('.loaded', __name__), name)\n"
            ),
            "lazy/loaded.py": "Lazy = 1\n",
            "lazy/typed.py": "Typed = 1\n",
            "unused.py": "raise RuntimeError\n",
        },
    )
    assert import_closure(["entry.py"], package=tmp_path, root="pkg") == (
        "core.py",
        "deep/leaf.py",
        "entry.py",
        "helpers.py",
        "lazy/__init__.py",
        "lazy/loaded.py",
        "lazy/typed.py",
    )


def test_closure_names_real_files_and_fails_on_missing_modules(tmp_path):
    # A re-exported class name never resolves to a same-named file on a
    # case-insensitive file system.
    closure = import_closure(["market/generation.py"], package=PACKAGE)
    names = {
        path: set(p.name for p in (PACKAGE / path).parent.iterdir()) for path in closure
    }
    assert all(Path(path).name in names[path] for path in closure)
    write(tmp_path, {"entry.py": "import pkg.missing\n"})
    with pytest.raises(ModuleNotFoundError, match="pkg.missing"):
        import_closure(["entry.py"], package=tmp_path, root="pkg")
    with pytest.raises(FileNotFoundError):
        import_closure(["absent.py"], package=tmp_path, root="pkg")


class Trace:
    """Record each package function that runs inside the wrapped calls."""

    def __init__(self):
        self.ran: set[tuple[str, str]] = set()
        self.files: dict[str, str | None] = {}

    def file(self, filename):
        if filename not in self.files:
            path = Path(filename).resolve()
            self.files[filename] = (
                path.relative_to(PACKAGE).as_posix()
                if path.is_relative_to(PACKAGE)
                else None
            )
        return self.files[filename]

    def wrap(self, function):
        def traced(*args, **kwargs):
            def profile(frame, event, arg):
                if event == "call":
                    name = self.file(frame.f_code.co_filename)
                    if name is not None:
                        self.ran.add((name, frame.f_code.co_name))

            previous = sys.getprofile()
            sys.setprofile(profile)
            try:
                return function(*args, **kwargs)
            finally:
                sys.setprofile(previous)

        return traced

    def outside(self, closure, *, injected=frozenset()):
        return {
            item for item in self.ran if item[0] not in closure and item not in injected
        }


@pytest.mark.skipif(
    any(importlib.util.find_spec(name) is None for name in ("pyomo", "highspy")),
    reason="requires the optional execution extra",
)
def test_execution_closures_cover_every_module_that_runs(monkeypatch):
    from rangekeeper.execution import attempt, implementation
    from tests.execution.test_execution import execute, setup, spec

    traces = {"compiler": Trace(), "evaluator": Trace()}
    for module, name, role in (
        (attempt.preparation, "prepare", "compiler"),
        (attempt.compiler, "compile", "compiler"),
        (attempt.acceptance, "check", "evaluator"),
    ):
        monkeypatch.setattr(module, name, traces[role].wrap(getattr(module, name)))
    store, _ = setup()
    execute(store, spec())
    # The caller injects its deadline check and record resolver.
    injected = {
        ("execution/attempt.py", "checkpoint"),
        ("execution/planning.py", "load_model"),
    }
    for role, trace in traces.items():
        assert trace.ran, role
        closure = implementation.sources(role)
        assert trace.outside(closure, injected=injected) == set(), role


def test_scenario_closure_covers_every_module_that_runs():
    from rangekeeper.market import generation as market
    from rangekeeper.market import implementation
    from tests.market.test_contracts import base, plan

    trace = Trace()
    trace.wrap(market.generate)(base(), plan(), scenario_keys=["traced"])
    assert trace.ran
    assert trace.outside(implementation.source_paths()) == set()
