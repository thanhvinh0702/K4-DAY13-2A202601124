from __future__ import annotations

import time

from .incidents import STATE
from .tracing import get_langfuse_client, observe

CORPUS = {
    "refund": ["Refunds are available within 7 days with proof of purchase."],
    "monitoring": ["Metrics detect incidents, traces localize them, logs explain root cause."],
    "policy": ["Do not expose PII in logs. Use sanitized summaries only."],
}


@observe(
    name="rag.retrieve",
    capture_input=False,
    capture_output=False,
)
def retrieve(message: str) -> list[str]:
    if STATE["tool_fail"]:
        raise RuntimeError("Vector store timeout")
    if STATE["rag_slow"]:
        time.sleep(2.5)

    lowered = message.lower()
    docs = next(
        (items for key, items in CORPUS.items() if key in lowered),
        ["No domain document matched. Use general fallback answer."],
    )
    get_langfuse_client().update_current_span(
        metadata={
            "doc_count": len(docs),
            "rag_slow": STATE["rag_slow"],
        }
    )
    return docs
