import streamlit as st
import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="OncoTriage Assistant",
    page_icon="🩺",
    layout="centered",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
section.main > div { max-width: 720px; margin: 0 auto; }
.card-hdr { display:flex; align-items:center; gap:10px; margin-bottom:12px; }
.icon-box {
    width:28px; height:28px; border-radius:6px; background:#e1f5ee;
    display:flex; align-items:center; justify-content:center; font-size:14px; flex-shrink:0;
}
.icon-box.danger { background:#fcebeb; }
.card-title { font-size:14px; font-weight:600; color:var(--text-color); margin:0; }
.card-sub   { font-size:12px; color:var(--text-color); opacity:0.6; margin:0; }
.sym-grid   { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:4px; }
.sym-btn    { display:flex; align-items:center; gap:8px; padding:9px 12px;
              border:1px solid rgba(128,128,128,0.25); border-radius:8px;
              font-size:13px; color:var(--text-color); background:transparent; }
.sym-btn.active   { background:#e1f5ee; border-color:#5dcaa5; color:#085041; font-weight:500; }
.sym-btn.disabled { opacity:0.38; }
.soon-badge { margin-left:auto; font-size:10px; padding:2px 6px;
              background:rgba(128,128,128,0.15); border-radius:4px;
              color:var(--text-color); opacity:0.55; }
.urg-badge  { display:inline-flex; align-items:center; gap:5px; font-size:12px;
              padding:4px 10px; border-radius:8px; background:#fcebeb; color:#a32d2d; font-weight:500; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for k, v in {
    "summary": None,
    "summary_had_flags": False,
    "med_nothing": False,
    "med_tylenol": False,
    "med_nsaid": False,
    "med_rx": False,
    "med_antiemetic": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Med mutual-exclusivity callbacks ──────────────────────────────────────────
MED_KEYS = ["med_tylenol", "med_nsaid", "med_rx", "med_antiemetic"]

def on_med():
    if any(st.session_state[k] for k in MED_KEYS):
        st.session_state["med_nothing"] = False

def on_nothing():
    if st.session_state["med_nothing"]:
        for k in MED_KEYS:
            st.session_state[k] = False

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
  <div style="width:32px;height:32px;border-radius:8px;background:#e1f5ee;
       display:flex;align-items:center;justify-content:center;font-size:18px;">🩺</div>
  <span style="font-size:18px;font-weight:500;color:var(--text-color);">OncoTriage Assistant</span>
</div>
<p style="font-size:13px;color:var(--text-color);opacity:0.6;margin-bottom:1rem;">
  Structured symptom screener — complete all sections, then generate a provider-ready summary
</p>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# 1. PATIENT CONTEXT
# ─────────────────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("""
    <div class="card-hdr">
      <div class="icon-box">👤</div>
      <div><div class="card-title">Patient context</div>
           <div class="card-sub">Demographics &amp; treatment status</div></div>
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    age = c1.number_input("Age *", min_value=18, max_value=110, value=None,
                          placeholder="e.g. 58", step=1)
    dx  = c2.text_input("Cancer diagnosis *", placeholder="e.g. NSCLC")
    tx  = c3.selectbox("Current treatment *", [
        "", "Chemotherapy", "Immunotherapy", "Targeted therapy",
        "Radiation", "Combination", "Supportive care only",
    ])
    last_tx = st.text_input("Last treatment date", placeholder="e.g. 4 days ago / June 3")

# ─────────────────────────────────────────────────────────────────────────────
# 2. CHIEF COMPLAINT
# ─────────────────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("""
    <div class="card-hdr">
      <div class="icon-box">📋</div>
      <div><div class="card-title">Chief complaint</div>
           <div class="card-sub">Select symptom to activate screener</div></div>
    </div>
    <div class="sym-grid">
      <div class="sym-btn active">🧠 Headache</div>
      <div class="sym-btn disabled">💧 Nausea / vomiting <span class="soon-badge">soon</span></div>
      <div class="sym-btn disabled">🏃 Muscle pain / myalgia <span class="soon-badge">soon</span></div>
      <div class="sym-btn disabled">🌊 Diarrhea <span class="soon-badge">soon</span></div>
      <div class="sym-btn disabled">🩸 Bleeding / bruising <span class="soon-badge">soon</span></div>
      <div class="sym-btn disabled">⚡ Fatigue / weakness <span class="soon-badge">soon</span></div>
      <div class="sym-btn disabled">💨 Shortness of breath <span class="soon-badge">soon</span></div>
      <div class="sym-btn disabled">🌡️ Fever / chills <span class="soon-badge">soon</span></div>
    </div>
    <hr style="margin:14px 0;border-color:#e5e7eb;">
    """, unsafe_allow_html=True)

    location = st.multiselect("Location *", [
        "Frontal", "Occipital", "Temporal (bilateral)",
        "Temporal (unilateral)", "Vertex", "Diffuse / whole head", "Behind the eyes",
    ])
    onset_txt = st.text_input("Onset *", placeholder="e.g. yesterday evening")

    onset_char = st.radio("Onset character",
        ["Gradual", "Sudden", "Intermittent"],
        horizontal=True, index=None)
    trajectory = st.radio("Trajectory",
        ["Worsening", "Stable", "Improving"],
        horizontal=True, index=None)

# ─────────────────────────────────────────────────────────────────────────────
# 3. SEVERITY
# ─────────────────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("""
    <div class="card-hdr">
      <div class="icon-box">🎛️</div>
      <div><div class="card-title">Severity</div>
           <div class="card-sub">Numeric pain scale</div></div>
    </div>""", unsafe_allow_html=True)

    pain = st.slider("Pain score (0–10) *", 0, 10, 5)

# ─────────────────────────────────────────────────────────────────────────────
# 4. ASSOCIATED SYMPTOMS
# ─────────────────────────────────────────────────────────────────────────────
ASSOC = [
    "Nausea", "Vomiting", "Dizziness / vertigo", "Vision changes",
    "Confusion / AMS", "Focal weakness", "Neck stiffness", "Photophobia",
]

with st.container(border=True):
    st.markdown("""
    <div class="card-hdr">
      <div class="icon-box">☑️</div>
      <div><div class="card-title">Associated symptoms</div>
           <div class="card-sub">Select all that apply</div></div>
    </div>""", unsafe_allow_html=True)

    assoc_sel = []
    ac1, ac2 = st.columns(2)
    for i, opt in enumerate(ASSOC):
        if (ac1 if i % 2 == 0 else ac2).checkbox(opt, key=f"assoc_{i}"):
            assoc_sel.append(opt)

# ─────────────────────────────────────────────────────────────────────────────
# 5. MEDICATIONS
# ─────────────────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("""
    <div class="card-hdr">
      <div class="icon-box">💊</div>
      <div><div class="card-title">Medications tried</div>
           <div class="card-sub">Select all taken</div></div>
    </div>""", unsafe_allow_html=True)

    mc1, mc2 = st.columns(2)
    mc1.checkbox("Acetaminophen (Tylenol)", key="med_tylenol",    on_change=on_med)
    mc2.checkbox("Ibuprofen / NSAID",       key="med_nsaid",      on_change=on_med)
    mc1.checkbox("Prescribed pain med",     key="med_rx",         on_change=on_med)
    mc2.checkbox("Antiemetic",              key="med_antiemetic", on_change=on_med)
    mc1.checkbox("Nothing tried yet",       key="med_nothing",    on_change=on_nothing)

    meds_sel = [
        label for key, label in [
            ("med_tylenol",    "Acetaminophen (Tylenol)"),
            ("med_nsaid",      "Ibuprofen / NSAID"),
            ("med_rx",         "Prescribed pain med"),
            ("med_antiemetic", "Antiemetic"),
        ] if st.session_state[key]
    ]

    med_time_str = ""
    med_help = None
    if meds_sel:
        st.markdown(
            '<div style="background:#f9fafb;border-radius:8px;padding:10px;margin-top:8px;'
            'display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text-color);opacity:0.6;">⏱️ Last dose</div>',
            unsafe_allow_html=True,
        )
        mt_c1, mt_c2 = st.columns([1, 2])
        med_time_str = mt_c1.text_input("Time", placeholder="e.g. 2:30 PM",
                                         label_visibility="collapsed", key="med_time_val")
        med_help = st.radio("Did medication help?",
            ["Yes — some relief", "No relief", "Partial relief"],
            horizontal=True, index=None, key="med_help_radio")

# ─────────────────────────────────────────────────────────────────────────────
# 6. SAFETY FLAGS
# ─────────────────────────────────────────────────────────────────────────────
FLAGS = [
    "Fever (≥100.4°F)",        "Worst headache of life",
    "Uncontrolled vomiting",   "New neurological deficits",
    "Altered consciousness",   "Recent fall or head trauma",
]

with st.container(border=True):
    st.markdown("""
    <div class="card-hdr">
      <div class="icon-box danger">⚠️</div>
      <div><div class="card-title">Safety flags</div>
           <div class="card-sub">Select all present — triggers urgent review</div></div>
    </div>""", unsafe_allow_html=True)

    flags_sel = []
    fc1, fc2 = st.columns(2)
    for i, opt in enumerate(FLAGS):
        if (fc1 if i % 2 == 0 else fc2).checkbox(opt, key=f"flag_{i}"):
            flags_sel.append(opt)

# ─────────────────────────────────────────────────────────────────────────────
# 7. NURSE NOTE
# ─────────────────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("""
    <div class="card-hdr">
      <div class="icon-box">📝</div>
      <div><div class="card-title">Nurse note</div>
           <div class="card-sub">Free-text observations</div></div>
    </div>""", unsafe_allow_html=True)

    nurse_note = st.text_area(
        "note", label_visibility="collapsed",
        placeholder="Additional observations, patient demeanor, prior similar episodes, recent labs…",
    )

# ─────────────────────────────────────────────────────────────────────────────
# GENERATE
# ─────────────────────────────────────────────────────────────────────────────
required_ok = bool(age is not None and dx and tx and location and onset_txt)

generate = st.button(
    "✨  Generate provider summary",
    type="primary", use_container_width=True,
    disabled=not required_ok,
)
if not required_ok:
    st.caption("Complete required fields (age, diagnosis, treatment, headache location, onset) to enable.")

if generate:
    prompt = (
        "You are a clinical documentation assistant helping oncology nurses write concise, "
        "provider-ready triage summaries. Write in professional clinical language, past tense, "
        "third person. Be factual and concise — one paragraph, 3–5 sentences. Include: chief "
        "complaint with timing and severity, treatment context, associated symptoms, medications "
        "tried with timing and effect, safety flags if present, and end with a clear request for "
        "provider review. Do not add recommendations or diagnoses.\n\n"
        f"Triage data:\n"
        f"- Patient: {int(age)} y/o with {dx}, on {tx}"
        f"{f', last treatment {last_tx}' if last_tx else ''}\n"
        f"- Chief complaint: Headache — {', '.join(location)}, onset {onset_txt}"
        f"{f', {onset_char}' if onset_char else ''}{f', {trajectory}' if trajectory else ''}\n"
        f"- Pain: {pain}/10\n"
        f"- Associated symptoms: {', '.join(assoc_sel) if assoc_sel else 'none reported'}\n"
        f"- Medications: {', '.join(meds_sel) if meds_sel else 'none'}"
        f"{f' (last taken {med_time_str})' if med_time_str else ''}"
        f"{f', {med_help}' if med_help else ''}\n"
        f"- Safety flags: {', '.join(flags_sel) if flags_sel else 'none'}\n"
        f"- Nurse note: {nurse_note or 'none'}\n\n"
        "Write the provider summary now:"
    )

    api_key = os.getenv("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY", None)

    if not api_key:
        st.error("⚠️ ANTHROPIC_API_KEY not set. Add it to `.env` (local) or Streamlit Secrets (cloud).")
    else:
        with st.spinner("Generating summary…"):
            try:
                client = anthropic.Anthropic(api_key=api_key)
                msg = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}],
                )
                st.session_state["summary"] = msg.content[0].text
                st.session_state["summary_had_flags"] = bool(flags_sel)
            except Exception as e:
                st.session_state["summary"] = f"API error: {e}"
                st.session_state["summary_had_flags"] = False

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY OUTPUT
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state["summary"]:
    with st.container(border=True):
        h1, h2 = st.columns([3, 2])
        h1.markdown("**PROVIDER SUMMARY**")
        if st.session_state["summary_had_flags"]:
            h2.markdown(
                '<div style="text-align:right">'
                '<span class="urg-badge">⚠️ Urgent flags present</span></div>',
                unsafe_allow_html=True,
            )
        st.code(st.session_state["summary"], language=None)
