"""Tool-calling review insight agent with a deterministic offline fallback."""

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .data import dataset_stats
from .heuristic import build_heuristic_report
from .llm import LLMUnavailable, OpenAIChatClient
from .models import InsightReport, ToolTrace, report_from_dict
from .tools import ToolContext, compact_tool_result, execute_tool, tool_schemas


REPORT_SCHEMA_HINT = {
    "app": {"app_id": "string", "country": "string|null", "language": "string|null"},
    "dataset": {
        "review_count": "integer",
        "average_score": "number",
        "low_score_rate": "number",
        "date_range": {"start": "YYYY-MM-DD|null", "end": "YYYY-MM-DD|null"},
    },
    "overview": "string",
    "topics": [{
        "name": "string",
        "summary": "string",
        "review_count": "integer",
        "share": "number",
        "average_score": "number",
        "severity": "number 0..1",
        "recency": "number 0..1",
        "priority_score": "number 0..1",
        "impact": "string",
        "recommendation": "string",
        "facts": ["string"],
        "inferences": ["string"],
        "evidence": [{
            "review_id": "string",
            "score": "number",
            "review_date": "string|null",
            "quote": "exact original review text",
            "why_relevant": "string",
        }],
    }],
    "recommendations": ["string"],
    "limitations": ["string"],
}


class ReviewAgent:
    def __init__(self, context: ToolContext, output_language: str = "en",
                 client: Optional[OpenAIChatClient] = None,
                 max_rounds: int = 4) -> None:
        self.context = context
        self.output_language = "zh" if output_language.lower().startswith("zh") else "en"
        self.client = client or OpenAIChatClient()
        self.max_rounds = max(1, min(4, int(max_rounds)))

    def run(self, question: str) -> InsightReport:
        question = (question or "What are the most important user problems and what should the product team improve first?").strip()
        trace: List[ToolTrace] = []
        if not self.client.available:
            return self._demo_report(question, trace, "No API key configured.")

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": question},
        ]
        try:
            for round_number in range(self.max_rounds):
                response = self.client.chat(messages, tool_schemas(), final=False)
                message = response.choices[0].message
                tool_calls = getattr(message, "tool_calls", None) or []
                if tool_calls:
                    messages.append(self._assistant_message(message, tool_calls))
                    for call in tool_calls:
                        name, raw_arguments, call_id = self._tool_call_parts(call)
                        try:
                            arguments = json.loads(raw_arguments or "{}")
                            result = execute_tool(name, arguments, self.context)
                            trace.append(ToolTrace(name=name, arguments=arguments,
                                                   result_summary=compact_tool_result(result), success=True))
                            tool_content = json.dumps(result, ensure_ascii=False)
                        except Exception as exc:
                            arguments = _safe_json(raw_arguments)
                            trace.append(ToolTrace(name=name, arguments=arguments,
                                                   result_summary=str(exc), success=False))
                            tool_content = json.dumps({"error": str(exc)}, ensure_ascii=False)
                        messages.append({"role": "tool", "tool_call_id": call_id, "content": tool_content})
                    continue

                content = getattr(message, "content", None) or ""
                payload = _parse_json(content)
                if payload:
                    report = report_from_dict(
                        payload,
                        default_app_id=self.context.app_id,
                        default_country=self.context.country,
                        default_language=self.context.language,
                        output_language=self.output_language,
                        trace=trace,
                        demo_mode=False,
                    )
                    return self._ground_report(report)
                # Ask for a clean final JSON response if the model returned prose.
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": "Return only valid JSON using this exact structure: %s" % json.dumps(REPORT_SCHEMA_HINT),
                })
                final_response = self.client.chat(messages, [], final=True)
                final_message = final_response.choices[0].message
                payload = _parse_json(getattr(final_message, "content", None) or "")
                if payload:
                    report = report_from_dict(
                        payload,
                        default_app_id=self.context.app_id,
                        default_country=self.context.country,
                        default_language=self.context.language,
                        output_language=self.output_language,
                        trace=trace,
                        demo_mode=False,
                    )
                    return self._ground_report(report)
                break
            # If the model spent all tool rounds researching, give it one final
            # synthesis request instead of immediately falling back offline.
            messages.append({
                "role": "user",
                "content": "The research step is complete. Return only valid JSON using this exact structure: %s" %
                           json.dumps(REPORT_SCHEMA_HINT, ensure_ascii=False),
            })
            final_response = self.client.chat(messages, [], final=True)
            final_message = final_response.choices[0].message
            payload = _parse_json(getattr(final_message, "content", None) or "")
            if payload:
                report = report_from_dict(
                    payload,
                    default_app_id=self.context.app_id,
                    default_country=self.context.country,
                    default_language=self.context.language,
                    output_language=self.output_language,
                    trace=trace,
                    demo_mode=False,
                )
                return self._ground_report(report)
            return self._demo_report(question, trace, "The model did not return a valid structured report.")
        except Exception as exc:
            return self._demo_report(question, trace, "Live model call failed: %s" % exc)

    def _demo_report(self, question: str, trace: List[ToolTrace], reason: str) -> InsightReport:
        stats = dataset_stats(self.context.reviews)
        trace.append(ToolTrace(
            name="offline_demo_fallback",
            arguments={"question": question},
            result_summary=reason,
            success=True,
        ))
        return build_heuristic_report(
            self.context.reviews,
            app_id=self.context.app_id,
            country=self.context.country,
            language=self.context.language,
            output_language=self.output_language,
            question=question,
            trace=trace,
            demo_mode=True,
        )

    def _ground_report(self, report: InsightReport) -> InsightReport:
        valid_ids = {review.review_id: review for review in self.context.reviews}
        for topic in report.topics:
            grounded = []
            for evidence in topic.evidence:
                original = valid_ids.get(evidence.review_id)
                if not original:
                    continue
                # Always render the source-of-truth text and metadata. This prevents
                # a model from paraphrasing an evidence quote while presenting it as exact.
                evidence.score = original.score
                evidence.review_date = original.review_date
                evidence.quote = original.content
                grounded.append(evidence)
            topic.evidence = grounded
            topic.review_count = max(0, topic.review_count)
            topic.share = max(0.0, min(1.0, topic.share))
            topic.priority_score = max(0.0, min(1.0, topic.priority_score))
        if not report.review_count:
            stats = dataset_stats(self.context.reviews)
            report.review_count = stats["review_count"]
            report.average_score = stats["average_score"]
            report.low_score_rate = stats["low_score_rate"]
            report.date_range = stats["date_range"]
        if not report.limitations:
            report.limitations = ["Only Google Play reviews were analyzed."]
        return report

    def _system_prompt(self) -> str:
        language = "Chinese" if self.output_language == "zh" else "English"
        return """You are a product and user-research analyst for a generic Google Play app review dataset.
The app can belong to any category. Do not assume a delivery, finance, social or gaming context.
Answer in %s. Use tools to inspect the dataset and original reviews before making claims.
You may discover 3-7 themes; do not use a fixed product-specific taxonomy.
Use the following transparent priority formula: priority_score = 0.5*prevalence + 0.3*severity + 0.2*recency.
Prevalence, severity and recency must be normalized to 0..1 and shown separately.
Never invent review IDs, quotes, counts or dates. Evidence quotes must be copied exactly from tool results.
Clearly separate facts from inferences. Return JSON only when you are ready, with this schema:
%s""" % (language, json.dumps(REPORT_SCHEMA_HINT, ensure_ascii=False))

    @staticmethod
    def _assistant_message(message: Any, tool_calls: Sequence[Any]) -> Dict[str, Any]:
        calls = []
        for call in tool_calls:
            name, raw_arguments, call_id = ReviewAgent._tool_call_parts(call)
            calls.append({
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": raw_arguments},
            })
        return {"role": "assistant", "content": getattr(message, "content", None) or "", "tool_calls": calls}

    @staticmethod
    def _tool_call_parts(call: Any) -> Tuple[str, str, str]:
        function = getattr(call, "function", None)
        name = getattr(function, "name", None) or call.get("function", {}).get("name")
        arguments = getattr(function, "arguments", None) or call.get("function", {}).get("arguments", "{}")
        call_id = getattr(call, "id", None) or call.get("id", "tool-call")
        return str(name), str(arguments), str(call_id)


def _parse_json(content: str) -> Optional[Dict[str, Any]]:
    text = content.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None


def _safe_json(raw: str) -> Dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def run_agent(reviews: Sequence[Any], app_id: str, country: Optional[str],
              language: Optional[str], question: str, output_language: str = "en",
              client: Optional[OpenAIChatClient] = None) -> InsightReport:
    context = ToolContext(list(reviews), app_id=app_id, country=country, language=language)
    return ReviewAgent(context, output_language=output_language, client=client).run(question)
