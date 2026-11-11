"""
Domain models for repository inspection and codebase analysis.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass(frozen=True)
class SymbolInfo:
    """Represents a code symbol extracted via AST."""
    name: str
    symbol_type: str  # "class", "function", "method"
    line_number: int
    docstring: Optional[str] = None
    file_path: str = ""


@dataclass(frozen=True)
class ImportInfo:
    """Represents an imported module or name."""
    module: str
    name: Optional[str] = None
    alias: Optional[str] = None


@dataclass(frozen=True)
class SecurityFinding:
    """Represents a detected secret or credential leak."""
    rule_id: str
    rule_name: str
    file_path: str
    line_number: int
    masked_snippet: str
    severity: str = "HIGH"  # "CRITICAL", "HIGH", "MEDIUM"


@dataclass(frozen=True)
class FileInfo:
    """Metadata and metrics for a scanned file."""
    relative_path: str
    absolute_path: str
    size_bytes: int
    lines_of_code: int
    language: str
    token_estimate: int
    is_binary: bool = False
    symbols: List[SymbolInfo] = field(default_factory=list)
    imports: List[ImportInfo] = field(default_factory=list)


@dataclass(frozen=True)
class LanguageStat:
    """Language breakdown across the codebase."""
    language: str
    file_count: int
    lines_of_code: int
    percentage: float


@dataclass
class CodebaseAnalysisReport:
    """Comprehensive analysis report for a scanned repository."""
    target_path: str
    scanned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_files: int = 0
    total_lines: int = 0
    total_bytes: int = 0
    estimated_tokens: int = 0
    languages: List[LanguageStat] = field(default_factory=list)
    files: List[FileInfo] = field(default_factory=list)
    all_symbols: List[SymbolInfo] = field(default_factory=list)
    security_findings: List[SecurityFinding] = field(default_factory=list)
    architecture_assessment: str = ""
    readiness_status: str = "READY"
