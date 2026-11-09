"""
Evaluation engine for running benchmark tasks, pattern matching, and metric aggregation.
"""
import re
import time
from typing import List, Optional

from brahmastra.domain.evaluation.models import (
    BenchmarkReport,
    BenchmarkSuite,
    EvalTask,
    TaskEvalResult,
)
from brahmastra.domain.providers.interface import ProviderInterface
from brahmastra.domain.providers.models import ChatMessage, GenerationRequest


class EvaluationEngine:
    """Executes benchmark tasks against model providers and scores results."""

    @classmethod
    def evaluate_task(
        cls,
        task: EvalTask,
        model_id: str,
        adapter: ProviderInterface,
        api_key: Optional[str] = None,
    ) -> TaskEvalResult:
        """
        Executes a single evaluation task and verifies expected patterns.
        """
        request = GenerationRequest(
            model=model_id,
            messages=[
                ChatMessage(
                    role="system",
                    content="You are an expert Python coding assistant. Output concise, correct Python code without conversational filler.",
                ),
                ChatMessage(role="user", content=task.prompt),
            ],
            temperature=0.0,  # Zero temperature for deterministic evaluation
        )

        start_time = time.perf_counter()
        try:
            response = adapter.generate(request=request, api_key=api_key)
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            output_text = response.content

            # Verify all expected patterns match
            all_patterns_matched = True
            for pattern_str in task.expected_patterns:
                if not re.search(pattern_str, output_text, re.MULTILINE):
                    all_patterns_matched = False
                    break

            # Calculate cost approximation in micro-USD (default 1 micro-USD per token if not priced)
            total_tokens = response.usage.total_tokens or (response.usage.prompt_tokens + response.usage.completion_tokens)
            cost_micro_usd = total_tokens * 1  # 1 micro-dollar per token baseline

            return TaskEvalResult(
                task_id=task.task_id,
                model_id=model_id,
                passed=all_patterns_matched,
                response_text=output_text,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                latency_ms=latency_ms,
                cost_micro_usd=cost_micro_usd,
            )

        except Exception as ex:
            return TaskEvalResult(
                task_id=task.task_id,
                model_id=model_id,
                passed=False,
                response_text="",
                error_message=str(ex),
            )

    @classmethod
    def run_suite(
        cls,
        suite: BenchmarkSuite,
        model_id: str,
        adapter: ProviderInterface,
        api_key: Optional[str] = None,
    ) -> BenchmarkReport:
        """
        Executes all tasks in a benchmark suite and aggregates scoring telemetry.
        """
        results: List[TaskEvalResult] = []
        total_tokens = 0
        total_cost = 0
        total_latency = 0.0
        passed_count = 0

        for task in suite.tasks:
            res = cls.evaluate_task(
                task=task,
                model_id=model_id,
                adapter=adapter,
                api_key=api_key,
            )
            results.append(res)
            if res.passed:
                passed_count += 1
            total_tokens += res.prompt_tokens + res.completion_tokens
            total_cost += res.cost_micro_usd
            total_latency += res.latency_ms

        total_tasks = len(suite.tasks)
        pass_rate = round((passed_count / total_tasks * 100), 1) if total_tasks > 0 else 0.0
        avg_latency = round(total_latency / total_tasks, 2) if total_tasks > 0 else 0.0

        return BenchmarkReport(
            suite_id=suite.suite_id,
            model_id=model_id,
            total_tasks=total_tasks,
            passed_tasks=passed_count,
            pass_rate=pass_rate,
            total_tokens=total_tokens,
            total_cost_micro_usd=total_cost,
            avg_latency_ms=avg_latency,
            task_results=results,
        )
