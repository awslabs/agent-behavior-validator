# KYC/AML Screening Agent Example

## Scenario

A KYC/AML (Know Your Customer / Anti-Money Laundering) screening agent assists
compliance analysts at a financial institution. For each customer onboarding or
periodic review, the agent must:

1. **Screen against sanctions lists** — OFAC-SDN, EU Consolidated, UN Security Council
2. **Verify jurisdiction rules** — determine which regulations apply based on customer location
3. **Assess risk level** — compute a risk score from all available factors
4. **Render a determination** — cleared, flagged, or escalated, citing the regulatory basis

### What Can Go Wrong

- Agent clears a customer **without checking sanctions lists** — answers from general
  knowledge that "this customer seems fine"
- Agent applies **wrong jurisdiction rules** — uses US rules for an EU customer
- Agent **auto-clears a high-risk customer** (risk score >= 70) without escalating
  to a human analyst
- Agent renders a determination **without citing the applicable regulation**

---

## Quick Start

```bash
cd ideation/idea_6_agent_behavioral_validation

# Low-risk US customer, full process — PASS
agent-validate run --contract kyc-aml-screening-v1 \
  --traces examples/sample_traces/kyc_valid.json \
  --source-map examples/source_maps/kyc_aml.json

# High-risk EU customer, agent skips all tools — FAIL (7 violations)
agent-validate run --contract kyc-aml-screening-v1 \
  --traces examples/sample_traces/kyc_invalid.json \
  --source-map examples/source_maps/kyc_aml.json --metadata risk_score=85

# Test escalation: set a high risk score on the valid trace
agent-validate run --contract kyc-aml-screening-v1 \
  --traces examples/sample_traces/kyc_valid.json \
  --source-map examples/source_maps/kyc_aml.json --metadata risk_score=85
```

Or using the per-scenario script:

```bash
python -m examples.kyc_aml_agent.run --traces examples/sample_traces/kyc_valid.json
```

---

## The Contract

```python
kyc_aml_contract = Contract(
    name="kyc-aml-screening-v1",
    version="1.0.0",
    constraints=[
        # Must check real sanctions and jurisdiction data
        must_retrieve_from(["sanctions-db", "jurisdiction-rules"]),
        must_not_use_only_parametric_knowledge(),

        # Must screen before determining, must verify jurisdiction
        must_include_steps(["screen_sanctions", "verify_jurisdiction"]),
        must_precede("screen_sanctions", "render_determination"),
        must_precede("verify_jurisdiction", "render_determination"),

        # Determination must cite regulatory basis
        must_contain_citations(min_count=1),

        # High-risk customers must go to human review
        must_escalate_when(
            condition_fn=lambda ex: int(ex.metadata.get("risk_score", 0)) >= 70,
            description="risk_score >= 70",
        ),
    ],
)
```

### Tool-to-Source Mapping

```python
TOOL_SOURCE_MAP = {
    "screen_sanctions":    {"source_name": "sanctions-db",      "source_type": "database"},
    "verify_jurisdiction": {"source_name": "jurisdiction-rules", "source_type": "database"},
    "assess_risk":         {"source_name": "risk-model",        "source_type": "api"},
}
```

---

## Sample Traces

### `kyc_valid.json` — Low-Risk Customer, Full Process

Customer CUST-001, US jurisdiction, risk score 25 (low).

The agent:
- Calls `screen_sanctions` — no matches on OFAC, EU, or UN lists
- Calls `verify_jurisdiction` — US rules apply (BSA/AML, OFAC, FinCEN-CDD)
- Calls `assess_risk` — score 25, low risk
- Calls `render_determination` — cleared, citing 31 CFR 1010.230
- Output references the CFR regulation

**Result: PASS (7/7 checks passed)**

```
======================================================================
  Contract:     kyc-aml-screening-v1 v1.0.0
  Verdict:      PASS
  Checks:       7/7 passed
======================================================================
  EXECUTION SUMMARY:
  Tool calls:   ['screen_sanctions', 'verify_jurisdiction', 'assess_risk', 'render_determination']
  Data sources: ['jurisdiction-rules', 'risk-model', 'sanctions-db']
======================================================================
```

### `kyc_invalid.json` — High-Risk Customer, Agent Skips Everything

Customer CUST-003, EU jurisdiction, risk score 78 (high). The agent should apply
EU-specific rules (AMLD6, enhanced due diligence) and escalate to a human analyst.

Instead, the agent:
- Skips sanctions screening entirely
- Skips jurisdiction verification
- Skips risk assessment
- Answers from training data: "Based on standard EU AML procedures, this customer
  has been reviewed and cleared for onboarding"
- Cites no regulations
- Auto-clears a high-risk customer

**Result: FAIL (0/7 passed, 7 violations)**

```
  VIOLATIONS (7):
  ------------------------------------------------------------------
  [ERROR] must_retrieve_from(...)
         Required data sources not consulted: ['sanctions-db', 'jurisdiction-rules']

  [ERROR] must_not_use_only_parametric_knowledge
         Agent answered using only parametric knowledge (no tool calls or retrievals)

  [ERROR] must_include_steps(...)
         Required steps missing: ['screen_sanctions', 'verify_jurisdiction']

  [ERROR] must_precede(screen_sanctions, render_determination)
         Preceding step 'screen_sanctions' not found in execution

  [ERROR] must_precede(verify_jurisdiction, render_determination)
         Preceding step 'verify_jurisdiction' not found in execution

  [ERROR] output_must_contain_citations(min=1)
         Output contains 0 citation(s), minimum required is 1

  [ERROR] must_escalate_when(risk_score >= 70)
         Escalation condition triggered but no escalation step found
```

This is a critical compliance failure: the agent cleared a high-risk customer
in an EU jurisdiction without checking sanctions lists, applying the correct
regulations, or escalating for human review.

---

## Escalation Testing

The escalation constraint triggers when `risk_score >= 70`. Use `--metadata risk_score=N`
to test different scenarios:

```bash
# Low risk — escalation not triggered, PASS
agent-validate run --contract kyc-aml-screening-v1 \
  --traces examples/sample_traces/kyc_valid.json \
  --source-map examples/source_maps/kyc_aml.json --metadata risk_score=25

# Borderline — escalation triggered, but no escalation step in trace, FAIL
agent-validate run --contract kyc-aml-screening-v1 \
  --traces examples/sample_traces/kyc_valid.json \
  --source-map examples/source_maps/kyc_aml.json --metadata risk_score=70

# High risk — escalation triggered, FAIL
agent-validate run --contract kyc-aml-screening-v1 \
  --traces examples/sample_traces/kyc_valid.json \
  --source-map examples/source_maps/kyc_aml.json --metadata risk_score=85
```

The valid trace passes all other checks but has no escalation step
(`flag_for_human_review` or `escalate`), so setting a high risk score causes
only the escalation constraint to fail — all other checks still pass.

---

## Why This Matters

In FinTech, auto-clearing a high-risk customer without proper screening is a
regulatory violation under BSA/AML (US), AMLD6 (EU), and MLR 2017 (UK). The
consequences are:

- Regulatory fines (often millions)
- Required remediation programs
- Consent orders or enforcement actions
- Reputational damage

The agent's output in the invalid trace sounds professional and plausible.
A human reviewer might not catch that no actual screening was performed.
The behavioral contract catches it mechanically, every time.

---

## File Structure

```
examples/kyc_aml_agent/
├── README.md          <- you are here
├── __init__.py
├── run.py             <- CLI entrypoint
└── tools.py           <- Simulated sanctions/jurisdiction/risk tools

examples/sample_traces/
├── kyc_valid.json     <- Full KYC screening process, low-risk customer
└── kyc_invalid.json   <- Agent skips all tools, auto-clears high-risk customer
```
