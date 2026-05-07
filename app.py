"""
SOC 2 Analyzer — Streamlit App

A free, BYOK (Bring Your Own Key) tool that turns a 100-page SOC 2 report
into a 1-page risk assessment in 30 seconds.

Privacy: nothing is stored. The PDF is processed in memory, sent to the
Anthropic API using the user's own key, and discarded. No logging, no
analytics, no database.
"""

import streamlit as st

from analyzer import (
    AnalysisError,
    HAIKU_4_5,
    MODELS,
    PDFExtractionError,
    SONNET_4_6,
    analyze_soc2_report,
    extract_pdf_text,
    render_report_markdown,
)

# ----- Page Config -----

st.set_page_config(
    page_title="SOC 2 Analyzer — Free Vendor Risk Triage",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Free SOC 2 vendor risk triage tool. Built by Kaps · Rapid Grasper.",
        "Get Help": "https://github.com/ethicalkaps/soc2-analyzer",
    },
)

# ----- Custom CSS + Animations -----

st.markdown(
    """
    <style>
    /* ── Layout ── */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1100px;
    }

    /* ── Page fade-in on load ── */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(18px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    .block-container {
        animation: fadeInUp 0.55s ease-out both;
    }

    /* ── Animated gradient hero title ── */
    @keyframes gradientShift {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .gradient-title {
        font-size: 2.6rem;
        font-weight: 800;
        background: linear-gradient(270deg, #6366f1, #0ea5e9, #10b981, #6366f1);
        background-size: 300% 300%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: gradientShift 5s ease infinite;
        margin-bottom: 0.25rem;
    }

    /* ── Subtitle slide-in ── */
    @keyframes slideInLeft {
        from { opacity: 0; transform: translateX(-16px); }
        to   { opacity: 1; transform: translateX(0); }
    }
    .hero-subtitle {
        animation: slideInLeft 0.6s ease-out 0.2s both;
        color: #475569;
        font-size: 1.05rem;
    }
    .hero-tagline {
        animation: slideInLeft 0.6s ease-out 0.4s both;
        color: #94a3b8;
        font-size: 0.9rem;
    }

    /* ── Risk badges ── */
    .risk-badge {
        display: inline-block;
        padding: 0.4rem 1rem;
        border-radius: 0.5rem;
        font-weight: 600;
        font-size: 0.95rem;
        letter-spacing: 0.02em;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .risk-badge:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    }
    .risk-Low      { background: #dcfce7; color: #166534; }
    .risk-Medium   { background: #fef3c7; color: #92400e; }
    .risk-High     { background: #fed7aa; color: #9a3412; }
    .risk-Critical { background: #fecaca; color: #991b1b; }

    /* Pulse animation for Critical/High risk */
    @keyframes pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(220,38,38,0.35); }
        50%       { box-shadow: 0 0 0 7px rgba(220,38,38,0); }
    }
    .risk-Critical { animation: pulse 1.8s ease-in-out infinite; }

    @keyframes pulseOrange {
        0%, 100% { box-shadow: 0 0 0 0 rgba(234,88,12,0.3); }
        50%       { box-shadow: 0 0 0 6px rgba(234,88,12,0); }
    }
    .risk-High { animation: pulseOrange 2s ease-in-out infinite; }

    /* ── Finding cards with hover lift ── */
    .finding-card {
        background: #f8fafc;
        border-left: 3px solid #cbd5e1;
        padding: 0.85rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0.35rem;
        transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
    }
    .finding-card:hover {
        transform: translateX(4px);
        box-shadow: 0 4px 14px rgba(0,0,0,0.08);
        background: #ffffff;
    }
    .finding-card.severity-Critical { border-left-color: #dc2626; }
    .finding-card.severity-High     { border-left-color: #ea580c; }
    .finding-card.severity-Medium   { border-left-color: #d97706; }
    .finding-card.severity-Low      { border-left-color: #65a30d; }

    /* ── Shimmer skeleton for loading ── */
    @keyframes shimmer {
        0%   { background-position: -600px 0; }
        100% { background-position: 600px 0; }
    }
    .shimmer {
        background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
        background-size: 600px 100%;
        animation: shimmer 1.4s infinite linear;
        border-radius: 0.4rem;
        height: 1rem;
        margin: 0.4rem 0;
    }

    /* ── Empty state ── */
    .empty-state {
        text-align: center;
        padding: 2rem;
        color: #64748b;
        background: #f8fafc;
        border-radius: 0.5rem;
        border: 1px dashed #cbd5e1;
        transition: border-color 0.2s ease;
    }
    .empty-state:hover { border-color: #94a3b8; }

    /* ── Sidebar fade-in ── */
    @keyframes sidebarFade {
        from { opacity: 0; transform: translateX(-10px); }
        to   { opacity: 1; transform: translateX(0); }
    }
    section[data-testid="stSidebar"] {
        animation: sidebarFade 0.5s ease-out both;
    }

    /* ── Smooth tab transitions ── */
    .stTabs [data-baseweb="tab"] {
        transition: color 0.2s ease, border-color 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #6366f1 !important;
    }

    /* ── Button hover glow ── */
    .stButton > button[kind="primary"] {
        transition: box-shadow 0.2s ease, transform 0.15s ease;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 0 0 3px rgba(99,102,241,0.25);
        transform: translateY(-1px);
    }

    /* ── Hide Streamlit branding ── */
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }

    /* ── Section headings ── */
    h2 { margin-top: 2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----- Sidebar -----

with st.sidebar:
    st.markdown("### 🔑 API Configuration")
    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
        help="Your key is held in browser memory only. Never stored, never logged.",
    )

    if not api_key:
        st.info(
            "**Don't have a key?**  \n"
            "Get one free at [console.anthropic.com](https://console.anthropic.com) — "
            "new accounts get $5 in credit (~70 reports on Haiku)."
        )

    st.markdown("### 🧠 Model")
    model_choice = st.radio(
        "Choose model",
        list(MODELS.keys()),
        index=0,
        label_visibility="collapsed",
    )
    selected_model = MODELS[model_choice]
    st.caption(f"{selected_model.description}  \n**{selected_model.cost_per_report_estimate}**")

    st.markdown("---")
    st.markdown("### 🔒 Privacy")
    st.markdown(
        """
        - Your API key stays in browser session only
        - PDFs processed in memory, never saved
        - No logging, no analytics, no database
        - [Self-host the source](https://github.com/ethicalkaps/soc2-analyzer)
        """
    )

    st.markdown("---")
    st.caption(
        "Built by [Kaps](https://github.com/ethicalkaps) · "
        "[Rapid Grasper](https://youtube.com/@rapidgrasper)"
    )


# ----- Main Content -----

st.markdown(
    """
    <div class="gradient-title">🛡️ SOC 2 Analyzer</div>
    <div class="hero-subtitle">Drop a vendor SOC 2 Type II report. Get a structured risk summary in 30 seconds.</div>
    <div class="hero-tagline">Free forever &nbsp;·&nbsp; Bring your own Anthropic API key &nbsp;·&nbsp; Nothing is stored.</div>
    """,
    unsafe_allow_html=True,
)

st.markdown("")  # spacer

# ----- File Upload -----

uploaded_file = st.file_uploader(
    "Upload SOC 2 report (PDF, max 25MB / 200 pages)",
    type=["pdf"],
    help="Your file is processed in memory and discarded. Nothing is saved server-side.",
)

# ----- Constants -----
MAX_FILE_SIZE_MB = 25
MAX_PAGES = 200

# ----- Process Upload -----

if uploaded_file is not None:
    # Size check
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        st.error(f"File is {file_size_mb:.1f} MB. Max is {MAX_FILE_SIZE_MB} MB.")
        st.stop()

    # Quick metadata row
    col1, col2, col3 = st.columns(3)
    col1.metric("File", uploaded_file.name[:30] + ("..." if len(uploaded_file.name) > 30 else ""))
    col2.metric("Size", f"{file_size_mb:.1f} MB")

    # Extract text
    with st.spinner("Extracting text from PDF..."):
        try:
            file_bytes = uploaded_file.getvalue()
            extracted = extract_pdf_text(file_bytes)
        except PDFExtractionError as e:
            st.error(f"Could not read PDF: {e}")
            st.stop()

    col3.metric("Pages", extracted.page_count)

    # Page count check
    if extracted.page_count > MAX_PAGES:
        st.error(f"Report has {extracted.page_count} pages. Max is {MAX_PAGES}.")
        st.stop()

    # Scanned PDF warning
    if extracted.looks_like_scanned:
        st.warning(
            "⚠️ This PDF appears to be scanned (image-based). Very little text was extracted, "
            "which means analysis quality will be poor. You'll need to OCR the PDF first using "
            "a tool like Adobe Acrobat or [ocrmypdf](https://github.com/ocrmypdf/OCRmyPDF)."
        )

    # Analyze button
    analyze_disabled = not api_key or not api_key.startswith("sk-ant-")
    if analyze_disabled and not api_key:
        st.info("👈 Add your Anthropic API key in the sidebar to analyze.")
    elif analyze_disabled:
        st.warning("API key should start with `sk-ant-`. Double-check it's the right key.")

    if st.button("🔍 Analyze Report", type="primary", disabled=analyze_disabled, use_container_width=False):
        with st.spinner(f"Claude {selected_model.display_name} is analyzing the report..."):
            try:
                result = analyze_soc2_report(
                    report_text=extracted.text,
                    api_key=api_key,
                    model_id=selected_model.id,
                )
            except AnalysisError as e:
                st.error(f"❌ {e}")
                st.stop()

        # Store in session so we can show it after rerun
        st.session_state["last_result"] = result
        st.session_state["last_filename"] = uploaded_file.name


# ----- Render Results -----

def severity_badge(severity: str) -> str:
    return f'<span class="risk-badge risk-{severity}">{severity}</span>'


def render_results(result):
    """Render the analysis results in the main panel."""
    d = result.data

    # Handle non-SOC2 documents
    if not d.get("is_soc2_report", True):
        st.error("📄 Not a SOC 2 Report")
        st.markdown(d.get("message", "The uploaded document does not appear to be a SOC 2 report."))
        if d.get("document_type_detected"):
            st.caption(f"Detected document type: {d['document_type_detected']}")
        return

    st.markdown("---")

    # Header card with risk rating
    risk = d.get("overall_risk_rating", "Unknown")

    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.markdown(f"## {d.get('vendor_name', 'Unknown Vendor')}")
        st.caption(
            f"{d.get('report_type', 'N/A')} · "
            f"{d.get('audit_period', {}).get('start_date', '?')} → "
            f"{d.get('audit_period', {}).get('end_date', '?')} · "
            f"Audited by {d.get('auditor_firm', 'N/A')}"
        )
    with header_col2:
        st.markdown(
            f"<div style='text-align: right; padding-top: 0.5rem;'>"
            f"<div style='font-size: 0.85rem; color: #64748b;'>Overall Risk</div>"
            f"<div>{severity_badge(risk)}</div></div>",
            unsafe_allow_html=True,
        )

    # Executive summary
    st.markdown("### Executive Summary")
    st.markdown(d.get("executive_summary", "N/A"))

    # Tabs for detailed sections
    exceptions = d.get("exceptions", [])
    red_flags = d.get("red_flags", [])
    cuecs = d.get("cuecs", [])

    tab_labels = [
        f"🚩 Red Flags ({len(red_flags)})",
        f"⚠️ Exceptions ({len(exceptions)})",
        f"📋 CUECs ({len(cuecs)})",
        "📊 Scope & Coverage",
        "❓ Follow-Up Questions",
    ]
    tabs = st.tabs(tab_labels)

    # Red Flags tab
    with tabs[0]:
        if red_flags:
            for rf in red_flags:
                sev = rf.get("severity", "?")
                cat = rf.get("category", "Other")
                desc = rf.get("description", "")
                st.markdown(
                    f'<div class="finding-card severity-{sev}">'
                    f'{severity_badge(sev)} &nbsp; <strong>{cat}</strong><br/>'
                    f'<span style="color: #334155;">{desc}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div class="empty-state">✅ No significant red flags identified.</div>', unsafe_allow_html=True)

    # Exceptions tab
    with tabs[1]:
        st.caption("Testing exceptions are controls the auditor found ineffective during the audit period.")
        if exceptions:
            for ex in exceptions:
                sev = ex.get("severity", "?")
                ctrl = ex.get("control_id", "N/A")
                desc = ex.get("description", "")
                mr = ex.get("management_response", "")
                inner = (
                    f'{severity_badge(sev)} &nbsp; <strong>Control: {ctrl}</strong><br/>'
                    f'<span style="color: #334155;">{desc}</span>'
                )
                if mr and mr != "Not specified":
                    inner += f'<br/><em style="color: #64748b; font-size: 0.9rem;">Management response: {mr}</em>'
                st.markdown(
                    f'<div class="finding-card severity-{sev}">{inner}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div class="empty-state">✅ No testing exceptions reported.</div>', unsafe_allow_html=True)

    # CUECs tab
    with tabs[2]:
        st.caption("Complementary User Entity Controls — what YOUR organization must do for the vendor's controls to work.")
        if cuecs:
            for c in cuecs:
                cat = c.get("category", "Other")
                desc = c.get("description", "")
                st.markdown(
                    f'<div class="finding-card">'
                    f'<strong>[{cat}]</strong> {desc}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div class="empty-state">No CUECs identified in this report.</div>', unsafe_allow_html=True)

    # Scope tab
    with tabs[3]:
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("**Trust Service Criteria**")
            criteria = d.get("trust_service_criteria", [])
            if criteria:
                for c in criteria:
                    st.markdown(f"- {c}")
            else:
                st.caption("Not specified")

            st.markdown("**Auditor Opinion**")
            opinion = d.get("auditor_opinion", "Unknown")
            st.markdown(f"`{opinion}`")

        with col_b:
            st.markdown("**In-Scope Services**")
            services = d.get("in_scope_services", [])
            if services:
                for s in services:
                    st.markdown(f"- {s}")
            else:
                st.caption("Not specified")

            st.markdown("**Subservice Organizations**")
            subs = d.get("subservice_organizations", [])
            if subs:
                for s in subs:
                    method = s.get("method", "?")
                    name = s.get("name", "N/A")
                    services_text = s.get("services", "")
                    st.markdown(f"- **{name}** ({method}) — {services_text}")
            else:
                st.caption("None disclosed")

    # Follow-up questions tab
    with tabs[4]:
        questions = d.get("recommended_questions", [])
        if questions:
            st.caption("Send these to the vendor based on gaps found in the report:")
            for i, q in enumerate(questions, 1):
                st.markdown(f"{i}. {q}")
        else:
            st.markdown('<div class="empty-state">No follow-up questions recommended.</div>', unsafe_allow_html=True)

    # Download + cost footer
    st.markdown("---")
    dl_col, cost_col = st.columns([1, 2])

    with dl_col:
        markdown_report = render_report_markdown(result)
        filename_base = st.session_state.get("last_filename", "soc2-report").rsplit(".", 1)[0]
        st.download_button(
            label="📥 Download Report (Markdown)",
            data=markdown_report,
            file_name=f"{filename_base}-risk-assessment.md",
            mime="text/markdown",
        )

    with cost_col:
        st.caption(
            f"Analyzed with **{result.model_used}** · "
            f"{result.input_tokens:,} in / {result.output_tokens:,} out tokens · "
            f"Estimated cost: **${result.estimated_cost:.4f}**"
        )


# Show results if we have them in session
if "last_result" in st.session_state:
    render_results(st.session_state["last_result"])
elif uploaded_file is None:
    # First-time landing state
    st.markdown("")
    st.markdown(
        """
        <div class="empty-state">
        <strong>How it works</strong><br/>
        1. Paste your Anthropic API key in the sidebar (free $5 credit on signup)<br/>
        2. Upload a vendor's SOC 2 Type II PDF<br/>
        3. Get a structured risk assessment with red flags, exceptions, CUECs, and follow-up questions
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("💡 Don't have a SOC 2 report to test with?"):
        st.markdown(
            """
            Many cloud providers publish their SOC 2 reports publicly:
            - [AWS Artifact](https://aws.amazon.com/artifact/) (requires AWS account)
            - [Cloudflare Trust Hub](https://www.cloudflare.com/trust-hub/compliance-resources/)
            - [Vercel Security](https://vercel.com/security)
            - Search: `"SOC 2 Type II" filetype:pdf [vendor name]`
            """
        )
