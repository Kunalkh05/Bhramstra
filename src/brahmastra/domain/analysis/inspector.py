"""
Repository inspection engine for static code analysis, AST extraction,
and credential leak detection. Strictly read-only.
"""
import ast
import os
import re
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set, Tuple

from brahmastra.domain.analysis.models import (
    CodebaseAnalysisReport,
    FileInfo,
    ImportInfo,
    LanguageStat,
    SecurityFinding,
    SymbolInfo,
)


class RepositoryInspector:
    """
    Read-only repository scanner that traverses file trees, parses ASTs,
    estimates token consumption, and detects credential leaks.
    """

    DEFAULT_IGNORED_DIRS: Set[str] = {
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".brahmastra",
        "node_modules",
        "dist",
        "build",
        ".egg-info",
        ".tox",
        ".idea",
        ".vscode",
        ".coverage",
    }

    DEFAULT_IGNORED_EXTENSIONS: Set[str] = {
        ".pyc",
        ".pyo",
        ".pyd",
        ".so",
        ".dylib",
        ".dll",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".svg",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".lock",
    }

    EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
        ".py": "Python",
        ".md": "Markdown",
        ".toml": "TOML",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".json": "JSON",
        ".sh": "Shell",
        ".bash": "Shell",
        ".zsh": "Shell",
        ".sql": "SQL",
        ".txt": "Text",
        ".html": "HTML",
        ".css": "CSS",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".rst": "reStructuredText",
        ".ini": "Config",
        ".cfg": "Config",
    }

    # Pre-compiled high-precision security regex patterns
    SECURITY_PATTERNS: Dict[str, re.Pattern] = {
        "openai_proj": re.compile(r"\bsk-proj-[a-zA-Z0-9_\-]{48,160}\b"),
        "openai_std": re.compile(r"\bsk-[a-zA-Z0-9]{20,48}\b"),
        "anthropic": re.compile(r"\bsk-ant-(?:api03|admin01)?-[a-zA-Z0-9_\-]{32,120}\b"),
        "google_api": re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
        "groq_api": re.compile(r"\bgsk_[a-zA-Z0-9]{48,64}\b"),
        "huggingface": re.compile(r"\bhf_[a-zA-Z0-9]{34,40}\b"),
        "aws_access_key": re.compile(r"\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b"),
        "bearer_token": re.compile(r"(?i)\bBearer\s+([a-zA-Z0-9_\-\.]{24,})\b"),
        "hardcoded_secret": re.compile(
            r"(?i)\b(?:api[_-]?key|secret[_-]?key|auth[_-]?token|private[_-]?key)\s*[:=]\s*['\"]([a-zA-Z0-9_\-\.]{20,})['\"]"
        ),
    }

    MAX_PARSE_FILE_SIZE_BYTES: int = 1_048_576  # 1 MB threshold

    def __init__(
        self,
        target_path: Path,
        max_depth: int = 5,
        scan_secrets: bool = True,
        extra_ignored_dirs: Optional[Set[str]] = None,
    ):
        self.target_path = target_path.resolve()
        if not self.target_path.exists():
            raise FileNotFoundError(f"Target path does not exist: {self.target_path}")

        self.max_depth = max_depth
        self.scan_secrets = scan_secrets
        self.ignored_dirs = self.DEFAULT_IGNORED_DIRS.copy()
        if extra_ignored_dirs:
            self.ignored_dirs.update(extra_ignored_dirs)

    def is_binary_file(self, file_path: Path) -> bool:
        """
        Check if a file is binary by looking for null bytes in the first 1024 bytes.
        """
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\x00" in chunk
        except Exception:
            return True

    def scan(self) -> CodebaseAnalysisReport:
        """
        Execute read-only analysis and return the comprehensive report.
        """
        report = CodebaseAnalysisReport(target_path=str(self.target_path))
        file_infos: List[FileInfo] = []
        all_symbols: List[SymbolInfo] = []
        security_findings: List[SecurityFinding] = []
        language_lines: Dict[str, int] = {}
        language_files: Dict[str, int] = {}

        for file_path in self._walk_directory():
            file_info, symbols, findings = self._inspect_file(file_path)
            file_infos.append(file_info)
            all_symbols.extend(symbols)
            security_findings.extend(findings)

            # Accumulate language metrics
            lang = file_info.language
            language_files[lang] = language_files.get(lang, 0) + 1
            language_lines[lang] = language_lines.get(lang, 0) + file_info.lines_of_code

            report.total_files += 1
            report.total_lines += file_info.lines_of_code
            report.total_bytes += file_info.size_bytes
            report.estimated_tokens += file_info.token_estimate

        # Calculate language distribution percentages
        total_loc = report.total_lines or 1
        languages: List[LanguageStat] = []
        for lang, lines in sorted(language_lines.items(), key=lambda item: item[1], reverse=True):
            pct = round((lines / total_loc) * 100, 1)
            languages.append(
                LanguageStat(
                    language=lang,
                    file_count=language_files[lang],
                    lines_of_code=lines,
                    percentage=pct,
                )
            )

        report.languages = languages
        report.files = file_infos
        report.all_symbols = all_symbols
        report.security_findings = security_findings

        # Formulate architecture and readiness assessment
        self._assess_codebase(report)

        return report

    def _walk_directory(self) -> Iterator[Path]:
        """
        Walks directory respecting ignore lists, symlink cycles, and depth limits.
        """
        if self.target_path.is_file():
            yield self.target_path
            return

        visited_real_paths: Set[str] = set()

        for root, dirs, files in os.walk(self.target_path, followlinks=False):
            current_root = Path(root).resolve()
            
            # Prevent infinite recursion loops via symlinks
            real_path = str(current_root)
            if real_path in visited_real_paths:
                dirs.clear()
                continue
            visited_real_paths.add(real_path)

            # Check directory depth relative to target_path
            try:
                rel_parts = current_root.relative_to(self.target_path).parts
                if len(rel_parts) >= self.max_depth:
                    dirs.clear()  # Do not recurse deeper
                    continue
            except ValueError:
                dirs.clear()
                continue

            # In-place filtering to prune ignored directories
            dirs[:] = [
                d for d in dirs
                if d not in self.ignored_dirs
                and not d.startswith(".")
                and not any(d.endswith(ext) for ext in self.DEFAULT_IGNORED_EXTENSIONS)
            ]

            for file_name in sorted(files):
                if file_name.startswith("."):
                    continue
                file_path = current_root / file_name
                ext = file_path.suffix.lower()
                if ext in self.DEFAULT_IGNORED_EXTENSIONS:
                    continue
                yield file_path

    def _inspect_file(
        self, file_path: Path
    ) -> Tuple[FileInfo, List[SymbolInfo], List[SecurityFinding]]:
        """
        Read file strictly in read-only mode, extract AST data if Python,
        estimate tokens, and scan for secrets.
        """
        try:
            rel_path = str(file_path.relative_to(self.target_path))
        except ValueError:
            rel_path = file_path.name

        ext = file_path.suffix.lower()
        language = self.EXTENSION_LANGUAGE_MAP.get(ext, "Other")
        size_bytes = file_path.stat().st_size

        if self.is_binary_file(file_path) or size_bytes > self.MAX_PARSE_FILE_SIZE_BYTES:
            return (
                FileInfo(
                    relative_path=rel_path,
                    absolute_path=str(file_path),
                    size_bytes=size_bytes,
                    lines_of_code=0,
                    language="Binary" if self.is_binary_file(file_path) else language,
                    token_estimate=0,
                    is_binary=True,
                ),
                [],
                [],
            )

        # Read text file
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            return (
                FileInfo(
                    relative_path=rel_path,
                    absolute_path=str(file_path),
                    size_bytes=size_bytes,
                    lines_of_code=0,
                    language=language,
                    token_estimate=0,
                ),
                [],
                [],
            )

        lines = content.splitlines()
        loc = len(lines)

        # Approximate token footprint: ~4 characters per token
        token_estimate = max(1, len(content) // 4)

        symbols: List[SymbolInfo] = []
        imports: List[ImportInfo] = []

        # Parse AST for Python files
        if language == "Python":
            symbols, imports = self._parse_python_ast(content, rel_path)

        # Security scan for secrets
        findings: List[SecurityFinding] = []
        if self.scan_secrets:
            findings = self._scan_secrets_in_text(lines, rel_path)

        file_info = FileInfo(
            relative_path=rel_path,
            absolute_path=str(file_path),
            size_bytes=size_bytes,
            lines_of_code=loc,
            language=language,
            token_estimate=token_estimate,
            symbols=symbols,
            imports=imports,
        )

        return file_info, symbols, findings

    def _parse_python_ast(
        self, content: str, rel_path: str
    ) -> Tuple[List[SymbolInfo], List[ImportInfo]]:
        """
        Extract classes, functions, and imports safely using Python standard AST.
        """
        symbols: List[SymbolInfo] = []
        imports: List[ImportInfo] = []

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return symbols, imports

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                symbols.append(
                    SymbolInfo(
                        name=node.name,
                        symbol_type="class",
                        line_number=node.lineno,
                        docstring=doc.splitlines()[0] if doc else None,
                        file_path=rel_path,
                    )
                )
                # Inspect methods inside class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m_doc = ast.get_docstring(item)
                        symbols.append(
                            SymbolInfo(
                                name=f"{node.name}.{item.name}",
                                symbol_type="method",
                                line_number=item.lineno,
                                docstring=m_doc.splitlines()[0] if m_doc else None,
                                file_path=rel_path,
                            )
                        )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node)
                symbols.append(
                    SymbolInfo(
                        name=node.name,
                        symbol_type="function",
                        line_number=node.lineno,
                        docstring=doc.splitlines()[0] if doc else None,
                        file_path=rel_path,
                    )
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportInfo(module=alias.name, alias=alias.asname))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        imports.append(
                            ImportInfo(
                                module=node.module,
                                name=alias.name,
                                alias=alias.asname,
                            )
                        )

        return symbols, imports

    def _scan_secrets_in_text(
        self, lines: List[str], rel_path: str
    ) -> List[SecurityFinding]:
        """
        Scan lines for hardcoded credentials and produce masked security findings.
        Never outputs raw unmasked secrets.
        """
        findings: List[SecurityFinding] = []

        for line_no, line in enumerate(lines, start=1):
            # Skip obvious mock / test documentation strings or dummy keys
            lower_line = line.lower()
            if "mock" in lower_line or "placeholder" in lower_line or "test-secret" in lower_line:
                continue

            for rule_id, pattern in self.SECURITY_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    raw_val = match.group(0)
                    # Mask value
                    if len(raw_val) > 8:
                        masked = f"{raw_val[:4]}...[REDACTED]...{raw_val[-4:]}"
                    else:
                        masked = "[REDACTED_SECRET]"

                    findings.append(
                        SecurityFinding(
                            rule_id=rule_id,
                            rule_name=rule_id.replace("_", " ").title(),
                            file_path=rel_path,
                            line_number=line_no,
                            masked_snippet=masked,
                            severity="CRITICAL" if "key" in rule_id or "proj" in rule_id else "HIGH",
                        )
                    )
                    break  # One finding per line is sufficient

        return findings

    def _assess_codebase(self, report: CodebaseAnalysisReport) -> None:
        """
        Derives an architectural summary and LLM context readiness assessment.
        """
        # Architectural style
        has_domain = any("domain" in f.relative_path for f in report.files)
        has_infra = any("infrastructure" in f.relative_path for f in report.files)
        has_app = any("application" in f.relative_path or "cli" in f.relative_path for f in report.files)

        if has_domain and has_infra and has_app:
            report.architecture_assessment = "Clean Architecture (Domain / Application / Infrastructure / CLI separation)"
        elif any("src" in f.relative_path for f in report.files):
            report.architecture_assessment = "Standard src-layout modular package"
        else:
            report.architecture_assessment = "Flat / script layout"

        # Context readiness
        if report.security_findings:
            report.readiness_status = "WARNING: Credential leaks detected"
        elif report.estimated_tokens > 200_000:
            report.readiness_status = "LARGE: Exceeds 200k context; requires file-level targeted slicing"
        elif report.estimated_tokens > 64_000:
            report.readiness_status = "MODERATE: Fits within 128k context window"
        else:
            report.readiness_status = "EXCELLENT: Readily ingestible into standard LLM context"
