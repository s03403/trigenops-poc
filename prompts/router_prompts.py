"""Prompts for Step 5: Severity & Routing.

LLM generates incident descriptions and recommends assignment.
Hard severity rules remain deterministic.
"""

INCIDENT_DESCRIPTION_PROMPT = """You are preparing an ITSM incident description for ServiceNow.

Incident details:
Application: {application}
Environment: {environment}
Severity: {severity}
Detections: {detections_summary}
Correlation: {correlation_summary}
Business Date: {business_date}

Relevant application logs (retrieved from log store):
{rag_context}

Generate a professional incident description that includes:
- What is affected
- Since when
- Root cause (if logs provide evidence)
- Business impact

Rules:
- Use evidence from logs to state root cause when available.
- If no log evidence, do NOT speculate root cause.
- Be factual and concise.
- Use professional ITSM language.

Return plain text (3-5 sentences).
"""

ROUTING_PROMPT = """You are an ITSM routing assistant for Uniper.

Given the following incident, recommend the assignment group.

Application: {application}
Environment: {environment}
Incident Type: {incident_type}
Detections: {detections_summary}

Known assignment groups:
- ASCM App Support: ASCM application issues
- ATE Trading Support: ATE trade execution issues
- PromptOpt Data Ops: PromptOpt processing issues
- Infrastructure Ops: Network, connectivity, auth failures
- Data Platform Team: Cross-system data pipeline issues

Return a JSON object:
{{
    "assignment_group": "<group name>",
    "reason": "<one sentence why>"
}}
"""
