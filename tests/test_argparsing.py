import sys
import types

import pytest


@pytest.fixture
def argparsing(monkeypatch):
    saved_providers = sys.modules.get("providers")
    saved_argparsing = sys.modules.pop("argparsing", None)

    providers = types.ModuleType("providers")

    def fetch_domains(required_arg, optional_arg="default", **kwargs):
        pass

    stub = types.ModuleType("providers.stub")
    stub.description = "stub provider"
    stub.fetch_domains = fetch_domains
    providers.stub = stub
    providers.__all__ = ["stub"]
    sys.modules["providers"] = providers

    import argparsing

    yield argparsing

    sys.modules.pop("argparsing", None)
    if saved_providers is None:
        sys.modules.pop("providers", None)
    else:
        sys.modules["providers"] = saved_providers
    if saved_argparsing is not None:
        sys.modules["argparsing"] = saved_argparsing


def test_out_accepts_equals_form(argparsing, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "stub", "--required-arg", "x", "--out=report.json"],
    )

    assert argparsing.parse_args().out == "report.json"


def test_out_defaults_to_none(argparsing, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "stub", "--required-arg", "x"])

    assert argparsing.parse_args().out is None


def test_out_stdout(argparsing, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "stub", "--required-arg", "x", "--out=stdout"],
    )

    assert argparsing.parse_args().out == "stdout"


def test_parallelism_rejects_zero(argparsing, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "stub", "--required-arg", "x", "--parallelism", "0"],
    )

    with pytest.raises(SystemExit) as error:
        argparsing.parse_args()

    assert error.value.code == 2


def test_parallelism_accepts_one(argparsing, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "stub", "--required-arg", "x", "--parallelism", "1"],
    )

    assert argparsing.parse_args().parallelism == 1


def test_parallelism_rejects_text(argparsing, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "stub", "--required-arg", "x", "--parallelism", "many"],
    )

    with pytest.raises(SystemExit) as error:
        argparsing.parse_args()

    assert error.value.code == 2
