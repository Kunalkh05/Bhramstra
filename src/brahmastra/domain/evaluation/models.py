"""
Domain models for benchmark suites, held-out evaluation tasks, and scoring reports.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class EvalTask:
    """A held-out evaluation task with verification criteria."""
    __test__ = False
    task_id: str
    name: str
    prompt: str
    expected_patterns: List[str]
    verification_code: Optional[str] = None
    difficulty: str = "MEDIUM"  # "EASY", "MEDIUM", "HARD"
    tags: List[str] = field(default_factory=list)


@dataclass
class TaskEvalResult:
    """Individual task evaluation result."""
    __test__ = False
    task_id: str
    model_id: str
    passed: bool
    response_text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cost_micro_usd: int = 0
    error_message: Optional[str] = None


@dataclass
class BenchmarkSuite:
    """A collection of canonical evaluation tasks."""
    __test__ = False
    suite_id: str
    name: str
    description: str
    tasks: List[EvalTask] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    """Aggregated scoring report across an evaluation benchmark."""
    __test__ = False
    suite_id: str
    model_id: str
    total_tasks: int
    passed_tasks: int
    pass_rate: float
    total_tokens: int
    total_cost_micro_usd: int
    avg_latency_ms: float
    task_results: List[TaskEvalResult] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
