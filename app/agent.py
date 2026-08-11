from __future__ import annotations

import time
from dataclasses import dataclass

from . import metrics
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text, trace_text
from .prompt_management import resolve_prompt
from .tracing import get_langfuse_client, observe, propagate_attributes, tracing_enabled


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)

    @observe(name="answer-chat-message", as_type="agent", capture_input=False, capture_output=False)
    def run(
        self,
        user_id: str,
        feature: str,
        session_id: str,
        message: str,
        correlation_id: str | None = None,
    ) -> AgentResult:
        started = time.perf_counter()
        langfuse_client = get_langfuse_client()
        safe_message = trace_text(message)
        safe_feature = summarize_text(feature, max_len=50)
        trace_metadata = {
            "correlation_id": correlation_id or "unavailable",
            "feature": safe_feature,
            "service": "api",
        }

        langfuse_client.update_current_span(
            input={"message": safe_message},
            metadata=trace_metadata,
        )
        with propagate_attributes(
            user_id=hash_user_id(user_id),
            session_id=hash_user_id(session_id),
            tags=["lab", f"feature:{safe_feature}"],
            trace_name="answer-chat-message",
            metadata=trace_metadata,
            environment=os.getenv("APP_ENV", "dev"),
        ):
            docs = self._retrieve_context(message)
            prompt = self._resolve_prompt(langfuse_client, feature, docs, message)
            response, cost_usd = self._generate_response(langfuse_client, prompt, safe_message)
            quality_score = self._evaluate_response(message, response.text, docs)

        latency_ms = int((time.perf_counter() - started) * 1000)
        langfuse_client.update_current_span(
            output={"answer": trace_text(response.text)},
            metadata={
                "prompt_name": prompt.name,
                "prompt_label": prompt.label,
                "prompt_version": prompt.version,
                "prompt_source": prompt.source,
                "quality_score": quality_score,
            },
        )
        if tracing_enabled():
            langfuse_client.score_current_trace(
                name="response-quality",
                value=quality_score,
                data_type="NUMERIC",
                comment="Deterministic heuristic quality proxy",
            )

        metrics.record_request(
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            quality_score=quality_score,
        )

        return AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
        )

    @observe(name="retrieve-context", as_type="retriever", capture_input=False, capture_output=False)
    def _retrieve_context(self, message: str) -> list[str]:
        docs = retrieve(message)
        get_langfuse_client().update_current_span(
            input={"query": trace_text(message)},
            output={"documents": [trace_text(doc) for doc in docs]},
            metadata={"document_count": len(docs), "source": "in-memory-corpus"},
        )
        return docs

    @observe(name="resolve-prompt", as_type="span", capture_input=False, capture_output=False)
    def _resolve_prompt(self, langfuse_client, feature: str, docs: list[str], message: str):
        prompt = resolve_prompt(
            langfuse_client,
            feature=feature,
            docs=docs,
            message=message,
            enabled=tracing_enabled(),
        )
        langfuse_client.update_current_span(
            input={"feature": summarize_text(feature, 50), "document_count": len(docs)},
            output={"prompt_name": prompt.name, "prompt_version": prompt.version},
            metadata={
                "prompt_label": prompt.label,
                "prompt_source": prompt.source,
                "prompt_fetch_error": prompt.fetch_error,
            },
        )
        return prompt

    @observe(name="generate-response", as_type="generation", capture_input=False, capture_output=False)
    def _generate_response(self, langfuse_client, prompt, safe_message: str):
        response = self.llm.generate(prompt.text)
        cost_usd = self._estimate_cost(response.usage.input_tokens, response.usage.output_tokens)
        langfuse_client.update_current_generation(
            input=[{"role": "user", "content": safe_message}],
            output=[{"role": "assistant", "content": trace_text(response.text)}],
            model=response.model,
            metadata={
                "prompt_name": prompt.name,
                "prompt_label": prompt.label,
                "prompt_version": prompt.version,
                "prompt_source": prompt.source,
                "prompt_fetch_error": prompt.fetch_error,
            },
            usage_details={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            cost_details={"total": cost_usd},
            prompt=prompt.managed_prompt,
        )
        return response, cost_usd

    @observe(name="evaluate-response", as_type="evaluator", capture_input=False, capture_output=False)
    def _evaluate_response(self, question: str, answer: str, docs: list[str]) -> float:
        quality_score = self._heuristic_quality(question, answer, docs)
        get_langfuse_client().update_current_span(
            input={"answer": trace_text(answer), "document_count": len(docs)},
            output={"quality_score": quality_score},
            metadata={"method": "deterministic-heuristic"},
        )
        return quality_score

    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        input_cost = (tokens_in / 1_000_000) * 3
        output_cost = (tokens_out / 1_000_000) * 15
        return round(input_cost + output_cost, 6)

    def _heuristic_quality(self, question: str, answer: str, docs: list[str]) -> float:
        score = 0.5
        if docs:
            score += 0.2
        if len(answer) > 40:
            score += 0.1
        if question.lower().split()[0:1] and any(token in answer.lower() for token in question.lower().split()[:3]):
            score += 0.1
        if "[REDACTED" in answer:
            score -= 0.2
        return round(max(0.0, min(1.0, score)), 2)
