# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for compliance tracking and drift detection."""

from agent_validator.compliance import CompliancePolicy, ComplianceTracker, DriftAlert
from agent_validator.models import ConstraintType, CheckMethod, Verdict, VerdictStatus, Violation


def _pass_verdict(contract="test-contract", exec_id="exec-001"):
    return Verdict(
        status=VerdictStatus.PASS,
        contract_name=contract,
        execution_id=exec_id,
        violations=[],
        checks_performed=6,
        checks_passed=6,
    )


def _fail_verdict(constraint_name="must_include_steps(['lookup'])", contract="test-contract", exec_id="exec-002"):
    return Verdict(
        status=VerdictStatus.FAIL,
        contract_name=contract,
        execution_id=exec_id,
        violations=[
            Violation(
                constraint_name=constraint_name,
                constraint_type=ConstraintType.STEP,
                check_method=CheckMethod.DETERMINISTIC,
                message="Step missing",
                severity="error",
            )
        ],
        checks_performed=6,
        checks_passed=5,
    )


# --- Basic tracking ---


def test_empty_tracker():
    tracker = ComplianceTracker()
    assert tracker.overall_compliance == 1.0
    assert tracker.summary()["window_size"] == 0


def test_all_pass():
    tracker = ComplianceTracker()
    for i in range(20):
        tracker.record(_pass_verdict(exec_id=f"exec-{i}"))
    assert tracker.overall_compliance == 1.0
    assert tracker.summary()["threshold_met"] is True


def test_mixed_results():
    tracker = ComplianceTracker(policy=CompliancePolicy(min_window_size=5))
    for i in range(8):
        tracker.record(_pass_verdict(exec_id=f"exec-{i}"))
    for i in range(2):
        tracker.record(_fail_verdict(exec_id=f"exec-fail-{i}"))
    assert tracker.overall_compliance == 0.8  # 8/10


# --- Drift detection ---


def test_no_alert_below_min_window():
    """Don't alert if we haven't seen min_window_size executions yet."""
    tracker = ComplianceTracker(policy=CompliancePolicy(min_window_size=10))
    # 5 failures out of 5 — terrible rate but below min window
    alerts = []
    for i in range(5):
        alerts.extend(tracker.record(_fail_verdict(exec_id=f"exec-{i}")))
    assert len(alerts) == 0  # Not enough data


def test_alert_on_overall_drift():
    """Alert when overall compliance drops below threshold."""
    collected_alerts = []
    tracker = ComplianceTracker(
        policy=CompliancePolicy(overall_threshold=0.90, min_window_size=10),
        on_alert=lambda a: collected_alerts.append(a),
    )
    # 8 pass, 2 fail = 80% (below 90% threshold)
    for i in range(8):
        tracker.record(_pass_verdict(exec_id=f"exec-{i}"))
    for i in range(2):
        alerts = tracker.record(_fail_verdict(exec_id=f"exec-fail-{i}"))

    # Should have an overall alert
    overall_alerts = [a for a in collected_alerts if a.alert_type == "overall"]
    assert len(overall_alerts) >= 1
    assert overall_alerts[0].current_rate == 0.8
    assert overall_alerts[0].threshold == 0.90


def test_no_alert_when_above_threshold():
    """No alert when compliance is above threshold."""
    collected_alerts = []
    tracker = ComplianceTracker(
        policy=CompliancePolicy(overall_threshold=0.90, min_window_size=10),
        on_alert=lambda a: collected_alerts.append(a),
    )
    # 19 pass, 1 fail = 95% (above 90%)
    for i in range(19):
        tracker.record(_pass_verdict(exec_id=f"exec-{i}"))
    tracker.record(_fail_verdict(exec_id="exec-fail"))

    overall_alerts = [a for a in collected_alerts if a.alert_type == "overall"]
    assert len(overall_alerts) == 0


def test_alert_on_constraint_drift():
    """Alert when a specific constraint's compliance drops below its threshold."""
    collected_alerts = []
    tracker = ComplianceTracker(
        policy=CompliancePolicy(
            overall_threshold=0.50,  # low overall so we only get constraint alerts
            min_window_size=3,  # low min so per-constraint threshold is checked
            constraint_thresholds={"must_include_steps(['lookup'])": 0.95},
        ),
        on_alert=lambda a: collected_alerts.append(a),
    )
    # 8 pass, 4 fail on the same constraint
    # Per-constraint: 4 checked (only failures are tracked by name), 0% pass rate
    for i in range(8):
        tracker.record(_pass_verdict(exec_id=f"exec-{i}"))
    for i in range(4):
        tracker.record(_fail_verdict(
            constraint_name="must_include_steps(['lookup'])",
            exec_id=f"exec-fail-{i}",
        ))

    constraint_alerts = [a for a in collected_alerts if a.alert_type == "constraint"]
    assert len(constraint_alerts) >= 1
    assert constraint_alerts[0].constraint_name == "must_include_steps(['lookup'])"


# --- Sliding window ---


def test_sliding_window():
    """Old failures drop out of the window, compliance recovers."""
    tracker = ComplianceTracker(
        policy=CompliancePolicy(overall_threshold=0.90, min_window_size=5),
        window_size=10,
    )
    # Fill window with 5 failures
    for i in range(5):
        tracker.record(_fail_verdict(exec_id=f"fail-{i}"))
    # Then 5 passes
    for i in range(5):
        tracker.record(_pass_verdict(exec_id=f"pass-{i}"))
    assert tracker.overall_compliance == 0.5  # 5/10

    # Add 5 more passes — the 5 failures slide out of the window
    for i in range(5):
        tracker.record(_pass_verdict(exec_id=f"pass2-{i}"))
    assert tracker.overall_compliance == 1.0  # all 10 in window are passes


# --- Summary ---


def test_summary_structure():
    tracker = ComplianceTracker(policy=CompliancePolicy(min_window_size=5))
    for i in range(8):
        tracker.record(_pass_verdict(exec_id=f"exec-{i}"))
    tracker.record(_fail_verdict(constraint_name="step_check", exec_id="fail-1"))
    tracker.record(_fail_verdict(constraint_name="source_check", exec_id="fail-2"))

    summary = tracker.summary()
    assert summary["window_size"] == 10
    assert summary["total_recorded"] == 10
    assert "step_check" in summary["per_constraint"]
    assert "source_check" in summary["per_constraint"]


# --- DriftAlert ---


def test_drift_alert_to_dict():
    from datetime import datetime, timezone
    alert = DriftAlert(
        timestamp=datetime(2026, 3, 25, tzinfo=timezone.utc),
        alert_type="overall",
        constraint_name=None,
        current_rate=0.85,
        threshold=0.95,
        window_size=100,
        message="test",
    )
    d = alert.to_dict()
    assert d["current_rate"] == "85.0%"
    assert d["threshold"] == "95.0%"
    assert d["alert_type"] == "overall"
