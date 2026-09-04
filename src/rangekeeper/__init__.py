from importlib import import_module
from types import ModuleType

from . import validate as validate
from . import measure as measure
from . import graph as graph

# Helper Methods:
import functools


_LAZY_MODULES = frozenset(
    {
        "api",
        "distribution",
        "duration",
        "dynamics",
        "extrapolation",
        "flux",
        "formula",
        "format",
        "policy",
        "projection",
        "segmentation",
    }
)

__all__ = [
    "api",
    "distribution",
    "duration",
    "dynamics",
    "extrapolation",
    "flux",
    "formula",
    "format",
    "graph",
    "measure",
    "policy",
    "projection",
    "rgba_from_cmap",
    "segmentation",
    "update_class",
    "validate",
]


def __getattr__(name: str) -> ModuleType:
    if name not in _LAZY_MODULES:
        raise AttributeError(name)
    module = import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted({*globals(), *_LAZY_MODULES})


def update_class(
    main_class=None, exclude=("__module__", "__name__", "__dict__", "__weakref__")
):
    """Class decorator. Adds all methods and members from the wrapped class to main_class

    Args:
    - main_class: class to which to append members. Defaults to the class with the same name as the wrapped class
    - exclude: black-list of members which should not be copied
    """

    def decorates(main_class, exclude, appended_class):
        if main_class is None:
            main_class = locals()[appended_class.__name__]
        for k, v in appended_class.__dict__.items():
            if k not in exclude:
                setattr(main_class, k, v)
        return main_class

    return functools.partial(decorates, main_class, exclude)


def rgba_from_cmap(cmap_name, start_val, stop_val, val):
    """
    Returns the rgb value of a color from a matplotlib colormap
    from https://stackoverflow.com/a/26109298
    """
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from matplotlib import cm

    cmap = plt.get_cmap(cmap_name)
    norm = mpl.colors.Normalize(vmin=start_val, vmax=stop_val)
    scalar_map = cm.ScalarMappable(norm=norm, cmap=cmap)
    return scalar_map.to_rgba(val)
