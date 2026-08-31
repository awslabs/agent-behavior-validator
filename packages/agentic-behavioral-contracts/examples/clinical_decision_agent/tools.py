# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Simulated tools for the clinical decision support reference agent.

These tools use embedded lookup data to simulate drug interaction databases,
clinical guideline repositories, and dosing references. In production, these
would call services like DailyMed, DrugBank, or institutional formulary APIs.
"""

DRUG_INTERACTIONS = {
    ("warfarin", "aspirin"): {
        "interaction_found": True,
        "interaction_severity": "major",
        "description": "Increased risk of bleeding. Concurrent use of warfarin and aspirin significantly elevates hemorrhagic risk.",
        "recommendation": "Avoid combination unless specifically indicated. If required, monitor INR closely and watch for signs of bleeding.",
        "source_ref": "DrugBank DB00682-DB00945",
    },
    ("metformin", "lisinopril"): {
        "interaction_found": False,
        "interaction_severity": "none",
        "description": "No clinically significant interaction identified.",
        "recommendation": "Safe to co-administer. No dosage adjustment required.",
        "source_ref": "DrugBank DB00331-DB00722",
    },
    ("simvastatin", "amlodipine"): {
        "interaction_found": True,
        "interaction_severity": "moderate",
        "description": "Amlodipine may increase simvastatin levels, raising risk of myopathy.",
        "recommendation": "Limit simvastatin to 20mg/day when co-administered with amlodipine per FDA guidance.",
        "source_ref": "FDA Drug Safety Communication 2011-08",
    },
}

CLINICAL_GUIDELINES = {
    "hypertension": {
        "guideline": "AHA/ACC 2024 Guideline for the Management of Hypertension",
        "first_line": ["ACE inhibitors", "ARBs", "Calcium channel blockers", "Thiazide diuretics"],
        "target_bp": "< 130/80 mmHg for most adults",
        "monitoring": "Recheck BP in 4-6 weeks after initiation or dose change",
        "guideline_ref": "Section 7.2, AHA/ACC 2024",
    },
    "type2_diabetes": {
        "guideline": "ADA Standards of Care in Diabetes 2026",
        "first_line": ["Metformin"],
        "second_line": ["GLP-1 receptor agonists", "SGLT2 inhibitors"],
        "monitoring": "HbA1c every 3-6 months, renal function annually",
        "guideline_ref": "Section 9.1, ADA Standards 2026",
    },
    "hyperlipidemia": {
        "guideline": "ACC/AHA 2024 Guideline on Management of Blood Cholesterol",
        "first_line": ["High-intensity statin"],
        "target": "LDL-C reduction >= 50% for high-risk patients",
        "monitoring": "Lipid panel 4-12 weeks after initiation, then annually",
        "guideline_ref": "Section 4.4.2, ACC/AHA 2024",
    },
}

DOSING_REFERENCE = {
    "metformin": {
        "initial_dose": "500mg twice daily",
        "max_dose": "2000mg/day",
        "renal_adjustment": "eGFR < 30: contraindicated. eGFR 30-45: max 1000mg/day.",
        "source_ref": "DailyMed Metformin HCl Label",
    },
    "lisinopril": {
        "initial_dose": "10mg once daily",
        "max_dose": "40mg/day",
        "renal_adjustment": "CrCl < 30: start at 2.5mg/day",
        "source_ref": "DailyMed Lisinopril Label",
    },
    "simvastatin": {
        "initial_dose": "20mg once daily in evening",
        "max_dose": "40mg/day (20mg if on amlodipine)",
        "renal_adjustment": "Severe renal impairment: start at 5mg/day",
        "source_ref": "DailyMed Simvastatin Label",
    },
}


def check_drug_interactions(drug_a: str, drug_b: str) -> dict:
    """Check for known interactions between two drugs."""
    key = tuple(sorted([drug_a.lower(), drug_b.lower()]))
    result = DRUG_INTERACTIONS.get(key)
    if not result:
        return {
            "interaction_found": False,
            "interaction_severity": "unknown",
            "description": f"No interaction data available for {drug_a} + {drug_b}",
            "source": "drug-interaction-db",
        }
    return {**result, "drug_a": drug_a, "drug_b": drug_b, "source": "drug-interaction-db"}


def lookup_clinical_guidelines(condition: str) -> dict:
    """Retrieve current clinical guidelines for a condition."""
    result = CLINICAL_GUIDELINES.get(condition.lower().replace(" ", "_"))
    if not result:
        return {"error": f"No guidelines found for condition: {condition}", "source": "clinical-guidelines"}
    return {**result, "condition": condition, "source": "clinical-guidelines"}


def check_dosing_range(drug_name: str) -> dict:
    """Look up approved dosing ranges for a drug."""
    result = DOSING_REFERENCE.get(drug_name.lower())
    if not result:
        return {"error": f"No dosing data for {drug_name}", "source": "dosing-reference"}
    return {**result, "drug_name": drug_name, "source": "dosing-reference"}


def render_recommendation(
    patient_context: str,
    recommendation: str,
    reasoning: str,
    citations: list[str],
) -> dict:
    """Render the clinical recommendation with citations."""
    return {
        "recommendation": recommendation,
        "patient_context": patient_context,
        "reasoning": reasoning,
        "citations": citations,
        "source": "recommendation-engine",
    }
