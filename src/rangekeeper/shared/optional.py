"""Import optional dependencies with the extra that installs them."""

from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def requires(extra: str) -> Iterator[None]:
    """Give an ImportError inside the block an installation hint for one extra.

    Wrap the import statement where the dependency is needed, so that importing
    Rangekeeper and its core modules needs no optional extra::

        with requires("bundle"):
            import pyarrow as pa
    """
    try:
        yield
    except ImportError as error:
        package = (error.name or "A dependency").partition(".")[0]
        raise ImportError(
            f"{package} is not installed. Install it with: "
            f"pip install 'rangekeeper[{extra}]'",
            name=error.name,
        ) from error
