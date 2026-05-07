"""
SOC 2 Analyzer Core Logic

Handles PDF text extraction and Claude API calls.
Stateless — no data is stored anywhere.
"""

import json
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import fitz  # PyMuPDF
from anthropic import Anthropic, APIError, AuthenticationError, BadRequestError, RateLimitError

from prompts import SOC2_SYSTEM_PROMPT, build_user_message


# ----- Model configuration -----

@dataclass(frozen=True)
class ModelConfig:
    id: str
    display_name: str
    description: str
    cost_per_report_estimate: str
    input_cost_per_mtok: float
    output_cost_per_mtok: float


HAIKU_4_5 = ModelConfig(
    id="claude-haiku-4-5-20251001",
    display_name="Haiku 4.5",
    description="Fast, accurate, cheap. The right default for SOC 2 analysis.",
    cost_per_report_estimate="~$0.07 per report",
    input_cost_per_mtok=1.00,
    output_cost_per_mtok=5.00,
)

SONNET_4_6 = ModelConfig(
    id="claude-sonnet-4-6",
    display_name="Sonnet 4.6",
    description="Deeper analysis. Use for complex reports or when you want a second opinion.",
    cost_per_report_estimate="~$0.21 per report",
    input_cost_per_mtok=3.00,
    output_cost_per_mtok=15.00,
)

MODELS = {
    "Haiku 4.5": HAIKU_4_5,
    "Sonnet 4.6": SONNET_4_6,
}


# ----- PDF Extraction -----

class PDFExtractionError(Exception):
    pass


@dataclass
class ExtractedPDF:
    text: str
    page_count: int
    char_count: int
    looks_like_scanned: bool  # True if very little text was extracted


def extract_pdf_text(file_bytes: bytes) -> ExtractedPDF:
    """Extract text from PDF bytes. Returns an ExtractedPDF object.

    Raises PDFExtractionError if the PDF can't be opened.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise PDFExtractionError(f"Could not open PDF: {e}") from e

    try:
        page_count = doc.page_count
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        text = "\n\n".join(text_parts)
    finally:
        doc.close()

    char_count = len(text)
    # Heuristic: a real SOC 2 has thousands of chars per page. Scanned PDFs
    # often return <100 chars per page (just OCR'd page numbers, etc).
    chars_per_page = char_count / page_count if page_count else 0
    looks_like_scanned = chars_per_page < 100 and page_count > 5

    return ExtractedPDF(
        text=text,
        page_count=page_count,
        char_count=char_count,
        looks_like_scanned=looks_like_scanned,
    )


# ----- Claude API Call -----

class AnalysisError(Exception):
    """User-friendly error wrapping API failures."""
    pass


@dataclass
class AnalysisResult:
    data: dict
    model_used: str
    input_tokens: int
    output_tokens: int

    @property
    def estimated_cost(self) -> float:
        """Cost in USD based on the model used."""
        for cfg in MODELS.values():
            if cfg.id == self.model_used:
                input_cost = (self.input_tokens / 1_000_000) * cfg.input_cost_per_mtok
                output_cost = (self.output_tokens / 1_000_000) * cfg.output_cost_per_mtok
                return input_cost + output_cost
        return 0.0


def _parse_json_response(raw_text: str) -> dict:
    """Robustly parse JSON from Claude's response, handling common edge cases."""
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        # Remove first line (```json or ```)
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-3].strip()

    # Find the JSON object boundaries
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace == -1 or last_brace == -1 or last_brace < first_brace:
        raise AnalysisError(
            "Claude's response wasn't valid JSON. This sometimes happens with unusual report formats — try the other model."
        )

    json_text = text[first_brace:last_brace + 1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        raise AnalysisError(
            f"Could not parse Claude's response as JSON. Try the other model. (Detail: {e.msg})"
        ) from e


def analyze_soc2_report(
    report_text: str,
    api_key: str,
    model_id: str,
    max_tokens: int = 4096,
) -> AnalysisResult:
    """Send the SOC 2 text to Claude and return the structured analysis.

    Raises AnalysisError with a user-friendly message on any failure.
    """
    if not api_key or not api_key.strip():
        raise AnalysisError("API key is required.")

    if not report_text.strip():
        raise AnalysisError("No text could be extracted from the PDF.")

    client = Anthropic(api_key=api_key.strip())

    try:
        response = client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            system=SOC2_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": build_user_message(report_text)},
                # Prefill with `{` to strongly anchor JSON output
                {"role": "assistant", "content": "{"},
            ],
        )
    except AuthenticationError:
        raise AnalysisError(
            "Invalid API key. Double-check your key at console.anthropic.com — "
            "it should start with 'sk-ant-'."
        )
    except RateLimitError:
        raise AnalysisError(
            "Anthropic rate limit hit. Wait a minute and try again, or check "
            "your usage at console.anthropic.com."
        )
    except BadRequestError as e:
        msg = str(e).lower()
        if "max_tokens" in msg or "context" in msg or "too long" in msg:
            raise AnalysisError(
                "This report is too large for the selected model. Try Sonnet 4.6 "
                "(supports 1M token context) or upload a smaller report."
            )
        raise AnalysisError(f"Bad request to Anthropic API: {e}")
    except APIError as e:
        raise AnalysisError(f"Anthropic API error: {e}")
    except Exception as e:
        raise AnalysisError(f"Unexpected error calling Claude: {e}")

    # Reattach the prefilled `{` to the response
    raw_text = "{" + response.content[0].text

    try:
        data = _parse_json_response(raw_text)
    except AnalysisError:
        raise
    except Exception as e:
        raise AnalysisError(f"Could not parse response: {e}")

    return AnalysisResult(
        data=data,
        model_used=model_id,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


# ----- Markdown Report Generation (for download) -----

def render_report_markdown(result: AnalysisResult) -> str:
    """Convert the JSON result into a downloadable Markdown report."""
    d = result.data

    if not d.get("is_soc2_report", True):
        return f"# Not a SOC 2 Report\n\n{d.get('message', 'Document does not appear to be a SOC 2 report.')}\n"

    lines = []
    lines.append(f"# SOC 2 Risk Assessment: {d.get('vendor_name', 'Unknown Vendor')}\n")
    lines.append(f"_Generated by SOC 2 Analyzer — analysis only, not a substitute for professional review._\n")

    lines.append("## Overview\n")
    period = d.get("audit_period", {})
    lines.append(f"- **Vendor:** {d.get('vendor_name', 'N/A')}")
    lines.append(f"- **Report Type:** {d.get('report_type', 'N/A')}")
    lines.append(f"- **Audit Period:** {period.get('start_date', 'N/A')} → {period.get('end_date', 'N/A')}")
    lines.append(f"- **Auditor:** {d.get('auditor_firm', 'N/A')}")
    lines.append(f"- **Auditor Opinion:** {d.get('auditor_opinion', 'N/A')}")
    lines.append(f"- **Trust Service Criteria:** {', '.join(d.get('trust_service_criteria', [])) or 'N/A'}")
    lines.append(f"- **Overall Risk Rating:** **{d.get('overall_risk_rating', 'N/A')}**\n")

    lines.append("## Executive Summary\n")
    lines.append(f"{d.get('executive_summary', 'N/A')}\n")

    services = d.get("in_scope_services", [])
    if services:
        lines.append("## In-Scope Services\n")
        for s in services:
            lines.append(f"- {s}")
        lines.append("")

    subservices = d.get("subservice_organizations", [])
    if subservices:
        lines.append("## Subservice Organizations\n")
        for s in subservices:
            method = s.get("method", "?")
            lines.append(f"- **{s.get('name', 'N/A')}** ({method}) — {s.get('services', 'N/A')}")
        lines.append("")

    exceptions = d.get("exceptions", [])
    lines.append(f"## Testing Exceptions ({len(exceptions)})\n")
    if exceptions:
        for e in exceptions:
            lines.append(f"### [{e.get('severity', '?')}] {e.get('control_id', 'N/A')}")
            lines.append(f"{e.get('description', 'N/A')}\n")
            mr = e.get("management_response", "")
            if mr and mr != "Not specified":
                lines.append(f"_Management response: {mr}_\n")
    else:
        lines.append("No testing exceptions identified.\n")

    red_flags = d.get("red_flags", [])
    lines.append(f"## Red Flags ({len(red_flags)})\n")
    if red_flags:
        for r in red_flags:
            lines.append(f"- **[{r.get('severity', '?')}] {r.get('category', 'N/A')}** — {r.get('description', 'N/A')}")
        lines.append("")
    else:
        lines.append("No significant red flags identified.\n")

    cuecs = d.get("cuecs", [])
    lines.append(f"## Complementary User Entity Controls ({len(cuecs)})\n")
    lines.append("_These are controls YOUR organization must implement for the vendor's controls to be effective._\n")
    if cuecs:
        for c in cuecs:
            lines.append(f"- **[{c.get('category', 'Other')}]** {c.get('description', 'N/A')}")
        lines.append("")
    else:
        lines.append("No CUECs identified in the report.\n")

    questions = d.get("recommended_questions", [])
    if questions:
        lines.append("## Recommended Follow-Up Questions for the Vendor\n")
        for q in questions:
            lines.append(f"- {q}")
        lines.append("")

    lines.append("---")
    lines.append(f"_Analysis generated using {result.model_used}._  ")
    lines.append(f"_Tokens: {result.input_tokens:,} in / {result.output_tokens:,} out · Estimated cost: ${result.estimated_cost:.4f}_")

    return "\n".join(lines)
