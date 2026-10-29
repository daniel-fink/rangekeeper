"""One registry pattern for every extension point (ADR-013).

An extension point is a Protocol and a ``Registry``. The package that owns the
point makes the registry and registers its built-in implementations. Other code
calls ``register(name=, implementation=)``. An installed distribution can also
declare implementations in the entry point group ``rangekeeper.<point>``; the
registry loads an entry point only when a lookup asks for its name.

Explicit registrations take precedence over entry points, so an installed
distribution cannot replace a built-in. Each registration has a fingerprint,
and evidence records it with the registered name.
"""

import difflib
import importlib.util
import inspect
import platform
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from threading import RLock
from typing import Any

from rangekeeper.shared.errors import (
    ContractError,
    ExtensionConflictError,
    UnknownExtensionError,
)
from rangekeeper.shared.fingerprints import (
    import_closure,
    manifest_digest,
    semantic_digest,
)

FORMAT = "extension/v1"
_NAME = re.compile(r"[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*")


@dataclass(frozen=True, slots=True)
class Registration[T]:
    """One named implementation at one extension point, with its fingerprint.

    The fingerprint is calculated on first use, so registering a built-in at
    import time reads no source.
    """

    point: str
    name: str
    implementation: T
    _fingerprint: str | Callable[[], str] = field(repr=False, compare=False)
    registered: bool = True

    @property
    def fingerprint(self) -> str:
        """Return the fingerprint that evidence records for this implementation."""
        if not isinstance(self._fingerprint, str):
            object.__setattr__(self, "_fingerprint", self._fingerprint())
        assert isinstance(self._fingerprint, str)
        return self._fingerprint

    @property
    def qualified_name(self) -> str:
        """Return the name that evidence records.

        It is ``rangekeeper.<point>:<name>`` for a registered implementation, and
        ``<module>:<qualified name>`` for an unregistered one.
        """
        return f"rangekeeper.{self.point}:{self.name}" if self.registered else self.name


class Registry[T]:
    """Named implementations of one Protocol, with optional entry points.

    ``protocol`` is the type that every implementation must be an instance of;
    a Protocol must be ``runtime_checkable``. ``fingerprint`` returns the
    fingerprint of an implementation whose state, not only its code, defines
    its behaviour. Without it, the fingerprint hashes the source of the modules
    that the implementation's module imports.
    """

    def __init__(
        self,
        point: str,
        protocol: type,
        *,
        fingerprint: Callable[[Any], str] | None = None,
    ) -> None:
        if not isinstance(point, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", point):
            raise ContractError(
                f"invalid extension point name {point!r}", values={"point": point}
            )
        if getattr(protocol, "_is_protocol", False) and not getattr(
            protocol, "_is_runtime_protocol", False
        ):
            raise TypeError(f"{protocol.__name__} must be runtime_checkable")
        self.point, self.protocol = point, protocol
        self._fingerprint = fingerprint
        self._registered: dict[str, Registration[T]] = {}
        self._declared: dict[str, tuple[metadata.EntryPoint, ...]] | None = None
        self._lock = RLock()

    def __repr__(self) -> str:
        return f"Registry(point={self.point!r}, names={list(self.names())!r})"

    @property
    def group(self) -> str:
        """The entry point group that installed distributions declare names in."""
        return f"rangekeeper.{self.point}"

    def register(
        self,
        *,
        name: str,
        implementation: T,
        fingerprint: str | None = None,
        modules: Iterable[str] = (),
        replace: bool = False,
    ) -> Registration[T]:
        """Register one implementation under a name, and return its registration.

        ``fingerprint`` replaces the calculated fingerprint. ``modules`` names more
        modules whose source the calculated fingerprint includes, for example a
        module that runs in a worker process and that no import reaches.

        Registering the same object again under the same name changes nothing.
        A different implementation under a used name raises
        ``ExtensionConflictError`` unless ``replace`` is true.
        """
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ContractError(
                f"invalid {self.point} name {name!r}: use lowercase letters and "
                "digits, separated by '-', '_' or '.'",
                values={"point": self.point, "name": name},
            )
        self._require(implementation)
        with self._lock:
            existing = self._registered.get(name)
            if existing is not None and not replace:
                if existing.implementation is implementation and (
                    fingerprint is None or fingerprint == existing.fingerprint
                ):
                    return existing
                raise ExtensionConflictError(
                    f"{self.point} name {name!r} is already registered; "
                    "pass replace=True to replace it"
                )
            registration = Registration(
                self.point,
                name,
                implementation,
                fingerprint
                or (lambda: self._fingerprint_of(implementation, tuple(modules))),
            )
            self._registered[name] = registration
            return registration

    def names(self) -> tuple[str, ...]:
        """Return the registered and declared names; entry points do not load."""
        with self._lock:
            return tuple(sorted({*self._registered, *self._entry_points()}))

    def __contains__(self, name: object) -> bool:
        return name in self.names()

    def get(self, name: str) -> T:
        """Return the implementation registered or declared under a name."""
        return self.registration(name).implementation

    def registration(self, name: str) -> Registration[T]:
        """Return the registration of a name, loading its entry point if necessary."""
        with self._lock:
            if name in self._registered:
                return self._registered[name]
            declared = self._entry_points().get(name, ())
            if not declared:
                names = self.names()
                close = tuple(difflib.get_close_matches(str(name), names, n=3))
                hint = f"; did you mean {close[0]!r}?" if close else ""
                raise UnknownExtensionError(
                    f"no {self.point} implementation named {name!r}; "
                    f"known: {', '.join(names) or 'none'}{hint}",
                    suggestions=close,
                )
            if len(declared) > 1:
                sources = ", ".join(sorted(_distribution(item) for item in declared))
                raise ExtensionConflictError(
                    f"{self.point} name {name!r} is declared by several "
                    f"distributions: {sources}; register one explicitly"
                )
            entry = declared[0]
            try:
                implementation = entry.load()
            except Exception as error:
                raise ImportError(
                    f"entry point {name!r} in {self.group} from "
                    f"{_distribution(entry)} failed to load: {error}"
                ) from error
            return self.register(name=name, implementation=implementation)

    def describe(self, implementation: T) -> Registration[T]:
        """Return the registration that evidence records for an implementation.

        A registered implementation keeps its name. An unregistered one is named
        by its module and qualified name, with a fingerprint of its source.
        """
        with self._lock:
            registrations = tuple(self._registered.values())
        for registration in registrations:
            if registration.implementation is implementation:
                return registration
        for registration in registrations:
            if _equal(registration.implementation, implementation):
                return registration
        self._require(implementation)
        return Registration(
            self.point,
            _object_name(implementation),
            implementation,
            lambda: self._fingerprint_of(implementation),
            registered=False,
        )

    def _require(self, implementation: object) -> None:
        if not isinstance(implementation, self.protocol):
            raise TypeError(
                f"{self.point} implementations must be {self.protocol.__name__}, "
                f"not {type(implementation).__name__}"
            )

    def _fingerprint_of(
        self,
        implementation: object,
        modules: tuple[str, ...] = (),
    ) -> str:
        if self._fingerprint is not None:
            return self._fingerprint(implementation)
        return fingerprint(implementation, modules=modules)

    def _entry_points(self) -> dict[str, tuple[metadata.EntryPoint, ...]]:
        if self._declared is None:
            declared: dict[str, list[metadata.EntryPoint]] = {}
            for entry in metadata.entry_points(group=self.group):
                declared.setdefault(entry.name, []).append(entry)
            self._declared = {name: tuple(items) for name, items in declared.items()}
        return self._declared


def _equal(left: object, right: object) -> bool:
    try:
        return bool(left == right)
    except Exception:  # An implementation's __eq__ is outside this contract.
        return False


def _distribution(entry: metadata.EntryPoint) -> str:
    dist = entry.dist
    return "an unknown distribution" if dist is None else f"{dist.name} {dist.version}"


def _definition(implementation: object) -> object:
    """Return the class or function whose module defines an implementation."""
    if inspect.isclass(implementation) or inspect.isroutine(implementation):
        return implementation
    return type(implementation)


def _object_name(implementation: object) -> str:
    definition = _definition(implementation)
    return f"{definition.__module__}:{getattr(definition, '__qualname__', '?')}"


def fingerprint(implementation: object, *, modules: Iterable[str] = ()) -> str:
    """Hash the source of the modules that define and support an implementation.

    The sources are the static import closure of the implementation's module and
    of ``modules``, inside each top-level package. An implementation defined in a
    script or a notebook contributes its own source. A module without readable
    source, such as a compiled extension, contributes the version of the
    distribution that provides it. The manifest also names the implementation
    and the Python version.
    """
    definition = _definition(implementation)
    sources: dict[str, str] = {}
    versions: dict[str, str | None] = {}
    entries: dict[str, tuple[Path, set[str]]] = {}
    for name in (definition.__module__, *modules):
        root = name.split(".")[0]
        origin = _origin(name)
        if origin is None:
            text = _source(definition) if name == definition.__module__ else None
            if text is None:
                versions[root] = _version(root)
            else:
                sources[_object_name(definition)] = semantic_digest(text)
            continue
        package = _package(root, origin)
        if package is None:
            sources[name] = semantic_digest(Path(origin).read_text(encoding="utf-8"))
            continue
        relative = Path(origin).resolve().relative_to(package).as_posix()
        entries.setdefault(root, (package, set()))[1].add(relative)
    for root, (package, paths) in entries.items():
        for path in import_closure(sorted(paths), package=package, root=root):
            text = (package / path).read_text(encoding="utf-8")
            sources[f"{root}/{path}"] = semantic_digest(text)
    manifest = {
        "format": FORMAT,
        "implementation": _object_name(implementation),
        "sources": sources,
        "versions": versions,
        "python": platform.python_version(),
    }
    return f"{FORMAT}:{manifest_digest(manifest)}"


def _origin(name: str) -> str | None:
    """Return the Python source file of a module, or None if it has none."""
    module = sys.modules.get(name)
    origin = getattr(module, "__file__", None)
    if origin is None and module is None:
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError):
            spec = None
        origin = None if spec is None else spec.origin
    # A launcher can name a file that does not exist, such as pytest.exe\__main__.py.
    if isinstance(origin, str) and origin.endswith(".py") and Path(origin).is_file():
        return origin
    return None


def _package(root: str, origin: str) -> Path | None:
    """Return the folder of the top-level package that contains a source file."""
    try:
        spec = importlib.util.find_spec(root)
    except (ImportError, ValueError):
        return None
    file = Path(origin).resolve()
    for location in (spec and spec.submodule_search_locations) or ():
        folder = Path(location).resolve()
        if file.is_relative_to(folder):
            return folder
    return None


def _source(definition: object) -> str | None:
    try:
        return inspect.getsource(definition)  # type: ignore[arg-type]
    except (OSError, TypeError):
        return None


def _version(root: str) -> str | None:
    for distribution in metadata.packages_distributions().get(root, ()):
        try:
            return metadata.version(distribution)
        except metadata.PackageNotFoundError:
            continue
    return None
