"""
Canonical held-out evaluation tasks and benchmark suites for model verification.
"""
from typing import Dict, List, Optional
from brahmastra.domain.evaluation.models import BenchmarkSuite, EvalTask


def get_canonical_benchmark_suites() -> Dict[str, BenchmarkSuite]:
    """Returns the registry of canonical benchmark suites."""

    core_coding_tasks = [
        EvalTask(
            task_id="core-fibonacci",
            name="Fibonacci Sequence Function",
            prompt="Write a Python function named `fibonacci(n)` that returns the nth Fibonacci number (0-indexed, where fib(0)=0, fib(1)=1). Output only the code.",
            expected_patterns=[r"def\s+fibonacci\s*\(", r"return"],
            difficulty="EASY",
            tags=["algorithms", "python"],
        ),
        EvalTask(
            task_id="core-bugfix-palindrome",
            name="Palindrome Check Bug Fix",
            prompt="Fix the bug in this function:\n```python\ndef is_palindrome(s: str) -> bool:\n    return s == s[1:]\n```\nOutput only the corrected Python code.",
            expected_patterns=[r"s\[::-1\]|reversed\(s\)"],
            difficulty="EASY",
            tags=["bugfix", "python"],
        ),
        EvalTask(
            task_id="core-regex-emails",
            name="Extract Email Addresses",
            prompt="Write a Python function `extract_emails(text: str) -> list[str]` using `re` that returns all email addresses from a text string. Output only the code.",
            expected_patterns=[r"def\s+extract_emails\s*\(", r"re\.(findall|finditer)", r"@"],
            difficulty="MEDIUM",
            tags=["regex", "python"],
        ),
        EvalTask(
            task_id="core-security-redact",
            name="API Key Redactor",
            prompt="Write a Python function `mask_key(key: str) -> str` that keeps the first 4 and last 4 characters and replaces the rest with '[REDACTED]'. If key length <= 8, return '[REDACTED]'. Output only the code.",
            expected_patterns=[r"def\s+mask_key\s*\(", r"\[REDACTED\]", r"len\(key\)"],
            difficulty="MEDIUM",
            tags=["security", "python"],
        ),
    ]

    suites = {
        "core": BenchmarkSuite(
            suite_id="core",
            name="Core Developer Benchmark",
            description="Fundamental coding, bug-fixing, regular expressions, and security sanitization tasks.",
            tasks=core_coding_tasks,
        )
    }

    return suites


def get_benchmark_suite(suite_id: str) -> Optional[BenchmarkSuite]:
    """Retrieve benchmark suite by ID."""
    return get_canonical_benchmark_suites().get(suite_id)
