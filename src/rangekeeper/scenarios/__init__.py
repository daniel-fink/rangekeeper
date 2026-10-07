"""Market scenarios with lazy runtime imports and lightweight contract access."""

from importlib import import_module

__all__ = ["market", "Market", "replay", "ReplayUnavailableError"]


def __getattr__(name):
    if name == "market":
        value = import_module(".market", __name__)
    elif name == "Market":
        value = getattr(import_module(".view", __name__), name)
    elif name in {"replay", "ReplayUnavailableError"}:
        value = getattr(import_module(".replay", __name__), name)
    else:
        raise AttributeError(name)
    globals()[name] = value
    return value
