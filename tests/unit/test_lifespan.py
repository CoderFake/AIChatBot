import os
import sys
import types

import asyncio
import pytest

# Provide stubs for external modules required by api.main during import
sys.modules.setdefault("uvicorn", types.ModuleType("uvicorn"))

fastapi_stub = types.ModuleType("fastapi")
class _FastAPI:
    def __init__(self, *args, **kwargs):
        pass

    def add_middleware(self, *args, **kwargs):
        pass

    def include_router(self, *args, **kwargs):
        pass

    def middleware(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def get(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


class _Request:
    pass


fastapi_stub.FastAPI = _FastAPI
fastapi_stub.Request = _Request
fastapi_stub.HTTPException = type("HTTPException", (Exception,), {})

middleware_mod = types.ModuleType("fastapi.middleware")
cors_mod = types.ModuleType("fastapi.middleware.cors")
cors_mod.CORSMiddleware = object
middleware_mod.cors = cors_mod
fastapi_stub.middleware = middleware_mod
responses_mod = types.ModuleType("fastapi.responses")
responses_mod.JSONResponse = object
fastapi_stub.responses = responses_mod
exceptions_mod = types.ModuleType("fastapi.exceptions")
exceptions_mod.RequestValidationError = type(
    "RequestValidationError", (Exception,), {}
)
fastapi_stub.exceptions = exceptions_mod

sys.modules.setdefault("fastapi", fastapi_stub)
sys.modules.setdefault("fastapi.middleware", middleware_mod)
sys.modules.setdefault("fastapi.middleware.cors", cors_mod)
sys.modules.setdefault("fastapi.responses", responses_mod)
sys.modules.setdefault("fastapi.exceptions", exceptions_mod)

sys.path.append(os.path.abspath("api"))

dummy_settings = types.SimpleNamespace(
    DEBUG=True,
    ENV="test",
    CORS_ORIGINS=[],
    orchestrator={"enabled": True},
    get_enabled_providers=lambda: [],
    get_enabled_agents=lambda: [],
    get_enabled_tools=lambda: [],
)
settings_mod = types.SimpleNamespace(get_settings=lambda: dummy_settings)
config_mod = types.ModuleType("config")
config_mod.settings = settings_mod
sys.modules.setdefault("config", config_mod)
sys.modules.setdefault("config.settings", settings_mod)

# Stub API router modules
api_v1_router_mod = types.SimpleNamespace(api_router=object())
api_v1_endpoints_mod = types.ModuleType("api.v1.endpoints")
api_v1_endpoints_streaming = types.SimpleNamespace(router=object())
api_v1_endpoints_mod.streaming = api_v1_endpoints_streaming
sys.modules.setdefault("api.v1", types.ModuleType("api.v1"))
sys.modules.setdefault("api.v1.router", api_v1_router_mod)
sys.modules.setdefault("api.v1.endpoints", api_v1_endpoints_mod)
sys.modules.setdefault("api.v1.endpoints.streaming", api_v1_endpoints_streaming)

core_exceptions_mod = types.SimpleNamespace(setup_exception_handlers=lambda app: None)
sys.modules.setdefault("core.exceptions", core_exceptions_mod)

from api.main import _init_db, _init_milvus, _init_llm_providers


def test_init_db(monkeypatch):
    called = {}

    async def fake_init_db():
        called["init"] = True

    db_module = types.SimpleNamespace(init_db=fake_init_db)
    monkeypatch.setitem(sys.modules, "config.database", db_module)

    asyncio.run(_init_db())
    assert called.get("init") is True


def test_init_milvus(monkeypatch):
    class DummyMilvus:
        def __init__(self):
            self.initialized = False
            self.collection_configs = {}

        async def initialize(self):
            self.initialized = True

        async def health_check(self):  # pragma: no cover - not used here
            return True

    dummy = DummyMilvus()
    monkeypatch.setitem(
        sys.modules,
        "services.vector.milvus_service",
        types.SimpleNamespace(milvus_service=dummy),
    )

    result = asyncio.run(_init_milvus())
    assert result.initialized is True


def test_init_llm_providers(monkeypatch):
    called = {}

    async def fake_initialize(db_session):
        called["initialized"] = isinstance(db_session, object)

    class DummySession:
        def close(self):
            called["closed"] = True

    def fake_get_db_session():
        yield DummySession()

    llm_module = types.SimpleNamespace(
        llm_provider_manager=types.SimpleNamespace(initialize=fake_initialize)
    )
    db_module = types.SimpleNamespace(get_db_session=fake_get_db_session)

    monkeypatch.setitem(
        sys.modules, "services.llm.provider_manager", llm_module
    )
    monkeypatch.setitem(sys.modules, "config.database", db_module)

    asyncio.run(_init_llm_providers())
    assert called == {"initialized": True, "closed": True}

