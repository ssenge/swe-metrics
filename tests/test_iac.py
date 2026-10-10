"""terraform validate, tflint and checkov on recorded outputs, and on the Terraform fixture when installed."""
import json
import shutil
from pathlib import Path

import pytest

from swe_metrics.analyzers import checkov as checkov_module
from swe_metrics.analyzers import terraform as terraform_module
from swe_metrics.analyzers import tflint as tflint_module
from swe_metrics.analyzers.checkov import Checkov
from swe_metrics.analyzers.terraform import Terraform
from swe_metrics.analyzers.tflint import Tflint
from swe_metrics.core.target import Target
from swe_metrics.tools import process
from swe_metrics.tools.files import copy_directories
from swe_metrics.tools.process import ToolError
from tests.helpers import FIXTURES, values

TERRAFORM = FIXTURES / "terraform"
EXPECTED = json.loads((TERRAFORM / "expected.json").read_text())
ALL = ("broken/main.tf", "expected.json", "storage/main.tf", "valid/main.tf")
OFFLINE = ("broken/main.tf", "valid/main.tf")  # modules that validate without downloading a provider


def recorded_terraform(argv, cwd, ok=(0,)):
    """init succeeds; validate prints the recorded result of the module it runs in."""
    if argv[1] == "init":
        assert "-backend=false" in argv
        return ""
    return (FIXTURES / "recorded" / f"terraform-validate-{Path(cwd).name}.json").read_text()


def test_terraform_validation_errors_per_module(tmp_path, monkeypatch):
    """One error in broken/, none in valid/; each module is validated on its own copy."""
    monkeypatch.setattr(terraform_module, "run", recorded_terraform)
    analyzer = Terraform()
    target = Target(str(TERRAFORM), ALL)
    assert analyzer.applicable(target) == ("broken/main.tf", "storage/main.tf", "valid/main.tf")
    assert analyzer.prerequisites() == ""
    result = analyzer.measure(target, OFFLINE, str(tmp_path))
    assert values(result.metrics, "iac.validation_errors") == EXPECTED["iac.validation_errors"]
    assert {m.scope.level for m in result.metrics} == {"module", "target"}
    assert (tmp_path / "modules" / "valid" / "main.tf").exists()
    detail = json.loads(Path(result.details[0][1]).read_text())
    assert sorted(detail) == ["broken", "valid"]


def test_terraform_failed_init_names_the_module(tmp_path, monkeypatch):
    """A failed init (e.g. no network for a provider) fails the analyzer, naming the module."""
    def failing_init(argv, cwd, ok=(0,)):
        raise ToolError("terraform exited with 1: Failed to query available provider packages")
    monkeypatch.setattr(terraform_module, "run", failing_init)
    with pytest.raises(ToolError, match="init failed in module storage"):
        Terraform().measure(Target(str(TERRAFORM), ALL), ("storage/main.tf",), str(tmp_path))


def test_copy_directories_copies_whole_directories(tmp_path):
    """Every file of a given file's directory is copied, the root directory is ".", subdirectories aren't."""
    (tmp_path / "src" / "net" / "sub").mkdir(parents=True)
    for path in ("main.tf", "net/a.tf", "net/vars.tfvars", "net/sub/b.tf"):
        (tmp_path / "src" / path).write_text("")
    copied = copy_directories(str(tmp_path / "src"), ("main.tf", "net/a.tf"), tmp_path / "copy")
    assert copied == [".", "net"]
    assert sorted(str(p.relative_to(tmp_path / "copy")) for p in (tmp_path / "copy").rglob("*.tf*")) == [
        "main.tf", "net/a.tf", "net/vars.tfvars"]


def recorded_tflint(output):
    """A fake run that checks the fixed configuration and prints the given SARIF."""
    def fake_run(argv, cwd, ok=(0,)):
        config = Path(argv[argv.index("--config") + 1]).read_text()
        assert 'preset  = "recommended"' in config and "--recursive" in argv
        return output
    return fake_run


def test_tflint_counts_per_file_and_rule(tmp_path, monkeypatch):
    """Recorded findings per file and rule; findings outside the given files are dropped."""
    sarif = (FIXTURES / "recorded" / "tflint.sarif").read_text()
    monkeypatch.setattr(tflint_module, "run", recorded_tflint(sarif))
    analyzer = Tflint()
    target = Target(str(TERRAFORM), ALL)
    assert analyzer.applicable(target) == ("broken/main.tf", "storage/main.tf", "valid/main.tf")
    assert analyzer.prerequisites() == ""
    result = analyzer.measure(target, analyzer.applicable(target), str(tmp_path))
    assert values(result.metrics, "iac.lint_findings") == EXPECTED["iac.lint_findings"]
    result = analyzer.measure(target, OFFLINE, str(tmp_path))
    assert values(result.metrics, "iac.lint_findings") == {"total": 0}
    assert result.details[0][0] == "sarif"


def test_tflint_errors_fail_the_analyzer(tmp_path, monkeypatch):
    """A module tflint couldn't load raises with tflint's message instead of counting it as a finding."""
    errors = {"runs": [{"tool": {"driver": {"name": "tflint"}}, "results": []},
                       {"tool": {"driver": {"name": "tflint-errors"}},
                        "results": [{"ruleId": "application_error",
                                     "message": {"text": "Failed to run in bad; exit status 1\n\nmore"}}]}]}
    monkeypatch.setattr(tflint_module, "run", recorded_tflint(json.dumps(errors)))
    with pytest.raises(ToolError, match="tflint failed: Failed to run in bad; exit status 1$"):
        Tflint().measure(Target(str(TERRAFORM), ALL), ("storage/main.tf",), str(tmp_path))


@pytest.mark.parametrize(("printed", "expected"), [
    ("TFLint version 0.64.0\n+ ruleset.terraform (0.15.0-bundled)\n",
     "0.64.0 (ruleset terraform 0.15.0-bundled, recommended preset)"),
    ("TFLint version 0.64.0\n", None),
])
def test_tflint_version_includes_ruleset(monkeypatch, printed, expected):
    """The bundled ruleset's version is part of the version string; without it there is no version."""
    monkeypatch.setattr(process, "run", lambda argv, cwd, ok=(0,): printed)
    assert Tflint().version() == expected


@pytest.mark.skipif(not shutil.which("terraform"), reason="terraform not installed")
def test_terraform_real_tool_leaves_the_target_untouched(tmp_path):
    """The real tool finds the undeclared variable; the fixture gets no .terraform directory."""
    analyzer = Terraform()
    assert analyzer.version()
    result = analyzer.measure(Target(str(TERRAFORM), ALL), OFFLINE, str(tmp_path))
    assert values(result.metrics, "iac.validation_errors") == EXPECTED["iac.validation_errors"]
    assert not any(TERRAFORM.rglob(".terraform*"))


@pytest.mark.skipif(not shutil.which("tflint"), reason="tflint not installed")
def test_tflint_real_tool_ignores_target_config(tmp_path):
    """A .tflint.hcl in the target that disables the ruleset doesn't change what is measured."""
    copy = shutil.copytree(TERRAFORM, tmp_path / "terraform")
    (copy / ".tflint.hcl").write_text('plugin "terraform" {\n  enabled = false\n}\n')
    (tmp_path / "scratch").mkdir()
    analyzer = Tflint()
    assert analyzer.version()
    result = analyzer.measure(Target(str(copy), ALL), ALL[:1] + ALL[2:], str(tmp_path / "scratch"))
    assert values(result.metrics, "iac.lint_findings") == EXPECTED["iac.lint_findings"]


def recorded_checkov(report):
    """A fake run that writes the given checkov JSON report and an empty SARIF into --output-file-path."""
    def fake_run(argv, cwd, ok=(0,)):
        assert argv[argv.index("--framework") + 1] == "terraform" and "--skip-download" in argv
        output = Path(argv[argv.index("--output-file-path") + 1])
        output.mkdir()
        (output / "results_json.json").write_text(json.dumps(report))
        (output / "results_sarif.sarif").write_text("{}")
        return ""
    return fake_run


def test_checkov_counts_failed_checks_per_file_and_check(tmp_path, monkeypatch):
    """Failed checks per file and check ID, passed checks and resources in total, on a copy."""
    report = json.loads((FIXTURES / "recorded" / "checkov.json").read_text())
    monkeypatch.setattr(checkov_module, "run", recorded_checkov(report))
    analyzer = Checkov()
    target = Target(str(TERRAFORM), ALL)
    assert analyzer.applicable(target) == ("broken/main.tf", "storage/main.tf", "valid/main.tf")
    assert analyzer.prerequisites() == ""
    result = analyzer.measure(target, analyzer.applicable(target), str(tmp_path))
    for metric_id in ("iac.misconfigurations", "iac.passed_checks", "iac.resources"):
        assert values(result.metrics, metric_id) == EXPECTED[metric_id]
    assert (tmp_path / "modules" / "storage" / "main.tf").exists()
    assert [fmt for fmt, _ in result.details] == ["sarif", "checkov-json"]


def test_checkov_without_resources_and_with_parsing_errors(tmp_path, monkeypatch):
    """A summary-only report gives zeros; a file checkov couldn't parse fails the analyzer."""
    summary = {"passed": 0, "failed": 0, "parsing_errors": 0, "resource_count": 0}
    monkeypatch.setattr(checkov_module, "run", recorded_checkov(summary))
    result = Checkov().measure(Target(str(TERRAFORM), ALL), ("valid/main.tf",), str(tmp_path / "a"))
    assert {m.id: m.value for m in result.metrics} == {
        "iac.misconfigurations": 0, "iac.passed_checks": 0, "iac.resources": 0}
    broken = {"summary": {**summary, "parsing_errors": 1},
              "results": {"parsing_errors": ["/tmp/x/modules/valid/main.tf"]}}
    monkeypatch.setattr(checkov_module, "run", recorded_checkov(broken))
    with pytest.raises(ToolError, match="could not parse: valid/main.tf$"):
        Checkov().measure(Target(str(TERRAFORM), ALL), ("valid/main.tf",), str(tmp_path / "b"))


def test_checkov_version_records_settings(monkeypatch):
    """The framework and check set are part of the version string."""
    monkeypatch.setattr(checkov_module, "version", lambda argv: "3.3.26")
    assert Checkov().version() == "3.3.26 (terraform framework, built-in checks)"
    monkeypatch.setattr(checkov_module, "version", lambda argv: None)
    assert Checkov().version() is None


@pytest.mark.skipif(not shutil.which("checkov"), reason="checkov not installed")
def test_checkov_real_tool_ignores_target_config(tmp_path):
    """A .checkov.yaml in the target that skips a check doesn't change what is measured."""
    copy = shutil.copytree(TERRAFORM, tmp_path / "terraform")
    (copy / "storage" / ".checkov.yaml").write_text("skip-check:\n  - CKV_AWS_18\n")
    (tmp_path / "scratch").mkdir()
    analyzer = Checkov()
    assert analyzer.version()
    files = ("broken/main.tf", "storage/main.tf", "valid/main.tf")
    result = analyzer.measure(Target(str(copy), ALL), files, str(tmp_path / "scratch"))
    for metric_id in ("iac.misconfigurations", "iac.passed_checks", "iac.resources"):
        assert values(result.metrics, metric_id) == EXPECTED[metric_id]
