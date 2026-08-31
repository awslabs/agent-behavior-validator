# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for conditional constraints (dynamic contracts)."""

from datetime import datetime, timezone

from agent_validator.contracts.base import Contract
from agent_validator.contracts.constraints import (
    must_include_steps,
    must_retrieve_from,
    must_precede,
    must_contain_citations,
    must_not_use_only_parametric_knowledge,
    when,
)
from agent_validator.models import (
    DataSourceRef,
    ExecutionStep,
    NormalizedExecution,
    StepType,
    VerdictStatus,
)
from agent_validator.validator import validate

NOW = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)


def _make_execution(steps, metadata=None, output_text=None):
    return NormalizedExecution(
        execution_id="test",
        trace_source="test",
        started_at=NOW,
        steps=steps,
        metadata=metadata or {},
        output_text=output_text,
    )


def _tool_step(name, sources=None):
    return ExecutionStep(
        step_id=f"step-{name}",
        step_type=StepType.TOOL_CALL,
        name=name,
        started_at=NOW,
        data_sources=[DataSourceRef(source_name=s, source_type="database") for s in (sources or [])],
    )


# --- ConditionalConstraint tests ---


def test_when_condition_met_passes():
    """When condition matches and inner constraint passes, result is PASS."""
    constraint = when({"claim_type": "pharmacy"}, must_include_steps(["lookup_formulary"]))
    execution = _make_execution(
        steps=[_tool_step("lookup_formulary")],
        metadata={"claim_type": "pharmacy"},
    )
    result = constraint.evaluate(execution)
    assert result.passed


def test_when_condition_met_fails():
    """When condition matches but inner constraint fails, result is FAIL."""
    constraint = when({"claim_type": "pharmacy"}, must_include_steps(["lookup_formulary"]))
    execution = _make_execution(
        steps=[_tool_step("some_other_step")],
        metadata={"claim_type": "pharmacy"},
    )
    result = constraint.evaluate(execution)
    assert not result.passed
    assert "lookup_formulary" in result.violation.message


def test_when_condition_not_met_skips():
    """When condition doesn't match, constraint is skipped (passes)."""
    constraint = when({"claim_type": "pharmacy"}, must_include_steps(["lookup_formulary"]))
    execution = _make_execution(
        steps=[_tool_step("verify_dental_benefits")],
        metadata={"claim_type": "dental"},
    )
    result = constraint.evaluate(execution)
    assert result.passed  # skipped, counts as pass


def test_when_with_callable_condition():
    """When condition is a callable, it's evaluated against the execution."""
    constraint = when(
        lambda ex: ex.metadata.get("risk_score", 0) >= 70,
        must_include_steps(["enhanced_review"]),
        description="risk_score >= 70",
    )
    # Low risk — skipped
    low_risk = _make_execution(steps=[], metadata={"risk_score": 30})
    assert constraint.evaluate(low_risk).passed

    # High risk — required
    high_risk = _make_execution(steps=[], metadata={"risk_score": 85})
    assert not constraint.evaluate(high_risk).passed


def test_when_constraint_name_includes_condition():
    """The constraint name should describe the condition and inner constraint."""
    constraint = when({"claim_type": "pharmacy"}, must_include_steps(["lookup_formulary"]))
    assert "claim_type=pharmacy" in constraint.name
    assert "must_include_steps" in constraint.name


# --- Dynamic contract integration tests ---


def test_dynamic_contract_pharmacy():
    """A dynamic contract correctly applies pharmacy-specific constraints."""
    contract = Contract(
        name="claims-dynamic-v1",
        version="1.0.0",
        constraints=[
            # Always required
            must_not_use_only_parametric_knowledge(),
            must_contain_citations(min_count=1),
            # Pharmacy-specific
            when({"claim_type": "pharmacy"}, must_retrieve_from(["formulary-db"])),
            when({"claim_type": "pharmacy"}, must_include_steps(["lookup_formulary"])),
            when({"claim_type": "pharmacy"}, must_precede("lookup_formulary", "render_decision")),
            # Dental-specific
            when({"claim_type": "dental"}, must_retrieve_from(["dental-benefits-db"])),
            when({"claim_type": "dental"}, must_include_steps(["verify_dental_benefits"])),
        ],
    )

    # Pharmacy execution — pharmacy constraints apply, dental ones skip
    pharmacy_exec = _make_execution(
        steps=[
            _tool_step("lookup_formulary", sources=["formulary-db"]),
            _tool_step("render_decision"),
        ],
        metadata={"claim_type": "pharmacy"},
        output_text="Approved per Section 4.2.1",
    )
    verdict = validate(contract, pharmacy_exec)
    assert verdict.status == VerdictStatus.PASS
    assert verdict.checks_passed == 7  # all 7 constraints checked (2 dental skipped = pass)


def test_dynamic_contract_dental():
    """A dynamic contract correctly applies dental-specific constraints."""
    contract = Contract(
        name="claims-dynamic-v1",
        version="1.0.0",
        constraints=[
            must_not_use_only_parametric_knowledge(),
            must_contain_citations(min_count=1),
            when({"claim_type": "pharmacy"}, must_retrieve_from(["formulary-db"])),
            when({"claim_type": "pharmacy"}, must_include_steps(["lookup_formulary"])),
            when({"claim_type": "dental"}, must_retrieve_from(["dental-benefits-db"])),
            when({"claim_type": "dental"}, must_include_steps(["verify_dental_benefits"])),
        ],
    )

    # Dental execution — dental constraints apply, pharmacy ones skip
    dental_exec = _make_execution(
        steps=[
            _tool_step("verify_dental_benefits", sources=["dental-benefits-db"]),
            _tool_step("render_decision"),
        ],
        metadata={"claim_type": "dental"},
        output_text="Approved per Policy D-101",
    )
    verdict = validate(contract, dental_exec)
    assert verdict.status == VerdictStatus.PASS


def test_dynamic_contract_wrong_process_for_type():
    """A dental execution using pharmacy tools fails the dental constraints."""
    contract = Contract(
        name="claims-dynamic-v1",
        version="1.0.0",
        constraints=[
            must_not_use_only_parametric_knowledge(),
            when({"claim_type": "dental"}, must_retrieve_from(["dental-benefits-db"])),
            when({"claim_type": "dental"}, must_include_steps(["verify_dental_benefits"])),
        ],
    )

    # Dental claim but using pharmacy tools — should fail dental constraints
    wrong_exec = _make_execution(
        steps=[
            _tool_step("lookup_formulary", sources=["formulary-db"]),
        ],
        metadata={"claim_type": "dental"},
    )
    verdict = validate(contract, wrong_exec)
    assert verdict.status == VerdictStatus.FAIL
    violation_names = [v.constraint_name for v in verdict.violations]
    assert any("dental-benefits-db" in n for n in violation_names)
    assert any("verify_dental_benefits" in n for n in violation_names)


def test_multiple_metadata_conditions():
    """When condition is a dict with multiple keys, all must match."""
    constraint = when(
        {"claim_type": "pharmacy", "jurisdiction": "EU"},
        must_include_steps(["check_eu_formulary"]),
    )
    # Both match
    eu_pharma = _make_execution(steps=[], metadata={"claim_type": "pharmacy", "jurisdiction": "EU"})
    assert not constraint.evaluate(eu_pharma).passed  # condition met, step missing = fail

    # Only one matches — skipped
    us_pharma = _make_execution(steps=[], metadata={"claim_type": "pharmacy", "jurisdiction": "US"})
    assert constraint.evaluate(us_pharma).passed  # condition not met = skip
