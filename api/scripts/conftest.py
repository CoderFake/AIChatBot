"""Pytest configuration to expose project packages to script tests."""
from __future__ import annotations

import importlib
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Ensure legacy absolute imports remain valid in test context
sys.modules.setdefault("utils", importlib.import_module("api.utils"))
sys.modules.setdefault("config", importlib.import_module("api.config"))


import pytest


@pytest.fixture
def tenant_id() -> str:
    """Provide a deterministic tenant id for async workflow tests."""

    return "b397ab8f-353e-4031-a6b5-549904bb698d"
