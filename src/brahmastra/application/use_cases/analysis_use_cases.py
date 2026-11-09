"""
Application use cases for codebase inspection and analysis.
"""
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from brahmastra.domain.analysis.inspector import RepositoryInspector
from brahmastra.domain.analysis.models import CodebaseAnalysisReport


def analyze_repository(
    target_path: Path,
    max_depth: int = 5,
    scan_secrets: bool = True,
) -> CodebaseAnalysisReport:
    """
    Execute read-only repository inspection.
    Guarantees no file writes, mutations, or deletions.
    """
    inspector = RepositoryInspector(
        target_path=target_path,
        max_depth=max_depth,
        scan_secrets=scan_secrets,
    )
    return inspector.scan()


def export_report_as_dict(report: CodebaseAnalysisReport) -> Dict[str, Any]:
    """
    Converts a CodebaseAnalysisReport to a JSON-serializable dictionary.
    """
    data = asdict(report)
    data["scanned_at"] = report.scanned_at.isoformat()
    return data
