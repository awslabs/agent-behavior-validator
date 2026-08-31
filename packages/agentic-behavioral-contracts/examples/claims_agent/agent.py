# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Claims processing reference agent using Strands Agents + Bedrock.

Requires:
    pip install agent-validator[examples]
    AWS credentials configured with Bedrock access
    OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
"""

from __future__ import annotations

SYSTEM_PROMPT = """\
You are a claims processing agent for a health insurance company.

For each pharmacy claim, you MUST follow this exact process:
1. Look up the drug in the formulary database using the lookup_formulary tool
2. Check the member's coverage using the check_coverage tool
3. Based on the formulary and coverage results, render your decision using the render_decision tool

Rules:
- Always cite the policy section from the formulary lookup in your decision
- If the drug requires prior authorization, note this in your decision
- If the member's coverage is not active, deny the claim
- If the claim type is not pharmacy, medical, dental, or vision, you must escalate to human review
- Never approve a claim based on your general knowledge alone — always use the tools
"""


def create_claims_agent():
    """Create a Strands claims processing agent with OTEL enabled.

    This import is deferred so the core library doesn't depend on strands.
    """
    try:
        from strands import Agent
        from strands.models.bedrock import BedrockModel
        from strands.telemetry import StrandsTelemetry
    except ImportError:
        raise ImportError(
            "Strands Agents is required for the live agent. "
            "Install with: pip install agent-validator[examples]"
        )

    from examples.claims_agent.tools_strands import (
        lookup_formulary,
        check_coverage,
        render_decision,
    )

    StrandsTelemetry().setup_otlp_exporter()

    model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-6-20250514-v1:0")
    return Agent(
        model=model,
        tools=[lookup_formulary, check_coverage, render_decision],
        system_prompt=SYSTEM_PROMPT,
    )
