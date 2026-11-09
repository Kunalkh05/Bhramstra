"""
Unit tests for read-only repository inspection and AST extraction.
"""
import hashlib
import os
from pathlib import Path
import pytest

from brahmastra.domain.analysis.inspector import RepositoryInspector
from brahmastra.domain.analysis.models import CodebaseAnalysisReport


def _compute_sha256(path: Path) -> str:
    """Compute sha256 checksum of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def test_inspector_directory_traversal_and_ignore(tmp_path: Path):
    """Verify inspector walks project files and ignores excluded directories."""
    # Create valid files
    src_dir = tmp_path / "src" / "pkg"
    src_dir.mkdir(parents=True)
    valid_file = src_dir / "module.py"
    valid_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    # Create ignored directories and files
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

    venv_dir = tmp_path / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "site.py").write_text("# Virtual environment file\n")

    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "module.cpython-313.pyc").write_bytes(b"\x00\x01\x02")

    inspector = RepositoryInspector(target_path=tmp_path, max_depth=5)
    report = inspector.scan()

    assert report.total_files == 1
    assert len(report.files) == 1
    assert report.files[0].relative_path == "src/pkg/module.py"
    assert report.languages[0].language == "Python"
    assert report.languages[0].file_count == 1


def test_inspector_ast_symbol_extraction(tmp_path: Path):
    """Verify AST extraction of classes, methods, functions, and imports."""
    py_file = tmp_path / "sample.py"
    code = '''"""Module docstring."""
import os
from sys import version_info as py_ver

class Engine:
    """Core engine class."""
    def start(self):
        """Start the engine."""
        pass

def run_job(timeout: int = 10):
    """Run worker job."""
    return True
'''
    py_file.write_text(code, encoding="utf-8")

    inspector = RepositoryInspector(target_path=tmp_path)
    report = inspector.scan()

    assert report.total_files == 1
    file_info = report.files[0]

    # Verify extracted symbols
    symbol_names = [s.name for s in file_info.symbols]
    assert "Engine" in symbol_names
    assert "Engine.start" in symbol_names
    assert "run_job" in symbol_names

    # Check docstrings
    class_sym = next(s for s in file_info.symbols if s.name == "Engine")
    assert class_sym.docstring == "Core engine class."
    assert class_sym.symbol_type == "class"

    fn_sym = next(s for s in file_info.symbols if s.name == "run_job")
    assert fn_sym.docstring == "Run worker job."
    assert fn_sym.symbol_type == "function"

    # Check imports
    imported_modules = [imp.module for imp in file_info.imports]
    assert "os" in imported_modules
    assert "sys" in imported_modules


def test_inspector_secret_detection_and_redaction(tmp_path: Path):
    """Verify detection of leaked credentials and guarantee zero unmasked secrets."""
    secret_file = tmp_path / "config.py"
    # Create fake test keys matching production provider regexes
    fake_proj_key = "sk-proj-" + "a" * 50
    fake_google_key = "AIzaSy" + "b" * 33

    secret_file.write_text(
        f'OPENAI_API_KEY = "{fake_proj_key}"\n'
        f'GOOGLE_API_KEY = "{fake_google_key}"\n',
        encoding="utf-8",
    )

    inspector = RepositoryInspector(target_path=tmp_path, scan_secrets=True)
    report = inspector.scan()

    assert len(report.security_findings) == 2
    rule_ids = {f.rule_id for f in report.security_findings}
    assert "openai_proj" in rule_ids
    assert "google_api" in rule_ids

    # CRITICAL: Verify that the raw unmasked secrets NEVER appear in the finding snippets
    for finding in report.security_findings:
        assert fake_proj_key not in finding.masked_snippet
        assert fake_google_key not in finding.masked_snippet
        assert "[REDACTED]" in finding.masked_snippet


def test_inspector_binary_file_handling(tmp_path: Path):
    """Verify binary files with null bytes are detected and skipped for AST/text parsing."""
    bin_file = tmp_path / "data.bin"
    bin_file.write_bytes(b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 100)

    inspector = RepositoryInspector(target_path=tmp_path)
    report = inspector.scan()

    assert report.total_files == 1
    assert report.files[0].is_binary is True
    assert report.files[0].lines_of_code == 0
    assert len(report.files[0].symbols) == 0


def test_inspector_strict_read_only_guarantee(tmp_path: Path):
    """Verify strict read-only guarantee: file hashes and timestamps are unmodified."""
    test_file = tmp_path / "immutable.py"
    test_file.write_text("x = 42\ny = 100\n", encoding="utf-8")

    initial_mtime = test_file.stat().st_mtime_ns
    initial_hash = _compute_sha256(test_file)

    inspector = RepositoryInspector(target_path=tmp_path)
    report = inspector.scan()

    after_mtime = test_file.stat().st_mtime_ns
    after_hash = _compute_sha256(test_file)

    assert initial_mtime == after_mtime, "File modification timestamp changed!"
    assert initial_hash == after_hash, "File content hash changed during read-only inspection!"


def test_inspector_nonexistent_path_raises():
    """Verify inspecting a non-existent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        RepositoryInspector(target_path=Path("/path/does/not/exist/brahmastra_test"))
