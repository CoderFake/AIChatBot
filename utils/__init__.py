"""Compatibility layer exposing ``api.utils`` under the legacy ``utils`` namespace."""
from __future__ import annotations

import importlib
import sys
from typing import Dict

_SUBMODULE_MAP: Dict[str, str] = {
    "datetime_utils": "api.utils.datetime_utils",
    "email_utils": "api.utils.email_utils",
    "encryption_utils": "api.utils.encryption_utils",
    "file_processor": "api.utils.file_processor",
    "jwt_utils": "api.utils.jwt_utils",
    "language_utils": "api.utils.language_utils",
    "logging": "api.utils.logging",
    "password_utils": "api.utils.password_utils",
    "prompt_utils": "api.utils.prompt_utils",
    "request_utils": "api.utils.request_utils",
}

__all__ = list(_SUBMODULE_MAP.keys())


def __getattr__(name: str):
    if name in _SUBMODULE_MAP:
        module = importlib.import_module(_SUBMODULE_MAP[name])
        sys.modules[f"{__name__}.{name}"] = module
        return module
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_SUBMODULE_MAP.keys()))
