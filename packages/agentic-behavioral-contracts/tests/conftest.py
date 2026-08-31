# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Shared test fixtures."""

from datetime import datetime, timezone

import pytest

from agent_validator.models import (
    DataSourceRef,
    ExecutionStep,
    NormalizedExecution,
    StepType,
)


@pytest.fixture
def valid_claims_execution() -> NormalizedExecution:
    """A valid claims processing execution: formulary lookup → coverage check → decision."""
    now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
    return NormalizedExecution(
        execution_id="test-valid-001",
        trace_source="test",
        started_at=now,
        ended_at=datetime(2026, 3, 21, 12, 0, 5, tzinfo=timezone.utc),
        input_text="Process pharmacy claim for member MEM-001, drug lisinopril",
        output_text=(
            "Claim APPROVED. Lisinopril is covered at Tier 1 per Section 4.2.1. "
            "No prior authorization required. Copay: $10.00."
        ),
        metadata={"claim_type": "pharmacy"},
        steps=[
            ExecutionStep(
                step_id="step-model-1",
                step_type=StepType.MODEL_CALL,
                name="chat",
                started_at=now,
                status="success",
            ),
            ExecutionStep(
                step_id="step-tool-1",
                step_type=StepType.TOOL_CALL,
                name="lookup_formulary",
                started_at=now,
                status="success",
                inputs={"drug_name": "lisinopril"},
                outputs={
                    "status": "covered",
                    "tier": 1,
                    "policy_section": "Section 4.2.1",
                },
                data_sources=[
                    DataSourceRef(
                        source_name="formulary-db",
                        source_type="database",
                    )
                ],
            ),
            ExecutionStep(
                step_id="step-tool-2",
                step_type=StepType.TOOL_CALL,
                name="check_coverage",
                started_at=now,
                status="success",
                inputs={"member_id": "MEM-001", "drug_name": "lisinopril"},
                outputs={
                    "coverage_active": True,
                    "plan_type": "PPO",
                    "copay_amount": 10.00,
                },
                data_sources=[
                    DataSourceRef(
                        source_name="coverage-policy",
                        source_type="api",
                    )
                ],
            ),
            ExecutionStep(
                step_id="step-tool-3",
                step_type=StepType.TOOL_CALL,
                name="render_decision",
                started_at=now,
                status="success",
                inputs={"decision": "approved"},
                outputs={"decision": "approved", "citations": ["Section 4.2.1"]},
            ),
            ExecutionStep(
                step_id="step-model-2",
                step_type=StepType.MODEL_CALL,
                name="chat",
                started_at=now,
                status="success",
            ),
        ],
    )


@pytest.fixture
def invalid_claims_execution() -> NormalizedExecution:
    """Invalid: agent skips tools and answers from parametric knowledge only."""
    now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
    return NormalizedExecution(
        execution_id="test-invalid-001",
        trace_source="test",
        started_at=now,
        ended_at=datetime(2026, 3, 21, 12, 0, 3, tzinfo=timezone.utc),
        input_text="Process pharmacy claim for member MEM-002, drug ozempic",
        output_text=(
            "The claim for ozempic is APPROVED. Ozempic is a commonly prescribed "
            "GLP-1 receptor agonist that is generally covered by most plans."
        ),
        metadata={"claim_type": "pharmacy"},
        steps=[
            ExecutionStep(
                step_id="step-model-1",
                step_type=StepType.MODEL_CALL,
                name="chat",
                started_at=now,
                status="success",
            ),
        ],
    )


@pytest.fixture
def escalation_needed_execution() -> NormalizedExecution:
    """Execution where claim type is unknown but agent doesn't escalate."""
    now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
    return NormalizedExecution(
        execution_id="test-escalation-001",
        trace_source="test",
        started_at=now,
        input_text="Process chiropractic claim for member MEM-001",
        output_text="Claim approved for chiropractic services.",
        metadata={"claim_type": "chiropractic"},
        steps=[
            ExecutionStep(
                step_id="step-tool-1",
                step_type=StepType.TOOL_CALL,
                name="lookup_formulary",
                started_at=now,
                status="success",
                data_sources=[
                    DataSourceRef(source_name="formulary-db", source_type="database")
                ],
            ),
            ExecutionStep(
                step_id="step-tool-2",
                step_type=StepType.TOOL_CALL,
                name="check_coverage",
                started_at=now,
                status="success",
                data_sources=[
                    DataSourceRef(source_name="coverage-policy", source_type="api")
                ],
            ),
            ExecutionStep(
                step_id="step-tool-3",
                step_type=StepType.TOOL_CALL,
                name="render_decision",
                started_at=now,
                status="success",
            ),
        ],
    )
