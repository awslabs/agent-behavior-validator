# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end demo: validate clinical decision support agent behavior.

Usage:
    # Safe co-prescription, full process — PASS
    python -m examples.clinical_decision_agent.run --traces examples/sample_traces/clinical_valid.json

    # Dangerous interaction, agent skips checks — FAIL
    python -m examples.clinical_decision_agent.run --traces examples/sample_traces/clinical_invalid.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from agent_validator.adapters.otel import OTELAdapter
from agent_validator.audit import create_audit_record, render_audit_report
from agent_validator.contracts.templates.clinical_decision import clinical_decision_contract
from agent_validator.validator import validate

TOOL_SOURCE_MAP = {
    "check_drug_interactions": {"source_name": "drug-interaction-db", "source_type": "database"},
    "lookup_clinical_guidelines": {"source_name": "clinical-guidelines", "source_type": "database"},
    "check_dosing_range": {"source_name": "dosing-reference", "source_type": "database"},
}


def run_with_traces(trace_path: str) -> None:
    """Load pre-captured OTEL traces and validate against the clinical contract."""
    with open(trace_path) as f:
        raw_trace = json.load(f)

    adapter = OTELAdapter(tool_source_map=TOOL_SOURCE_MAP)
    execution = adapter.normalize(raw_trace)

    verdict = validate(clinical_decision_contract, execution)
    record = create_audit_record(verdict, execution, clinical_decision_contract.version)

    print(render_audit_report(record))
    print()
    print("--- JSON Audit Record ---")
    print(json.dumps(record.to_dict(), indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate clinical decision support agent behavior"
    )
    parser.add_argument("--traces", type=str, required=True, help="Path to OTEL trace JSON file")
    args = parser.parse_args()
    run_with_traces(args.traces)


if __name__ == "__main__":
    main()
