from __future__ import annotations

from app.harness.postprocess import ResponsePostProcessor
from app.harness.research import ResearchPolicy, ResearchResult, ResearchSource
from app.harness.tool_selection import ToolSelectionPolicy
from app.harness.tuning import HarnessTuner


def test_research_policy_keywords() -> None:
    policy = ResearchPolicy()
    plan = policy.plan("latest AI model release", {"mode": "knowing", "intent": "plan"})
    assert plan.enabled is True


def test_research_policy_disabled() -> None:
    policy = ResearchPolicy()
    plan = policy.plan("anything", {"mode": "knowing", "intent": "plan"}, requested=False)
    assert plan.enabled is False


def test_tool_selection_disables_lint_for_knowing() -> None:
    policy = ToolSelectionPolicy()
    decision = policy.select(
        "tell me about granite models",
        {"mode": "knowing", "requires_tools": []},
        available=["greptile", "lint", "jj"],
        defaults=["greptile", "lint", "jj"],
    )
    assert "lint" in decision.excluded_tools


def test_postprocess_adds_citations() -> None:
    research = ResearchResult(
        query="q",
        used=True,
        sources=[ResearchSource(title="Example", url="https://example.com")],
    )
    post = ResponsePostProcessor().apply("Answer without citations", research, enforce_citations=True)
    assert post.citations_added is True
    assert "Sources:" in post.response


def test_tuning_suggests_actions() -> None:
    tuner = HarnessTuner()
    summary = tuner.suggest(
        grade={"correctness": 4, "completeness": 4},
        tool_results=[{"name": "lint", "status": "error", "stderr": "command not found"}],
        scope={"mode": "knowing"},
    )
    kinds = {action.kind for action in summary.actions}
    assert "enable_research" in kinds
    assert "increase_iterations" in kinds
    assert "disable_tool" in kinds
