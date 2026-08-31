# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Simulated tools for the KYC/AML screening reference agent.

These tools use embedded lookup data to simulate sanctions databases,
jurisdiction rules, and risk scoring. In production, these would call
real services (OFAC API, EU sanctions list, jurisdiction rule engine, etc.).
"""

SANCTIONS_DB = {
    "CUST-001": {
        "match": False,
        "lists_checked": ["OFAC-SDN", "EU-Consolidated", "UN-Security-Council"],
        "checked_at": "2026-03-23T10:00:00Z",
    },
    "CUST-002": {
        "match": True,
        "matched_list": "OFAC-SDN",
        "match_type": "exact_name",
        "match_score": 0.98,
        "lists_checked": ["OFAC-SDN", "EU-Consolidated", "UN-Security-Council"],
        "checked_at": "2026-03-23T10:00:00Z",
    },
    "CUST-003": {
        "match": False,
        "lists_checked": ["OFAC-SDN", "EU-Consolidated", "UN-Security-Council"],
        "checked_at": "2026-03-23T10:00:00Z",
    },
}

JURISDICTION_RULES = {
    "US": {
        "applicable_regulations": ["BSA/AML", "OFAC", "FinCEN-CDD"],
        "risk_factors": ["PEP-status", "high-risk-country", "transaction-volume"],
        "reporting_threshold_usd": 10000,
        "enhanced_due_diligence_required": False,
        "regulation_ref": "31 CFR 1010.230",
    },
    "EU": {
        "applicable_regulations": ["AMLD6", "EU-Sanctions-Regulation"],
        "risk_factors": ["PEP-status", "high-risk-third-country", "complex-ownership"],
        "reporting_threshold_eur": 15000,
        "enhanced_due_diligence_required": True,
        "regulation_ref": "Directive (EU) 2024/1640 Art. 28",
    },
    "UK": {
        "applicable_regulations": ["MLR-2017", "Sanctions-Act-2018"],
        "risk_factors": ["PEP-status", "high-risk-country", "source-of-wealth"],
        "reporting_threshold_gbp": 10000,
        "enhanced_due_diligence_required": False,
        "regulation_ref": "MLR 2017 Reg. 33",
    },
}

RISK_SCORES = {
    "CUST-001": {"score": 25, "level": "low", "factors": ["standard-jurisdiction", "no-pep"]},
    "CUST-002": {"score": 95, "level": "critical", "factors": ["sanctions-match", "pep-status"]},
    "CUST-003": {"score": 78, "level": "high", "factors": ["high-risk-country", "complex-ownership", "large-transaction-volume"]},
}


def screen_sanctions(customer_id: str) -> dict:
    """Screen a customer against OFAC, EU, and UN sanctions lists."""
    result = SANCTIONS_DB.get(customer_id)
    if not result:
        return {"error": f"Customer {customer_id} not found", "source": "sanctions-db"}
    return {**result, "customer_id": customer_id, "source": "sanctions-db"}


def verify_jurisdiction(customer_id: str, jurisdiction: str) -> dict:
    """Look up applicable regulations and requirements for the customer's jurisdiction."""
    rules = JURISDICTION_RULES.get(jurisdiction.upper())
    if not rules:
        return {"error": f"Unknown jurisdiction: {jurisdiction}", "source": "jurisdiction-rules"}
    return {**rules, "customer_id": customer_id, "jurisdiction": jurisdiction, "source": "jurisdiction-rules"}


def assess_risk(customer_id: str) -> dict:
    """Compute a risk score for the customer based on all available factors."""
    result = RISK_SCORES.get(customer_id)
    if not result:
        return {"error": f"Customer {customer_id} not found", "source": "risk-model"}
    return {**result, "customer_id": customer_id, "source": "risk-model"}


def render_determination(
    customer_id: str,
    determination: str,
    reasoning: str,
    citations: list[str],
) -> dict:
    """Render the final KYC/AML determination."""
    return {
        "determination": determination,
        "customer_id": customer_id,
        "reasoning": reasoning,
        "citations": citations,
        "source": "determination-engine",
    }
