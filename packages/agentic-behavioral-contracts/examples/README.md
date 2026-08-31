# Examples

Three complete scenarios demonstrating behavioral validation in regulated environments.
Each has its own contract, sample traces (valid + invalid), tools, and README.

No AWS credentials or external services needed — all examples run against pre-captured
OTEL trace files.

## Using the CLI (recommended)

```bash
cd ideation/idea_6_agent_behavioral_validation

# List available built-in contracts
PYTHONPATH=src agent-validate list-contracts

# Validate traces against a contract
PYTHONPATH=src agent-validate run \
  --contract claims-processing-v1 \
  --traces "examples/sample_traces/*claim*.json" \
  --source-map examples/source_maps/claims.json \
  --metadata claim_type=pharmacy \
  --quiet
```

If `agent-validate` isn't on your path, use `python -m agent_validator.cli` instead:

```bash
PYTHONPATH=src python -m agent_validator.cli run \
  --contract claims-processing-v1 \
  --traces examples/sample_traces/valid_claim.json \
  --source-map examples/source_maps/claims.json
```

The per-scenario `run.py` scripts also still work:

```bash
python -m examples.claims_agent.run --traces examples/sample_traces/valid_claim.json
```

---

## 1. Claims Processing Agent (HCLS)

An insurance claims agent that must look up the formulary, check coverage, and cite
policy sections before rendering a decision.

```bash
# Valid: full process, lisinopril approved with citation — PASS (6/6)
agent-validate run --contract claims-processing-v1 \
  --traces examples/sample_traces/valid_claim.json \
  --source-map examples/source_maps/claims.json --metadata claim_type=pharmacy

# Invalid: skips all tools, approves ozempic from training data — FAIL (1/6)
agent-validate run --contract claims-processing-v1 \
  --traces examples/sample_traces/invalid_claim.json \
  --source-map examples/source_maps/claims.json --metadata claim_type=pharmacy

# Batch: validate all claims traces at once
agent-validate run --contract claims-processing-v1 \
  --traces "examples/sample_traces/*claim*.json" \
  --source-map examples/source_maps/claims.json --metadata claim_type=pharmacy --quiet
```

**What the invalid trace catches:** The agent approves a claim saying "Ozempic is a
commonly prescribed GLP-1 receptor agonist that is generally covered" — without
checking the formulary, verifying coverage, or citing any policy. Sounds plausible.
Completely ungrounded.

See [claims_agent/README.md](claims_agent/README.md) for details.

---

## 2. KYC/AML Screening Agent (FinTech)

A KYC/AML agent that must screen against sanctions lists, verify jurisdiction rules,
assess risk, and escalate high-risk customers for human review.

```bash
# Valid: full process, low-risk US customer cleared — PASS (7/7)
agent-validate run --contract kyc-aml-screening-v1 \
  --traces examples/sample_traces/kyc_valid.json \
  --source-map examples/source_maps/kyc_aml.json

# Invalid: skips all tools, auto-clears high-risk EU customer — FAIL (0/7)
agent-validate run --contract kyc-aml-screening-v1 \
  --traces examples/sample_traces/kyc_invalid.json \
  --source-map examples/source_maps/kyc_aml.json --metadata risk_score=85

# Batch: validate all KYC traces
agent-validate run --contract kyc-aml-screening-v1 \
  --traces "examples/sample_traces/kyc_*.json" \
  --source-map examples/source_maps/kyc_aml.json --quiet
```

**What the invalid trace catches:** The agent clears a high-risk customer in EU
jurisdiction saying "Based on standard EU AML procedures, this customer has been
reviewed and cleared" — without checking sanctions lists, applying EU-specific
regulations (AMLD6), or escalating despite a risk score of 85. Every constraint fails.

See [kyc_aml_agent/README.md](kyc_aml_agent/README.md) for details.

---

## 3. Clinical Decision Support Agent (HCLS)

A clinical advisor that must check drug interactions, look up guidelines, verify
dosing, and escalate dangerous interactions for clinician review.

```bash
# Valid: safe co-prescription, metformin + lisinopril with guidelines — PASS (7/7)
agent-validate run --contract clinical-decision-support-v1 \
  --traces examples/sample_traces/clinical_valid.json \
  --source-map examples/source_maps/clinical.json

# Invalid: recommends warfarin + aspirin without checking interactions — FAIL (1/7)
agent-validate run --contract clinical-decision-support-v1 \
  --traces examples/sample_traces/clinical_invalid.json \
  --source-map examples/source_maps/clinical.json

# Batch: validate all clinical traces
agent-validate run --contract clinical-decision-support-v1 \
  --traces "examples/sample_traces/clinical_*.json" \
  --source-map examples/source_maps/clinical.json --quiet
```

**What the invalid trace catches:** The agent recommends adding aspirin to warfarin
saying "Aspirin is a well-established anti-inflammatory that is commonly used
alongside anticoagulants" — without checking the drug interaction database, which
would have flagged a major bleeding risk (DrugBank DB00682-DB00945). This is a
**patient safety failure** caught by behavioral validation.

See [clinical_decision_agent/README.md](clinical_decision_agent/README.md) for details.

---

## Pattern Across All Three

Each invalid trace shows the same fundamental failure mode:

| Scenario | What the agent says | What actually happened |
|---|---|---|
| Claims | "Ozempic is generally covered by most plans" | Never checked the formulary |
| KYC/AML | "This customer has been reviewed and cleared" | Never screened sanctions lists |
| Clinical | "Aspirin is commonly used alongside anticoagulants" | Never checked drug interactions |

In every case:
- The agent sounds confident and plausible
- A human reviewer might not catch the problem
- The behavioral contract catches it mechanically, every time
- The audit record documents exactly what went wrong with evidence

---

## Discovery and Dry Run

Before writing a contract, inspect your traces to see what step names, data sources,
and structure the adapter produces:

```bash
# See what's in a trace
agent-validate discover --traces examples/sample_traces/valid_claim.json \
  --source-map examples/source_maps/claims.json

# Test a contract against a trace — detailed constraint-by-constraint output
agent-validate dry-run --contract claims-processing-v1 \
  --traces examples/sample_traces/valid_claim.json \
  --source-map examples/source_maps/claims.json --metadata claim_type=pharmacy
```

Or from Python:

```python
from agent_validator import describe_execution, dry_run
print(describe_execution(execution))
print(dry_run(contract, execution))
```

---

## Output Formats

All examples produce two outputs:

**Human-readable report** — for terminal review:
```
======================================================================
  AUDIT RECORD: a1b2c3d4-...
  Timestamp:    2026-03-23T14:12:46+00:00
  Contract:     claims-processing-v1 v1.0.0
  Verdict:      PASS
  Checks:       6/6 passed
======================================================================
```

**JSON audit record** — for storage, compliance systems, or further processing:
```json
{
  "audit_id": "a1b2c3d4-...",
  "timestamp": "2026-03-23T14:12:46+00:00",
  "contract_version": "1.0.0",
  "verdict": { "status": "pass", "violations": [] },
  "execution_summary": { "tool_calls": [...], "data_sources_consulted": [...] },
  "evidence_package": []
}
```

---

## Running Tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

---

## File Structure

```
examples/
├── README.md                          <- you are here
├── source_maps/                       <- JSON tool-to-source maps for the CLI
│   ├── claims.json
│   ├── kyc_aml.json
│   └── clinical.json
├── claims_agent/                      <- HCLS: pharmacy claims processing
│   ├── README.md
│   ├── agent.py                       <- Strands agent (requires AWS for live mode)
│   ├── run.py                         <- Per-scenario script (alternative to CLI)
│   └── tools.py                       <- Simulated formulary/coverage tools
├── kyc_aml_agent/                     <- FinTech: KYC/AML screening
│   ├── README.md
│   ├── run.py                         <- Per-scenario script (alternative to CLI)
│   └── tools.py                       <- Simulated sanctions/jurisdiction/risk tools
├── clinical_decision_agent/           <- HCLS: clinical decision support
│   ├── README.md
│   ├── run.py                         <- Per-scenario script (alternative to CLI)
│   └── tools.py                       <- Simulated drug interaction/guidelines tools
└── sample_traces/
    ├── valid_claim.json               <- Claims: agent follows all steps
    ├── invalid_claim.json             <- Claims: agent skips tools
    ├── kyc_valid.json                 <- KYC: full screening, low-risk customer
    ├── kyc_invalid.json               <- KYC: agent skips tools, auto-clears high-risk
    ├── clinical_valid.json            <- Clinical: safe co-prescription with guidelines
    └── clinical_invalid.json          <- Clinical: dangerous interaction not checked
```
