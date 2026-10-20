import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STUB_MODULES = (
    "fastapi",
    "mangum",
    "providers",
    "providers.projectdiscovery",
    "lambda_app",
)


@pytest.fixture(scope="module")
def lambda_app():
    saved = {name: sys.modules.get(name) for name in STUB_MODULES}

    fastapi = types.ModuleType("fastapi")

    class FastAPI:
        def get(self, path):
            return lambda fn: fn

    fastapi.FastAPI = FastAPI

    mangum = types.ModuleType("mangum")

    class Mangum:
        def __init__(self, app):
            self.app = app

    mangum.Mangum = Mangum

    providers = types.ModuleType("providers")
    providers.__path__ = []
    projectdiscovery = types.ModuleType("providers.projectdiscovery")
    projectdiscovery.fetch_domains = lambda *args, **kwargs: []
    providers.projectdiscovery = projectdiscovery

    sys.modules.update(
        {
            "fastapi": fastapi,
            "mangum": mangum,
            "providers": providers,
            "providers.projectdiscovery": projectdiscovery,
        }
    )

    try:
        spec = importlib.util.spec_from_file_location("lambda_app", ROOT / "lambda.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["lambda_app"] = module
        spec.loader.exec_module(module)
        yield module
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, 2000),
        ("50", 50),
        (" 7 ", 7),
        ("0", 2000),
        ("-3", 2000),
        ("abc", 2000),
        ("", 2000),
    ],
)
def test_env_positive_int(lambda_app, monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("SCAN_DOMAIN_LIMIT", raising=False)
    else:
        monkeypatch.setenv("SCAN_DOMAIN_LIMIT", raw)

    assert lambda_app._env_positive_int("SCAN_DOMAIN_LIMIT", 2000) == expected
