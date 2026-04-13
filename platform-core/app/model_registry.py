from __future__ import annotations

from importlib import import_module

_MODEL_MODULES = (
    "app.dashboard.models",
    "app.memberships.models",
    "app.notifications.models",
    "app.registry.models",
    "app.spaces.models",
    "app.users.models",
)

_loaded = False


def load_all_models() -> None:
    global _loaded

    if _loaded:
        return

    for module_path in _MODEL_MODULES:
        import_module(module_path)

    _loaded = True
