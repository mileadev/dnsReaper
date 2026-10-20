import json

from output import Output, resolve_output_path
from scan import pipeline_exit_code, scan_exit_code


class DummyFinding:
    def __init__(self):
        self.domain = "example.com"
        self.signature = "test"


def test_empty_json_is_valid(tmp_path):
    target = tmp_path / "r.json"
    with Output("json", str(target)):
        pass
    assert json.loads(target.read_text()) == []


def test_one_finding_json(tmp_path):
    target = tmp_path / "r.json"
    with Output("json", str(target)) as out:
        out.write(DummyFinding())
    assert len(json.loads(target.read_text())) == 1


def test_multiple_findings_json_have_valid_commas(tmp_path):
    target = tmp_path / "r.json"
    with Output("json", str(target)) as out:
        out.write(DummyFinding())
        out.write(DummyFinding())
    assert len(json.loads(target.read_text())) == 2


def test_resolve_output_path():
    assert resolve_output_path(None, "json") == "results.json"
    assert resolve_output_path("report.json", "json") == "report.json"
    assert resolve_output_path("stdout", "csv") == "stdout"


def test_pipeline_exit_code():
    assert pipeline_exit_code([]) == 0
    assert pipeline_exit_code([object()] * 256) == 1


def test_scan_exit_code():
    assert scan_exit_code([]) == 0
    assert scan_exit_code([object()]) == 0
    assert scan_exit_code([], pipeline=True) == 0
    assert scan_exit_code([object()], pipeline=True) == 1
    assert scan_exit_code([], timed_out=True) == 3
    assert scan_exit_code([object()], timed_out=True, pipeline=True) == 3
