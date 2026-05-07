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

# ----- Palmer-style Theme: CSS + Smoke Orbs -----

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ── Design tokens ── */
    :root {
        --bg:          #080808;
        --bg-card:     #111111;
        --bg-card-2:   #181818;
        --border:      rgba(255,255,255,0.07);
        --border-hi:   rgba(255,255,255,0.14);
        --white:       #ffffff;
        --gray-200:    #e5e5e5;
        --gray-400:    #a0a0a0;
        --gray-600:    #666666;
        --gray-800:    #222222;
        --font:        'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ── Base ── */
    body { background: var(--bg) !important; margin: 0; }
    .stApp {
        background: transparent !important;
        font-family: var(--font) !important;
        color: var(--gray-400) !important;
    }

    /* ── Floating smoke orbs (Palmer aesthetic) ── */
    .stApp::before {
        content: '';
        position: fixed;
        top: -25%; right: -15%;
        width: 70vw; height: 70vw;
        background: radial-gradient(circle, rgba(255,255,255,0.072) 0%, rgba(255,255,255,0.018) 45%, transparent 70%);
        filter: blur(90px);
        pointer-events: none;
        z-index: 0;
        animation: driftA 18s ease-in-out infinite alternate;
    }
    .stApp::after {
        content: '';
        position: fixed;
        bottom: -20%; left: -15%;
        width: 55vw; height: 55vw;
        background: radial-gradient(circle, rgba(255,255,255,0.048) 0%, rgba(255,255,255,0.01) 50%, transparent 70%);
        filter: blur(110px);
        pointer-events: none;
        z-index: 0;
        animation: driftB 22s ease-in-out infinite alternate;
    }

    /* ── Z-index stacking: content above orbs ── */
    [data-testid="stSidebar"],
    [data-testid="stMain"],
    [data-testid="stHeader"] { position: relative; z-index: 1; }

    /* ── Layout ── */
    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 4rem;
        max-width: 1080px;
        animation: fadeUp 0.6s ease-out both;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: rgba(8,8,8,0.9) !important;
        border-right: 1px solid var(--border) !important;
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        animation: slideLeft 0.5s ease-out both;
    }
    [data-testid="stSidebar"] h3 {
        color: var(--gray-600) !important;
        font-size: 0.68rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.12em !important;
        text-transform: uppercase !important;
    }

    /* ── Text input ── */
    [data-testid="stTextInput"] input {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        color: var(--white) !important;
        font-family: var(--font) !important;
        border-radius: 10px !important;
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    [data-testid="stTextInput"] input:focus {
        border-color: rgba(255,255,255,0.28) !important;
        box-shadow: 0 0 0 3px rgba(255,255,255,0.06) !important;
        outline: none !important;
    }
    [data-testid="stTextInput"] input::placeholder { color: var(--gray-600) !important; }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        background: var(--bg-card) !important;
        border: 1px dashed rgba(255,255,255,0.12) !important;
        border-radius: 14px !important;
        padding: 0.85rem 1.1rem !important;
        transition: border-color 0.25s, box-shadow 0.25s;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: rgba(255,255,255,0.28) !important;
        box-shadow: 0 0 0 4px rgba(255,255,255,0.04) !important;
    }
    [data-testid="stFileUploader"] label {
        color: var(--gray-400) !important;
        font-size: 0.85rem !important;
        margin-bottom: 0.6rem !important;
        display: block !important;
    }

    /* ── Primary button — white filled ── */
    .stButton > button[kind="primary"] {
        background: var(--white) !important;
        color: #000000 !important;
        border: none !important;
        border-radius: 10px !important;
        font-family: var(--font) !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.5);
        transition: opacity 0.2s, transform 0.15s, box-shadow 0.2s;
    }
    .stButton > button[kind="primary"]:hover:not(:disabled) {
        opacity: 0.88 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(255,255,255,0.14) !important;
    }
    .stButton > button[kind="primary"]:disabled {
        background: var(--gray-800) !important;
        color: var(--gray-600) !important;
        box-shadow: none !important;
    }

    /* ── Download button — outline ── */
    .stDownloadButton > button {
        background: transparent !important;
        border: 1px solid var(--border-hi) !important;
        color: var(--white) !important;
        border-radius: 10px !important;
        font-family: var(--font) !important;
        font-weight: 500 !important;
        font-size: 0.88rem !important;
        transition: background 0.2s, border-color 0.2s, transform 0.15s;
    }
    .stDownloadButton > button:hover {
        background: rgba(255,255,255,0.06) !important;
        border-color: rgba(255,255,255,0.3) !important;
        transform: translateY(-1px) !important;
    }

    /* ── Tabs ── */
    [data-baseweb="tab-list"] {
        background: transparent !important;
        border-bottom: 1px solid var(--border) !important;
        gap: 0 !important;
    }
    [data-baseweb="tab"] {
        background: transparent !important;
        color: var(--gray-600) !important;
        font-family: var(--font) !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        border-bottom: 2px solid transparent !important;
        padding: 0.6rem 1.2rem !important;
        transition: color 0.2s, border-color 0.2s !important;
    }
    [data-baseweb="tab"]:hover { color: var(--gray-400) !important; }
    [aria-selected="true"][data-baseweb="tab"] {
        color: var(--white) !important;
        border-bottom-color: var(--white) !important;
    }

    /* ── Metrics ── */
    [data-testid="stMetric"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        padding: 1rem 1.2rem !important;
    }
    [data-testid="stMetricLabel"] p {
        color: var(--gray-600) !important;
        font-size: 0.68rem !important;
        letter-spacing: 0.1em !important;
        text-transform: uppercase !important;
        font-weight: 500 !important;
    }
    [data-testid="stMetricValue"] {
        color: var(--white) !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
    }

    /* ── Headings ── */
    h1, h2, h3 {
        font-family: var(--font) !important;
        color: var(--white) !important;
        font-weight: 600 !important;
    }
    h2 {
        font-size: 1.05rem !important;
        margin-top: 2rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--border);
        letter-spacing: -0.01em;
    }

    /* ── Expander (Palmer accordion style) ── */
    [data-testid="stExpander"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        overflow: hidden;
        margin-bottom: 0.4rem !important;
    }
    [data-testid="stExpander"] summary {
        color: var(--white) !important;
        font-family: var(--font) !important;
        font-weight: 500 !important;
        padding: 0.9rem 1.1rem !important;
    }
    [data-testid="stExpander"] summary:hover {
        background: rgba(255,255,255,0.04) !important;
    }

    /* ── Inline code ── */
    code {
        background: rgba(255,255,255,0.08) !important;
        color: var(--gray-200) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        padding: 0.1rem 0.35rem !important;
        font-size: 0.85em !important;
    }

    /* ── HR & Caption ── */
    hr { border-color: var(--border) !important; }
    [data-testid="stCaptionContainer"] p, .stCaption {
        color: var(--gray-600) !important;
        font-size: 0.75rem !important;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

    /* ── Hero ── */
    .palmer-hero {
        padding: 1.8rem 0 2rem 0;
        margin-bottom: 0.5rem;
    }
    .hero-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.11);
        border-radius: 100px;
        padding: 0.3rem 1rem;
        font-size: 0.78rem;
        color: var(--gray-400);
        font-family: var(--font);
        margin-bottom: 1.6rem;
        animation: fadeUp 0.4s ease-out both;
    }
    .pill-dot { color: var(--white); font-size: 0.55rem; }
    .palmer-title {
        font-size: 3.4rem;
        font-weight: 700;
        color: var(--white);
        line-height: 1.08;
        letter-spacing: -0.03em;
        margin: 0 0 1.2rem 0;
        animation: fadeUp 0.5s ease-out 0.1s both;
    }
    .title-dim { color: rgba(255,255,255,0.38); }
    .palmer-subtitle {
        font-size: 1rem;
        color: var(--gray-400);
        max-width: 540px;
        line-height: 1.7;
        margin-bottom: 0.8rem;
        animation: fadeUp 0.5s ease-out 0.2s both;
    }
    .palmer-meta {
        font-size: 0.74rem;
        color: var(--gray-600);
        letter-spacing: 0.03em;
        animation: fadeUp 0.5s ease-out 0.3s both;
    }

    /* ── Risk badges (pill shape) ── */
    .risk-badge {
        display: inline-block;
        padding: 0.22rem 0.8rem;
        border-radius: 100px;
        font-weight: 600;
        font-size: 0.72rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        font-family: var(--font);
        border: 1px solid;
        transition: box-shadow 0.25s;
    }
    .risk-Low      { color: #4ade80; border-color: rgba(74,222,128,0.35);  background: rgba(74,222,128,0.08); }
    .risk-Medium   { color: #fbbf24; border-color: rgba(251,191,36,0.35);  background: rgba(251,191,36,0.08); }
    .risk-High     { color: #fb923c; border-color: rgba(251,146,60,0.35);  background: rgba(251,146,60,0.08); }
    .risk-Critical { color: #f87171; border-color: rgba(248,113,113,0.35); background: rgba(248,113,113,0.08); }

    @keyframes critPulse {
        0%,100% { box-shadow: 0 0 0 0 rgba(248,113,113,0.3); }
        50%      { box-shadow: 0 0 0 5px rgba(248,113,113,0); }
    }
    @keyframes highPulse {
        0%,100% { box-shadow: 0 0 0 0 rgba(251,146,60,0.25); }
        50%      { box-shadow: 0 0 0 4px rgba(251,146,60,0); }
    }
    .risk-Critical { animation: critPulse 2.2s ease-in-out infinite; }
    .risk-High     { animation: highPulse 2.5s ease-in-out infinite; }

    /* ── Finding cards (Palmer dark card style) ── */
    .finding-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-left: 3px solid rgba(255,255,255,0.1);
        padding: 1rem 1.2rem;
        margin: 0.55rem 0;
        border-radius: 14px;
        color: var(--gray-400);
        font-family: var(--font);
        transition: background 0.2s, transform 0.18s, box-shadow 0.2s;
    }
    .finding-card:hover {
        background: var(--bg-card-2);
        transform: translateY(-2px);
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .finding-card.severity-Critical {
        border-left-color: #ef4444;
        border-color: rgba(239,68,68,0.14);
    }
    .finding-card.severity-Critical:hover { box-shadow: 0 10px 30px rgba(239,68,68,0.1); }
    .finding-card.severity-High {
        border-left-color: #f97316;
        border-color: rgba(249,115,22,0.14);
    }
    .finding-card.severity-High:hover { box-shadow: 0 10px 30px rgba(249,115,22,0.1); }
    .finding-card.severity-Medium {
        border-left-color: #eab308;
        border-color: rgba(234,179,8,0.12);
    }
    .finding-card.severity-Low {
        border-left-color: #22c55e;
        border-color: rgba(34,197,94,0.12);
    }

    /* ── Empty state ── */
    .empty-state {
        text-align: center;
        padding: 2.5rem;
        color: var(--gray-600);
        background: var(--bg-card);
        border-radius: 14px;
        border: 1px dashed rgba(255,255,255,0.08);
        font-family: var(--font);
        transition: border-color 0.2s;
    }
    .empty-state:hover { border-color: rgba(255,255,255,0.16); }

    /* ── Animations ── */
    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(12px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes slideLeft {
        from { opacity: 0; transform: translateX(-8px); }
        to   { opacity: 1; transform: translateX(0); }
    }
    @keyframes driftA {
        0%   { transform: translate(0,0) scale(1); }
        100% { transform: translate(-80px, 100px) scale(1.12); }
    }
    @keyframes driftB {
        0%   { transform: translate(0,0) scale(1.05); }
        100% { transform: translate(100px, -70px) scale(0.92); }
    }

    /* ── Custom cursor — white dot via SVG data URL (CSS-only, survives rerenders) ── */
    * {
        cursor: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16'%3E%3Ccircle cx='8' cy='8' r='6' fill='white' fill-opacity='0.95'/%3E%3C/svg%3E") 8 8, auto !important;
    }

    /* ── Hide Streamlit chrome ── */
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
    </style>

    <script>
    /* Mouse spotlight glow — follows cursor, survives rerenders via interval check */
    (function () {
        function initGlow() {
            if (document.getElementById('cur-glow')) return;
            const glow = document.createElement('div');
            glow.id = 'cur-glow';
            glow.style.cssText = [
                'position:fixed',
                'width:500px', 'height:500px',
                'border-radius:50%',
                'pointer-events:none',
                'z-index:0',
                'transform:translate(-50%,-50%)',
                'background:radial-gradient(circle,rgba(255,255,255,0.044) 0%,transparent 65%)',
                'filter:blur(30px)',
                'transition:left 0.13s ease-out,top 0.13s ease-out,opacity 0.3s',
                'will-change:left,top',
                'left:-600px', 'top:-600px'
            ].join(';');
            document.body.appendChild(glow);

            document.addEventListener('mousemove', (e) => {
                glow.style.left = e.clientX + 'px';
                glow.style.top  = e.clientY + 'px';
            });
            document.addEventListener('mouseleave', () => { glow.style.opacity = '0'; });
            document.addEventListener('mouseenter', () => { glow.style.opacity = '1'; });
        }
        initGlow();
        setInterval(initGlow, 2000);
    })();
    </script>
    """,
    unsafe_allow_html=True,
)


# ----- Sidebar -----

with st.sidebar:
    st.markdown("### 🔑 API Configuration")
    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="Paste your API key...",
        help="Your key is held in browser memory only. Never stored, never logged.",
    )

    if not api_key:
        st.info(
            "**Don't have a key?**  \n"
            "Get one at [console.anthropic.com](https://console.anthropic.com) — "
            "pay-as-you-go. Typical cost: ~\\$0.07 per report on Haiku, ~\\$0.21 on Sonnet."
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
        "Built by [Kaps](https://www.linkedin.com/in/kapil-chaudhary-cyber-security/) · "
        "[Rapid Grasper](https://youtube.com/@rapidgrasper)"
    )


# ----- Main Content -----

st.markdown(
    """
    <div class="palmer-hero">
        <div class="hero-pill"><span class="pill-dot">●</span> Vendor Risk Intelligence</div>
        <div class="palmer-title">SOC 2 Reports.<br><span class="title-dim">Analyzed in 30 seconds.</span></div>
        <div class="palmer-subtitle">Upload any vendor's SOC 2 Type II PDF and get a structured risk assessment — exceptions, red flags, CUECs, and recommended follow-up questions.</div>
        <div class="palmer-meta">Free &nbsp;·&nbsp; Bring your own API key &nbsp;·&nbsp; Zero data retention &nbsp;·&nbsp; Open source</div>
    </div>
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
    analyze_disabled = not api_key
    if analyze_disabled:
        st.info("👈 Add your Anthropic API key in the sidebar to analyze.")

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
        1. Paste your Anthropic API key in the sidebar (~\\$0.07 per report on Haiku)<br/>
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
