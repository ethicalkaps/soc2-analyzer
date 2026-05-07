# 🛡️ SOC 2 Analyzer

**A free, open-source tool that turns a 100-page SOC 2 report into a 1-page risk assessment in 30 seconds.**

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://soc2-analyzer-ethicalkaps.streamlit.app)

---

## What it does

GRC analysts spend 2–4 hours reading a single vendor's SOC 2 Type II report to find:
- Testing exceptions (controls that failed during the audit)
- Red flags (qualified opinions, stale reports, scope gaps)
- Complementary User Entity Controls (CUECs) the customer must implement
- Subservice organizations carved out of scope

This tool does that in 30 seconds using Claude. Drop in a SOC 2 PDF, get a structured risk summary with severity ratings and recommended follow-up questions to send to the vendor.

## Why it's different

- **Free forever.** Bring your own Anthropic API key — pay-as-you-go, ~$0.07 per report on Haiku 4.5 or ~$0.21 on Sonnet 4.6.
- **Privacy-first.** Your PDF is processed in memory, never stored. No logging, no analytics, no database. Self-host the source if you don't trust hosted tools with vendor data.
- **Built by a GRC practitioner.** Not a SaaS pitch. The prompt was designed by someone who reads these reports.

## Try it now

→ **[soc2-analyzer-ethicalkaps.streamlit.app](https://soc2-analyzer-ethicalkaps.streamlit.app)**

You'll need an Anthropic API key — get one at [console.anthropic.com](https://console.anthropic.com). Usage is pay-as-you-go: a typical SOC 2 analysis costs ~$0.07 on Haiku 4.5 or ~$0.21 on Sonnet 4.6.

## What you get

For each report, the tool extracts:

- **Vendor metadata** — name, audit period, auditor, opinion, in-scope services
- **Trust Service Criteria** covered (Security, Availability, Confidentiality, Processing Integrity, Privacy)
- **Subservice organizations** with carve-out vs. inclusive method flagged
- **Testing exceptions** with severity ratings and management responses
- **Red flags** — stale reports, scope gaps, qualified opinions, excessive CUECs
- **CUECs** organized by category (Access Management, Configuration, Monitoring, etc.)
- **Recommended follow-up questions** to send to the vendor
- **Overall risk rating** (Low / Medium / High / Critical)

Download the full report as Markdown to drop into your vendor risk register.

## Self-hosting

Don't trust hosted services with vendor SOC 2 reports? Run it locally.

```bash
git clone https://github.com/ethicalkaps/soc2-analyzer.git
cd soc2-analyzer
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. Paste your API key in the sidebar and start analyzing.

### Requirements

- Python 3.10+
- An Anthropic API key

## Privacy & Security

- **No persistence.** PDFs are processed in memory and discarded immediately after analysis.
- **No logging.** The app does not log requests, API keys, file contents, or analysis results.
- **No analytics.** Streamlit's anonymous usage stats are disabled in `.streamlit/config.toml`.
- **API key handling.** Your Anthropic API key is held in Streamlit session state for the duration of your browser session only. It's sent directly to Anthropic from the server hosting this app — never stored, never logged.
- **Self-host for max privacy.** If you're analyzing reports under NDA or with sensitive scope information, clone this repo and run it locally.

## How it works

1. **PDF text extraction** with [PyMuPDF](https://pymupdf.readthedocs.io/) — fast, no system dependencies, no OCR.
2. **Structured prompt to Claude** with a strict JSON schema (see `prompts.py`).
3. **Response parsing** with prefilled JSON anchoring for reliable structured output.
4. **Rendering** as an interactive Streamlit dashboard with downloadable Markdown report.

The "intelligence" is mostly in the prompt (`prompts.py`). It tells Claude to act as a senior GRC analyst, defines severity rubrics, lists categories of red flags to look for, and enforces a JSON schema. Tweak it for your needs.

## Limitations

- **Scanned PDFs don't work.** If the PDF is image-based (scanned), no text will be extracted. OCR it first with [ocrmypdf](https://github.com/ocrmypdf/OCRmyPDF) or Adobe Acrobat.
- **Very long reports may exceed Haiku's context window.** Switch to Sonnet 4.6 (1M token context) for >150-page reports.
- **This is a triage tool, not a substitute for professional review.** The output is a starting point. A qualified human should still review the actual report before any procurement decision.
- **Hallucination risk.** The prompt is designed to be conservative ("if not clearly stated, say 'Not specified'"), but LLMs can occasionally invent findings. Spot-check critical findings against the original report.

## Roadmap

- [ ] ISO 27001 audit report support
- [ ] Side-by-side comparison of two vendor reports
- [ ] Export to CSV / Excel for risk register import
- [ ] Multi-framework control mapping (SOC 2 → NIST CSF → CIS)
- [ ] Bridge letter detection and freshness check

PRs welcome.

## License

MIT — do whatever you want.

## Built by

[Kaps](https://www.linkedin.com/in/kapil-chaudhary-cyber-security/) — NOC Engineer pivoting to GRC. Run a YouTube channel called [Rapid Grasper](https://youtube.com/@rapidgrasper) where I cover cybersecurity and GRC topics.

If this tool saved you time, the best thanks is to share it with another GRC analyst or drop a star on the repo. ⭐
