"""Prompts for Step 4: Correlation & Suppression.

LLM generates human-readable correlation narratives.
Deduplication and grouping logic is deterministic.
"""

CORRELATION_PROMPT = """You are an observability assistant for Uniper energy trading systems.

Multiple anomalies have been detected. Analyze them and provide a correlation summary.

Detections:
{detections_json}

Relevant application logs (retrieved from log store):
{rag_context}

Your task:
1. Identify if these detections are likely related.
2. Use the application logs above to identify the likely root cause.
3. Provide a concise correlation narrative for the incident ticket.

Rules:
- Use evidence from logs to support your analysis.
- If logs clearly show a root cause, state it.
- If no relevant logs are available, use "likely", "suggests", "may indicate".
- Group related symptoms together.
- Be concise: 3-5 sentences max.

Return a JSON object:
{{
    "are_related": true/false,
    "likely_cause": "<root cause from logs or suspected issue>",
    "correlation_narrative": "<human-readable summary with log evidence>"
}}
"""
