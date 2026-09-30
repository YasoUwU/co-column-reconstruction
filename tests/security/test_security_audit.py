from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = PROJECT_ROOT / "tools" / "security_audit.py"
SPEC = importlib.util.spec_from_file_location("security_audit", AUDIT_PATH)
assert SPEC is not None and SPEC.loader is not None
security_audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = security_audit
SPEC.loader.exec_module(security_audit)


def _write(root: Path, relative: str, content: str = "safe\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _rules(root: Path) -> set[str]:
    return {finding.rule for finding in security_audit.audit_repository(root)}


@pytest.mark.parametrize(
    ("parts", "expected_rule"),
    [
        (("local_path = ", "D", ":/private/input"), "absolute Windows path"),
        (("source = ", "\\", "\\host\\share\\input"), "UNC/network path"),
        (("user", "@", "example.invalid"), "email address (possible PII)"),
        (("contact = +", "261 34 12 345 67"), "phone number (possible PII)"),
    ],
)
def test_text_hazards_are_detected_without_static_fixture_secrets(
    tmp_path: Path, parts: tuple[str, ...], expected_rule: str
) -> None:
    _write(tmp_path, "module.py", "".join(parts))
    assert expected_rule in _rules(tmp_path)


def test_literal_secret_assignment_is_detected_and_redacted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sensitive_value = "not-a-real-credential-123"
    _write(tmp_path, "settings.py", "pass" + "word = " + repr(sensitive_value))

    result = security_audit.main([str(tmp_path)])
    captured = capsys.readouterr()

    assert result == 1
    assert "literal secret assignment" in captured.err
    assert sensitive_value not in captured.err


def test_private_key_marker_is_detected(tmp_path: Path) -> None:
    marker = "-----BEGIN " + "PRIVATE KEY-----"
    _write(tmp_path, "key.txt", marker)
    assert "private key material" in _rules(tmp_path)


@pytest.mark.parametrize(
    "name",
    ["sample.nc", "table.csv", "array.npy", "model.joblib", "figure.png", "bundle.zip"],
)
def test_forbidden_extensions_are_detected(tmp_path: Path, name: str) -> None:
    _write(tmp_path, name)
    assert "forbidden data/model/archive/media type" in _rules(tmp_path)


@pytest.mark.parametrize("name", [".env", ".env.production", "config.local.yaml"])
def test_local_configuration_files_are_detected(tmp_path: Path, name: str) -> None:
    _write(tmp_path, name)
    assert "forbidden credential/configuration file" in _rules(tmp_path)


def test_forbidden_artefact_directory_is_detected(tmp_path: Path) -> None:
    _write(tmp_path, "outputs/result.txt")
    assert "file stored in a forbidden artefact directory" in _rules(tmp_path)


def test_large_file_is_detected_without_reading_content(tmp_path: Path) -> None:
    path = tmp_path / "large.bin"
    with path.open("wb") as stream:
        stream.truncate(security_audit.MAX_FILE_SIZE + 1)
    assert "file exceeds 10 MiB" in _rules(tmp_path)


def test_clean_tree_passes(tmp_path: Path) -> None:
    _write(tmp_path, "src/module.py", "value = 42\n")
    assert security_audit.audit_repository(tmp_path) == []
    assert security_audit.main([str(tmp_path)]) == 0


def test_cli_returns_nonzero_and_does_not_echo_sensitive_value(tmp_path: Path) -> None:
    sensitive_value = "another-fake-credential-456"
    _write(tmp_path, "config.yaml", "api_" + "key: " + sensitive_value)

    completed = subprocess.run(
        [sys.executable, str(AUDIT_PATH), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "literal secret assignment" in completed.stderr
    assert sensitive_value not in completed.stdout + completed.stderr


def test_scanner_skips_its_security_test_directory(tmp_path: Path) -> None:
    _write(tmp_path, "tests/security/generated.py", "pass" + "word='fake-secret'")
    assert security_audit.audit_repository(tmp_path) == []
