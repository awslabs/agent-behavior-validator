# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for individual constraint implementations."""

from datetime import datetime, timezone

from agent_validator.contracts.constraints import (
    MustEscalateWhen,
    MustIncludeSteps,
    MustNotUseOnlyParametricKnowledge,
    MustPrecede,
    MustRetrieveFrom,
    OutputMustContainCitations,
)
from agent_validator.models import (
    CheckMethod,
    ConstraintType,
    DataSourceRef,
    ExecutionStep,
    NormalizedExecution,
    StepType,
)


# --- MustRetrieveFrom ---


def test_must_retrieve_from_pass(valid_claims_execution):
    c = MustRetrieveFrom(["formulary-db", "coverage-policy"])
    result = c.evaluate(valid_claims_execution)
    assert result.passed is True
    assert result.violation is None


def test_must_retrieve_from_fail(invalid_claims_execution):
    c = MustRetrieveFrom(["formulary-db", "coverage-policy"])
    result = c.evaluate(invalid_claims_execution)
    assert result.passed is False
    assert result.violation is not None
    assert result.violation.constraint_type == ConstraintType.SOURCE
    assert "formulary-db" in result.violation.evidence["missing"]


def test_must_retrieve_from_partial_fail(valid_claims_execution):
    c = MustRetrieveFrom(["formulary-db", "coverage-policy", "audit-log"])
    result = c.evaluate(valid_claims_execution)
    assert result.passed is False
    assert result.violation.evidence["missing"] == ["audit-log"]


# --- MustNotUseOnlyParametricKnowledge ---


def test_must_not_use_parametric_pass(valid_claims_execution):
    c = MustNotUseOnlyParametricKnowledge()
    result = c.evaluate(valid_claims_execution)
    assert result.passed is True


def test_must_not_use_parametric_fail(invalid_claims_execution):
    c = MustNotUseOnlyParametricKnowledge()
    result = c.evaluate(invalid_claims_execution)
    assert result.passed is False
    assert "parametric knowledge" in result.violation.message


# --- MustIncludeSteps ---


def test_must_include_steps_pass(valid_claims_execution):
    c = MustIncludeSteps(["lookup_formulary", "check_coverage"])
    result = c.evaluate(valid_claims_execution)
    assert result.passed is True


def test_must_include_steps_fail(invalid_claims_execution):
    c = MustIncludeSteps(["lookup_formulary", "check_coverage"])
    result = c.evaluate(invalid_claims_execution)
    assert result.passed is False
    assert "lookup_formulary" in result.violation.evidence["missing"]
    assert "check_coverage" in result.violation.evidence["missing"]


# --- MustPrecede ---


def test_must_precede_pass(valid_claims_execution):
    c = MustPrecede("check_coverage", "render_decision")
    result = c.evaluate(valid_claims_execution)
    assert result.passed is True


def test_must_precede_fail():
    now = datetime(2026, 3, 21, tzinfo=timezone.utc)
    execution = NormalizedExecution(
        execution_id="test",
        trace_source="test",
        started_at=now,
        steps=[
            ExecutionStep(
                step_id="1",
                step_type=StepType.TOOL_CALL,
                name="render_decision",
                started_at=now,
            ),
            ExecutionStep(
                step_id="2",
                step_type=StepType.TOOL_CALL,
                name="check_coverage",
                started_at=now,
            ),
        ],
    )
    c = MustPrecede("check_coverage", "render_decision")
    result = c.evaluate(execution)
    assert result.passed is False
    assert "did not precede" in result.violation.message


def test_must_precede_missing_before():
    now = datetime(2026, 3, 21, tzinfo=timezone.utc)
    execution = NormalizedExecution(
        execution_id="test",
        trace_source="test",
        started_at=now,
        steps=[
            ExecutionStep(
                step_id="1",
                step_type=StepType.TOOL_CALL,
                name="render_decision",
                started_at=now,
            ),
        ],
    )
    c = MustPrecede("check_coverage", "render_decision")
    result = c.evaluate(execution)
    assert result.passed is False
    assert "not found" in result.violation.message


def test_must_precede_missing_after_passes():
    """If the 'after' step is missing, ordering can't be violated."""
    now = datetime(2026, 3, 21, tzinfo=timezone.utc)
    execution = NormalizedExecution(
        execution_id="test",
        trace_source="test",
        started_at=now,
        steps=[
            ExecutionStep(
                step_id="1",
                step_type=StepType.TOOL_CALL,
                name="check_coverage",
                started_at=now,
            ),
        ],
    )
    c = MustPrecede("check_coverage", "render_decision")
    result = c.evaluate(execution)
    assert result.passed is True


# --- OutputMustContainCitations ---


def test_output_citations_pass(valid_claims_execution):
    c = OutputMustContainCitations(min_count=1)
    result = c.evaluate(valid_claims_execution)
    assert result.passed is True


def test_output_citations_fail():
    now = datetime(2026, 3, 21, tzinfo=timezone.utc)
    execution = NormalizedExecution(
        execution_id="test",
        trace_source="test",
        started_at=now,
        output_text="The claim is approved. No issues found.",
    )
    c = OutputMustContainCitations(min_count=1)
    result = c.evaluate(execution)
    assert result.passed is False
    assert result.violation.check_method == CheckMethod.HEURISTIC


def test_output_citations_no_output():
    now = datetime(2026, 3, 21, tzinfo=timezone.utc)
    execution = NormalizedExecution(
        execution_id="test",
        trace_source="test",
        started_at=now,
        output_text=None,
    )
    c = OutputMustContainCitations()
    result = c.evaluate(execution)
    assert result.passed is False


def test_output_citations_various_patterns():
    now = datetime(2026, 3, 21, tzinfo=timezone.utc)

    # Policy reference
    execution = NormalizedExecution(
        execution_id="test",
        trace_source="test",
        started_at=now,
        output_text="As per Policy ABC-123, the claim is denied.",
    )
    assert OutputMustContainCitations().evaluate(execution).passed is True

    # Article reference
    execution.output_text = "According to Article 5, this is covered."
    assert OutputMustContainCitations().evaluate(execution).passed is True

    # Bracketed reference
    execution.output_text = "This drug is covered [1] with standard copay [2]."
    assert OutputMustContainCitations(min_count=2).evaluate(execution).passed is True


# --- MustEscalateWhen ---


def test_must_escalate_condition_not_triggered(valid_claims_execution):
    c = MustEscalateWhen(
        condition_fn=lambda e: e.metadata.get("claim_type") == "chiropractic",
        description="unknown claim type",
    )
    result = c.evaluate(valid_claims_execution)
    assert result.passed is True  # condition not triggered, so passes


def test_must_escalate_condition_triggered_no_escalation(escalation_needed_execution):
    c = MustEscalateWhen(
        condition_fn=lambda e: e.metadata.get("claim_type", "").lower()
        not in {"pharmacy", "medical", "dental", "vision"},
        description="unknown claim type",
    )
    result = c.evaluate(escalation_needed_execution)
    assert result.passed is False
    assert "Escalation condition triggered" in result.violation.message


def test_must_escalate_condition_triggered_with_escalation():
    now = datetime(2026, 3, 21, tzinfo=timezone.utc)
    execution = NormalizedExecution(
        execution_id="test",
        trace_source="test",
        started_at=now,
        metadata={"claim_type": "chiropractic"},
        steps=[
            ExecutionStep(
                step_id="1",
                step_type=StepType.TOOL_CALL,
                name="flag_for_human_review",
                started_at=now,
            ),
        ],
    )
    c = MustEscalateWhen(
        condition_fn=lambda e: e.metadata.get("claim_type") == "chiropractic",
        description="unknown claim type",
    )
    result = c.evaluate(execution)
    assert result.passed is True
