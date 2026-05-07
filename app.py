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

# ----- Cybersecurity Theme: CSS + Matrix Rain -----

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap');

    /* ── Design tokens ── */
    :root {
        --green:       #00ff41;
        --green-dim:   rgba(0,255,65,0.12);
        --green-glow:  0 0 8px rgba(0,255,65,0.5), 0 0 20px rgba(0,255,65,0.2);
        --cyan:        #00e5ff;
        --cyan-dim:    rgba(0,229,255,0.12);
        --cyan-glow:   0 0 8px rgba(0,229,255,0.5), 0 0 20px rgba(0,229,255,0.2);
        --red:         #ff3333;
        --orange:      #ff6600;
        --yellow:      #ffaa00;
        --bg:          #0a0e1a;
        --bg-card:     #0d1117;
        --bg-sidebar:  #080c14;
        --border:      rgba(0,255,65,0.14);
        --text:        #b0bec5;
        --text-dim:    #4a5568;
        --font:        'JetBrains Mono', 'Courier New', monospace;
    }

    /* ── Base ── */
    .stApp, body {
        background-color: var(--bg) !important;
        font-family: var(--font) !important;
        color: var(--text) !important;
    }

    /* ── Subtle scanlines overlay ── */
    .stApp::before {
        content: '';
        position: fixed;
        inset: 0;
        background: repeating-linear-gradient(
            0deg,
            transparent,
            transparent 3px,
            rgba(0,255,65,0.013) 3px,
            rgba(0,255,65,0.013) 4px
        );
        pointer-events: none;
        z-index: 9998;
    }

    /* ── Layout ── */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1100px;
        animation: fadeInUp 0.55s ease-out both;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: var(--bg-sidebar) !important;
        border-right: 1px solid var(--border) !important;
        animation: sidebarFade 0.5s ease-out both;
    }
    [data-testid="stSidebar"]::before {
        content: '';
        display: block;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--green), transparent);
        margin-bottom: 0.25rem;
    }
    [data-testid="stSidebar"] h3 {
        color: var(--green) !important;
        font-size: 0.75rem !important;
        letter-spacing: 0.18em !important;
        text-transform: uppercase !important;
    }

    /* ── Text input (API key) ── */
    [data-testid="stTextInput"] input {
        background: #05080f !important;
        border: 1px solid var(--border) !important;
        color: var(--green) !important;
        font-family: var(--font) !important;
        border-radius: 2px !important;
        caret-color: var(--green);
    }
    [data-testid="stTextInput"] input:focus {
        border-color: var(--green) !important;
        box-shadow: var(--green-glow) !important;
        outline: none !important;
    }
    [data-testid="stTextInput"] input::placeholder { color: var(--text-dim) !important; }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        background: rgba(0,255,65,0.02) !important;
        border: 1px dashed rgba(0,255,65,0.28) !important;
        border-radius: 4px !important;
        transition: border-color 0.25s, box-shadow 0.25s;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: var(--green) !important;
        box-shadow: var(--green-glow) !important;
    }

    /* ── Primary button ── */
    .stButton > button[kind="primary"] {
        background: transparent !important;
        border: 1px solid var(--green) !important;
        color: var(--green) !important;
        font-family: var(--font) !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        letter-spacing: 0.12em !important;
        text-transform: uppercase !important;
        border-radius: 2px !important;
        transition: background 0.2s, box-shadow 0.2s, transform 0.15s;
    }
    .stButton > button[kind="primary"]:hover:not(:disabled) {
        background: var(--green-dim) !important;
        box-shadow: var(--green-glow) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button[kind="primary"]:disabled {
        border-color: var(--text-dim) !important;
        color: var(--text-dim) !important;
        opacity: 0.5 !important;
    }

    /* ── Download button ── */
    .stDownloadButton > button {
        background: transparent !important;
        border: 1px solid rgba(0,229,255,0.45) !important;
        color: var(--cyan) !important;
        font-family: var(--font) !important;
        font-size: 0.8rem !important;
        letter-spacing: 0.08em !important;
        border-radius: 2px !important;
        transition: background 0.2s, box-shadow 0.2s;
    }
    .stDownloadButton > button:hover {
        background: var(--cyan-dim) !important;
        box-shadow: var(--cyan-glow) !important;
    }

    /* ── Tabs ── */
    [data-baseweb="tab-list"] {
        background: transparent !important;
        border-bottom: 1px solid var(--border) !important;
        gap: 0 !important;
    }
    [data-baseweb="tab"] {
        background: transparent !important;
        color: var(--text-dim) !important;
        font-family: var(--font) !important;
        font-size: 0.77rem !important;
        letter-spacing: 0.06em !important;
        border-bottom: 2px solid transparent !important;
        padding: 0.5rem 1.1rem !important;
        transition: color 0.2s, border-color 0.2s !important;
    }
    [data-baseweb="tab"]:hover { color: var(--green) !important; }
    [aria-selected="true"][data-baseweb="tab"] {
        color: var(--green) !important;
        border-bottom-color: var(--green) !important;
        text-shadow: 0 0 8px rgba(0,255,65,0.6);
    }

    /* ── Metrics ── */
    [data-testid="stMetric"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 3px !important;
        padding: 0.7rem 1rem !important;
    }
    [data-testid="stMetricLabel"] p {
        color: var(--text-dim) !important;
        font-size: 0.68rem !important;
        letter-spacing: 0.14em !important;
        text-transform: uppercase !important;
    }
    [data-testid="stMetricValue"] {
        color: var(--green) !important;
        font-size: 0.95rem !important;
    }

    /* ── Headings ── */
    h1, h2, h3 { font-family: var(--font) !important; }
    h2 {
        color: var(--cyan) !important;
        margin-top: 2rem;
        border-bottom: 1px solid var(--border);
        padding-bottom: 0.4rem;
        letter-spacing: 0.06em;
    }
    h3 { color: var(--cyan) !important; letter-spacing: 0.04em; }

    /* ── Expander ── */
    [data-testid="stExpander"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 3px !important;
    }
    [data-testid="stExpander"] summary p { color: var(--cyan) !important; }

    /* ── Inline code ── */
    code {
        background: rgba(0,255,65,0.07) !important;
        color: var(--green) !important;
        border: 1px solid rgba(0,255,65,0.18) !important;
        border-radius: 2px !important;
        padding: 0.1rem 0.35rem !important;
        font-family: var(--font) !important;
    }

    /* ── HR ── */
    hr { border-color: var(--border) !important; }

    /* ── Caption ── */
    [data-testid="stCaptionContainer"] p, .stCaption {
        color: var(--text-dim) !important;
        font-family: var(--font) !important;
        font-size: 0.72rem !important;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: rgba(0,255,65,0.2); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(0,255,65,0.4); }

    /* ── Hero ── */
    .hero-wrap {
        padding: 1.2rem 0 1.4rem 0;
        border-bottom: 1px solid var(--border);
        margin-bottom: 1.5rem;
    }
    .terminal-prompt {
        font-size: 0.76rem;
        color: var(--text-dim);
        line-height: 1.7;
        margin-bottom: 0.9rem;
        animation: fadeInUp 0.4s ease-out both;
    }
    .prompt-symbol { color: var(--green); }
    .prompt-path   { color: var(--cyan); }
    .prompt-flag   { color: #ffaa00; }

    @keyframes glitch {
        0%,89%,100% {
            text-shadow: 0 0 18px rgba(0,255,65,0.45), 0 0 36px rgba(0,255,65,0.15);
            transform: translate(0,0);
            filter: none;
        }
        90% {
            text-shadow: -3px 0 rgba(255,0,80,0.9), 3px 0 rgba(0,229,255,0.9);
            transform: translate(2px,0);
            filter: brightness(1.2);
        }
        92% {
            text-shadow: 3px 0 rgba(255,0,80,0.9), -3px 0 rgba(0,229,255,0.9);
            transform: translate(-2px,0);
        }
        94% {
            text-shadow: 0 0 18px rgba(0,255,65,0.45);
            transform: translate(0,0);
        }
    }
    .main-title {
        font-size: 2.7rem;
        font-weight: 700;
        color: #e8f5e9;
        letter-spacing: 0.06em;
        line-height: 1.1;
        animation: glitch 7s ease-in-out 1s infinite, fadeInUp 0.5s ease-out 0.1s both;
    }
    .hero-subtitle {
        font-size: 0.95rem;
        color: var(--text);
        margin-top: 0.6rem;
        animation: fadeInUp 0.5s ease-out 0.25s both;
    }
    .hero-tagline {
        font-size: 0.72rem;
        color: var(--green);
        letter-spacing: 0.18em;
        margin-top: 0.5rem;
        animation: fadeInUp 0.5s ease-out 0.4s both;
    }
    .cursor {
        display: inline-block;
        width: 9px; height: 1em;
        background: var(--green);
        vertical-align: text-bottom;
        margin-left: 2px;
        box-shadow: 0 0 6px var(--green);
        animation: blink 1s step-end infinite;
    }
    @keyframes blink { 50% { opacity: 0; } }

    /* ── Risk badges ── */
    .risk-badge {
        display: inline-block;
        padding: 0.28rem 0.85rem;
        border-radius: 2px;
        font-weight: 700;
        font-size: 0.75rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        font-family: var(--font);
        border: 1px solid;
        transition: box-shadow 0.2s;
    }
    .risk-Low      { color: #39ff14; border-color: #39ff14; background: rgba(57,255,20,0.07); }
    .risk-Medium   { color: #ffaa00; border-color: #ffaa00; background: rgba(255,170,0,0.07); }
    .risk-High     { color: #ff6600; border-color: #ff6600; background: rgba(255,102,0,0.07); }
    .risk-Critical { color: #ff3333; border-color: #ff3333; background: rgba(255,51,51,0.07); }

    @keyframes critPulse {
        0%,100% { box-shadow: 0 0 5px rgba(255,51,51,0.45), 0 0 14px rgba(255,51,51,0.2); }
        50%      { box-shadow: 0 0 12px rgba(255,51,51,0.8), 0 0 28px rgba(255,51,51,0.4); }
    }
    @keyframes highPulse {
        0%,100% { box-shadow: 0 0 5px rgba(255,102,0,0.4); }
        50%      { box-shadow: 0 0 12px rgba(255,102,0,0.75), 0 0 24px rgba(255,102,0,0.3); }
    }
    .risk-Critical { animation: critPulse 2s ease-in-out infinite; }
    .risk-High     { animation: highPulse 2.3s ease-in-out infinite; }

    /* ── Finding cards ── */
    .finding-card {
        background: rgba(0,255,65,0.018);
        border: 1px solid rgba(0,255,65,0.1);
        border-left: 3px solid rgba(0,255,65,0.3);
        padding: 0.85rem 1rem;
        margin: 0.5rem 0;
        border-radius: 2px;
        font-family: var(--font);
        color: var(--text);
        transition: transform 0.18s, box-shadow 0.18s, background 0.18s;
    }
    .finding-card:hover {
        transform: translateX(5px);
        background: rgba(0,255,65,0.035);
    }
    .finding-card.severity-Critical {
        border-left-color: #ff3333;
        border-color: rgba(255,51,51,0.18);
        background: rgba(255,51,51,0.025);
    }
    .finding-card.severity-Critical:hover { box-shadow: 0 0 14px rgba(255,51,51,0.22); }
    .finding-card.severity-High {
        border-left-color: #ff6600;
        border-color: rgba(255,102,0,0.18);
        background: rgba(255,102,0,0.025);
    }
    .finding-card.severity-High:hover { box-shadow: 0 0 14px rgba(255,102,0,0.22); }
    .finding-card.severity-Medium {
        border-left-color: #ffaa00;
        border-color: rgba(255,170,0,0.18);
        background: rgba(255,170,0,0.02);
    }
    .finding-card.severity-Low {
        border-left-color: #39ff14;
        border-color: rgba(57,255,20,0.18);
        background: rgba(57,255,20,0.015);
    }

    /* ── Empty state ── */
    .empty-state {
        text-align: center;
        padding: 2rem;
        color: var(--text-dim);
        background: var(--bg-card);
        border-radius: 2px;
        border: 1px dashed rgba(0,255,65,0.2);
        font-family: var(--font);
        transition: border-color 0.2s;
    }
    .empty-state:hover { border-color: rgba(0,255,65,0.45); }

    /* ── Animations ── */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(14px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes sidebarFade {
        from { opacity: 0; transform: translateX(-8px); }
        to   { opacity: 1; transform: translateX(0); }
    }

    /* ── Hide Streamlit chrome ── */
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
    </style>

    <script>
    /* Matrix rain canvas — injected once, persists across Streamlit rerenders */
    (function () {
        if (document.getElementById('matrix-bg')) return;
        const c = document.createElement('canvas');
        c.id = 'matrix-bg';
        c.style.cssText = [
            'position:fixed', 'top:0', 'left:0',
            'width:100vw', 'height:100vh',
            'z-index:0', 'pointer-events:none', 'opacity:0.055'
        ].join(';');
        document.body.prepend(c);
        const ctx = c.getContext('2d');
        const resize = () => { c.width = innerWidth; c.height = innerHeight; };
        resize();
        window.addEventListener('resize', resize);
        const CHARS = '01アイウカキクコサシスABCDEFGHIJKLM{}[]<>/\\|_=+';
        const FS = 13;
        let cols, drops;
        const init = () => {
            cols = Math.floor(c.width / FS);
            drops = Array.from({length: cols}, () => Math.random() * -(c.height / FS));
        };
        init();
        window.addEventListener('resize', init);
        setInterval(() => {
            ctx.fillStyle = 'rgba(10,14,26,0.055)';
            ctx.fillRect(0, 0, c.width, c.height);
            ctx.font = FS + 'px monospace';
            drops.forEach((y, i) => {
                ctx.fillStyle = Math.random() > 0.97 ? '#e8f5e9' : '#00ff41';
                ctx.fillText(CHARS[Math.floor(Math.random() * CHARS.length)], i * FS, y * FS);
                if (y * FS > c.height && Math.random() > 0.975) drops[i] = 0;
                drops[i] += 0.6;
            });
        }, 55);
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
        "Built by [Kaps](https://www.linkedin.com/in/kapil-chaudhary-cyber-security/) · "
        "[Rapid Grasper](https://youtube.com/@rapidgrasper)"
    )


# ----- Main Content -----

st.markdown(
    """
    <div class="hero-wrap">
        <div class="terminal-prompt">
            <span class="prompt-symbol">┌──(</span><span class="prompt-path">kaps@soc2-analyzer</span><span class="prompt-symbol">)-[</span><span class="prompt-flag">~/vendor-risk</span><span class="prompt-symbol">]</span><br>
            <span class="prompt-symbol">└─$</span> <span class="prompt-flag">soc2-analyzer</span> <span class="prompt-path">--mode</span> analyze <span class="prompt-path">--output</span> structured-json<span class="cursor"> </span>
        </div>
        <div class="main-title">🛡️ SOC 2 ANALYZER</div>
        <div class="hero-subtitle">Drop a vendor SOC 2 Type II PDF · Get a structured risk assessment in 30 seconds.</div>
        <div class="hero-tagline">[ FREE &nbsp;·&nbsp; BYOK &nbsp;·&nbsp; ZERO DATA RETENTION &nbsp;·&nbsp; OPEN SOURCE ]</div>
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
