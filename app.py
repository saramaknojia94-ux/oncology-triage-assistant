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
.icon-box.warn   { background:#fff8e1; }
.card-title { font-size:14px; font-weight:600; color:var(--text-color); margin:0; }
.card-sub   { font-size:12px; color:var(--text-color); opacity:0.6; margin:0; }
.sym-grid   { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:4px; }
.sym-btn    { display:flex; align-items:center; gap:8px; padding:9px 12px;
              border:1px solid rgba(128,128,128,0.25); border-radius:8px;
              font-size:13px; color:var(--text-color); background:transparent; }
.sym-btn.disabled { opacity:0.38; }
.soon-badge { margin-left:auto; font-size:10px; padding:2px 6px;
              background:rgba(128,128,128,0.15); border-radius:4px;
              color:var(--text-color); opacity:0.55; }
.urg-badge  { display:inline-flex; align-items:center; gap:5px; font-size:12px;
              padding:4px 10px; border-radius:8px; background:#fcebeb; color:#a32d2d; font-weight:500; }
.auto-flag  { background:#fff3cd; border-left:3px solid #ffc107; padding:5px 10px;
              border-radius:0 4px 4px 0; font-size:12px; margin:3px 0; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
NV_ANTIEMETIC_KEYS = [
    ("nv_med_ondansetron",      "Ondansetron (Zofran)"),
    ("nv_med_prochlorperazine", "Prochlorperazine (Compazine)"),
    ("nv_med_promethazine",     "Promethazine (Phenergan)"),
    ("nv_med_metoclopramide",   "Metoclopramide (Reglan)"),
    ("nv_med_olanzapine",       "Olanzapine (Zyprexa)"),
    ("nv_med_dexamethasone",    "Dexamethasone"),
    ("nv_med_lorazepam",        "Lorazepam (Ativan)"),
    ("nv_med_aprepitant",       "Aprepitant (Emend)"),
    ("nv_med_scopolamine",      "Scopolamine patch"),
    ("nv_med_meclizine",        "Meclizine"),
    ("nv_med_dramamine",        "Dramamine"),
    ("nv_med_ginger",           "Ginger (tea / supplement)"),
    ("nv_med_pepto",            "Pepto-Bismol"),
    ("nv_med_other",            "Other"),
]
NV_ACTUAL_MED_KEYS = [k for k, _ in NV_ANTIEMETIC_KEYS]

_defaults = {
    "summary": None,
    "summary_had_flags": False,
    # headache meds
    "med_nothing": False,
    "med_tylenol": False,
    "med_nsaid": False,
    "med_rx": False,
    "med_antiemetic": False,
    # N/V meds
    "nv_med_nothing": False,
}
for _k in NV_ACTUAL_MED_KEYS:
    _defaults[_k] = False

for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Headache med callbacks ────────────────────────────────────────────────────
HA_MED_KEYS = ["med_tylenol", "med_nsaid", "med_rx", "med_antiemetic"]

def on_med():
    if any(st.session_state[k] for k in HA_MED_KEYS):
        st.session_state["med_nothing"] = False

def on_nothing():
    if st.session_state["med_nothing"]:
        for k in HA_MED_KEYS:
            st.session_state[k] = False

# ── N/V med callbacks ─────────────────────────────────────────────────────────
def on_nv_med():
    if any(st.session_state[k] for k in NV_ACTUAL_MED_KEYS):
        st.session_state["nv_med_nothing"] = False

def on_nv_nothing():
    if st.session_state["nv_med_nothing"]:
        for k in NV_ACTUAL_MED_KEYS:
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
# SHARED: PATIENT CONTEXT
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
        "", "Chemotherapy", "Immunotherapy", "Targeted therapy", "Oral chemotherapy",
        "Radiation therapy", "Hormonal therapy", "Recent surgery",
        "Stem cell transplant / CAR-T", "Combination", "Supportive care only", "Other",
    ])
    last_tx = st.text_input("Last treatment date", placeholder="e.g. 4 days ago / June 3")

# ─────────────────────────────────────────────────────────────────────────────
# SHARED: SYMPTOM SELECTOR
# ─────────────────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("""
    <div class="card-hdr">
      <div class="icon-box">📋</div>
      <div><div class="card-title">Chief complaint</div>
           <div class="card-sub">Select active symptom screener</div></div>
    </div>""", unsafe_allow_html=True)

    active_symptom = st.radio(
        "symptom",
        ["Headache", "Nausea / Vomiting"],
        horizontal=True,
        label_visibility="collapsed",
        key="active_symptom_sel",
    )

    st.markdown("""
    <div class="sym-grid" style="margin-top:10px;">
      <div class="sym-btn disabled">🏃 Muscle pain / myalgia <span class="soon-badge">soon</span></div>
      <div class="sym-btn disabled">🌊 Diarrhea <span class="soon-badge">soon</span></div>
      <div class="sym-btn disabled">🩸 Bleeding / bruising <span class="soon-badge">soon</span></div>
      <div class="sym-btn disabled">⚡ Fatigue / weakness <span class="soon-badge">soon</span></div>
      <div class="sym-btn disabled">💨 Shortness of breath <span class="soon-badge">soon</span></div>
      <div class="sym-btn disabled">🌡️ Fever / chills <span class="soon-badge">soon</span></div>
    </div>
    """, unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# SCREENER: HEADACHE
# ═════════════════════════════════════════════════════════════════════════════
if active_symptom == "Headache":

    with st.container(border=True):
        st.markdown("""
        <div class="card-hdr">
          <div class="icon-box">🧠</div>
          <div><div class="card-title">Headache details</div>
               <div class="card-sub">Location, onset, character</div></div>
        </div>
        <hr style="margin:0 0 14px 0;border-color:#e5e7eb;">
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

    with st.container(border=True):
        st.markdown("""
        <div class="card-hdr">
          <div class="icon-box">🎛️</div>
          <div><div class="card-title">Severity</div>
               <div class="card-sub">Numeric pain scale</div></div>
        </div>""", unsafe_allow_html=True)
        pain = st.slider("Pain score (0–10) *", 0, 10, 5)

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
            if (ac1 if i % 2 == 0 else ac2).checkbox(opt, key=f"ha_assoc_{i}"):
                assoc_sel.append(opt)

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
                'display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text-color);'
                'opacity:0.6;">⏱️ Last dose</div>',
                unsafe_allow_html=True,
            )
            mt_c1, mt_c2 = st.columns([1, 2])
            med_time_str = mt_c1.text_input("Time", placeholder="e.g. 2:30 PM",
                                             label_visibility="collapsed", key="med_time_val")
            med_help = st.radio("Did medication help?",
                ["Yes — some relief", "No relief", "Partial relief"],
                horizontal=True, index=None, key="med_help_radio")

    FLAGS = [
        "Fever (≥100.4°F)",       "Worst headache of life",
        "Uncontrolled vomiting",  "New neurological deficits",
        "Altered consciousness",  "Recent fall or head trauma",
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
            if (fc1 if i % 2 == 0 else fc2).checkbox(opt, key=f"ha_flag_{i}"):
                flags_sel.append(opt)

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

    required_ok = bool(age is not None and dx and tx and location and onset_txt)
    generate = st.button("✨  Generate provider summary", type="primary",
                         use_container_width=True, disabled=not required_ok)
    if not required_ok:
        st.caption("Complete required fields (age, diagnosis, treatment, headache location, onset) to enable.")

    if generate:
        prompt = (
            "You are a clinical documentation assistant helping oncology nurses write concise, "
            "provider-ready triage summaries. Write in professional clinical language, past tense, "
            "third person. One paragraph, 3–5 sentences. Include: chief complaint with timing and "
            "severity, treatment context, associated symptoms, medications tried with effect, safety "
            "flags if present, end with a clear request for provider review. "
            "Do not add recommendations or diagnoses.\n\n"
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
            st.error("⚠️ ANTHROPIC_API_KEY not set.")
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

# ═════════════════════════════════════════════════════════════════════════════
# SCREENER: NAUSEA / VOMITING
# ═════════════════════════════════════════════════════════════════════════════
elif active_symptom == "Nausea / Vomiting":

    # Treatment context (CINV classification)
    with st.container(border=True):
        st.markdown("""
        <div class="card-hdr">
          <div class="icon-box">💉</div>
          <div><div class="card-title">Treatment context</div>
               <div class="card-sub">Used to classify CINV type and risk</div></div>
        </div>""", unsafe_allow_html=True)

        tc1, tc2, tc3 = st.columns(3)
        nv_regimen = tc1.text_input("Regimen name", placeholder="e.g. FOLFOX, AC-T")
        nv_cycle   = tc2.number_input("Cycle #", min_value=1, max_value=50, value=None, step=1)
        nv_day     = tc3.number_input("Day of cycle", min_value=1, max_value=28, value=None, step=1)

        nv_route = st.selectbox("Route", [
            "", "IV", "Oral", "Radiation", "Combination IV + oral", "Other",
        ])

        rc1, rc2 = st.columns(2)
        nv_premeds     = rc1.checkbox("Antiemetic premedications received?")
        nv_neutropenia = rc2.checkbox("Known neutropenia risk or recent low ANC?")

        nv_oral_chemo_meds = st.text_input("Current oral cancer medications",
            placeholder="e.g. capecitabine, ibrutinib, lenalidomide")

    # Section 2: Symptom characterization
    with st.container(border=True):
        st.markdown("""
        <div class="card-hdr">
          <div class="icon-box">📋</div>
          <div><div class="card-title">Symptom characterization</div>
               <div class="card-sub">Type, onset, pattern, trajectory</div></div>
        </div>""", unsafe_allow_html=True)

        nv_type = st.radio("What is the patient experiencing? *",
            ["Nausea only", "Vomiting only", "Both nausea and vomiting",
             "Dry heaving / retching", "Poor appetite without nausea"],
            index=None)

        nv_onset     = st.text_input("Onset *", placeholder="e.g. this morning / 2 days ago")
        nv_onset_char = st.radio("Onset character",
            ["Sudden", "Gradual", "Intermittent"],
            horizontal=True, index=None)

        nv_pattern = st.multiselect("Pattern / triggers", [
            "Constant", "Comes and goes", "Triggered by eating", "Triggered by drinking",
            "Triggered by medications", "Triggered by movement",
            "Morning only", "Evening only", "Anticipatory (before treatment)",
        ])

        nv_trajectory = st.radio("Trajectory",
            ["Worsening", "Stable", "Improving"],
            horizontal=True, index=None)

        nv_relieving = st.text_input("What helps (if anything)?",
            placeholder="e.g. lying still, ginger tea, nothing")

    # Auto CINV classification hint
    cinv_type = None
    if last_tx:
        if "Anticipatory (before treatment)" in nv_pattern:
            cinv_type = "Anticipatory CINV"
        elif nv_onset and any(w in nv_onset.lower() for w in ["today", "this morning", "hour", "few hours"]):
            cinv_type = "Acute CINV (within 24h of treatment)"
        elif nv_onset:
            cinv_type = "Possible delayed CINV (days 1–5 post-treatment)"
    if cinv_type:
        flag = cinv_type + (" — no antiemetic premeds reported" if not nv_premeds else "")
        st.info(f"Suggested CINV classification: **{flag}**")

    # Section 3: Severity
    with st.container(border=True):
        st.markdown("""
        <div class="card-hdr">
          <div class="icon-box">🎛️</div>
          <div><div class="card-title">Severity</div>
               <div class="card-sub">Intensity, frequency, functional impact</div></div>
        </div>""", unsafe_allow_html=True)

        nv_nausea_score = st.slider("Nausea severity (0–10)", 0, 10, 5) \
            if nv_type != "Vomiting only" else None

        sv1, sv2 = st.columns(2)
        nv_vomit_24h = sv1.number_input("Vomiting episodes — last 24h",
            min_value=0, max_value=99, value=0, step=1)
        nv_vomit_48h = sv2.number_input("Vomiting episodes — last 48h",
            min_value=0, max_value=99, value=0, step=1)

        nv_dry_heave     = 0
        nv_emesis_volume = None
        if nv_type in ["Vomiting only", "Both nausea and vomiting", "Dry heaving / retching"]:
            nv_dry_heave = st.number_input("Dry heaving episodes — last 24h",
                min_value=0, max_value=99, value=0, step=1)
            nv_emesis_volume = st.radio("Volume per episode",
                ["Small", "Moderate", "Large", "Projectile"],
                horizontal=True, index=None)

        nv_impact = st.radio("Impact on activities",
            ["No impact", "Mild", "Moderate", "Unable to perform normal activities"],
            horizontal=True, index=None)

        nv_concern = st.radio("Patient concern level",
            ["Low", "Moderate", "High", "Extremely concerned"],
            horizontal=True, index=None)

    # Section 4: Oral intake and hydration
    with st.container(border=True):
        st.markdown("""
        <div class="card-hdr">
          <div class="icon-box warn">💧</div>
          <div><div class="card-title">Oral intake &amp; hydration</div>
               <div class="card-sub">Dehydration risk assessment</div></div>
        </div>""", unsafe_allow_html=True)

        ic1, ic2 = st.columns(2)
        nv_food_tol  = ic1.radio("Tolerating food?",
            ["Eating normally", "Small amounts only", "Sips only", "Nothing"],
            index=None)
        nv_fluid_tol = ic2.radio("Tolerating fluids?",
            ["Drinking normally", "Reduced", "Sips only", "Nothing"],
            index=None)

        lk1, lk2 = st.columns(2)
        nv_last_food  = lk1.text_input("Last food kept down", placeholder="e.g. this morning")
        nv_last_fluid = lk2.text_input("Last fluids kept down", placeholder="e.g. 1 hour ago")

        om1, om2 = st.columns(2)
        nv_oral_meds_ok   = om1.radio("Able to take oral medications?",
            ["Yes", "No", "Unsure"], horizontal=True, index=None)
        nv_oral_chemo_ok  = om2.radio("Retaining oral cancer therapy?",
            ["Yes", "No", "N/A"], horizontal=True, index=None)

        nv_urine = st.radio("Urine output",
            ["Normal", "Reduced", "Dark urine", "No urine >8 hours", "No urine >12 hours"],
            horizontal=True, index=None)

        st.markdown("**Dehydration symptoms present** (select all)")
        DEHY = ["Dry mouth", "Increased thirst", "Dizziness", "Lightheadedness",
                "Feeling faint", "Weakness", "Rapid heart rate", "Confusion"]
        nv_dehydration = []
        dh1, dh2 = st.columns(2)
        for i, d in enumerate(DEHY):
            if (dh1 if i % 2 == 0 else dh2).checkbox(d, key=f"nv_dehy_{i}"):
                nv_dehydration.append(d)

    # Section 5: Emesis characteristics (conditional)
    nv_emesis_appearance = []
    nv_blood_present     = None
    nv_projectile        = None

    if nv_type in ["Vomiting only", "Both nausea and vomiting"]:
        with st.container(border=True):
            st.markdown("""
            <div class="card-hdr">
              <div class="icon-box">🔬</div>
              <div><div class="card-title">Emesis characteristics</div>
                   <div class="card-sub">Appearance — shown because vomiting is present</div></div>
            </div>""", unsafe_allow_html=True)

            nv_emesis_appearance = st.multiselect("Appearance", [
                "Clear / watery", "Mucus", "Food contents", "Yellow / bile", "Green",
                "Bright red blood", "Coffee-ground appearance",
                "Feculent / foul smelling", "Unable to assess",
            ])

            ea1, ea2 = st.columns(2)
            nv_blood_present = ea1.radio("Blood present?",
                ["Yes", "No", "Unsure"], horizontal=True, index=None)
            nv_projectile    = ea2.radio("Projectile vomiting?",
                ["Yes", "No"], horizontal=True, index=None)

    # Section 6: Bowel function
    with st.container(border=True):
        st.markdown("""
        <div class="card-hdr">
          <div class="icon-box">🔄</div>
          <div><div class="card-title">Bowel function</div>
               <div class="card-sub">Constipation and obstruction screen</div></div>
        </div>""", unsafe_allow_html=True)

        bf1, bf2 = st.columns(2)
        nv_last_bm  = bf1.text_input("Last bowel movement", placeholder="e.g. 2 days ago")
        nv_pass_gas = bf2.radio("Passing gas?",
            ["Yes", "No", "Unsure"], horizontal=True, index=None)

        nv_opioid_use  = st.checkbox("Currently on opioids?")
        nv_constipation = st.radio("Constipation severity",
            ["None", "Mild", "Moderate", "Severe — no BM in 3+ days"],
            horizontal=True, index=None)

        BOWEL_SX = ["Abdominal pain", "Cramping", "Bloating", "Distension",
                    "Hard abdomen", "Diarrhea", "Blood in stool", "Mucus in stool"]
        nv_bowel_sx = []
        bx1, bx2 = st.columns(2)
        for i, s in enumerate(BOWEL_SX):
            if (bx1 if i % 2 == 0 else bx2).checkbox(s, key=f"nv_bowel_{i}"):
                nv_bowel_sx.append(s)

        nv_abd_pain_score = nv_abd_pain_loc = nv_abd_pain_char = None
        if "Abdominal pain" in nv_bowel_sx:
            st.markdown("**Abdominal pain details**")
            ap1, ap2, ap3 = st.columns(3)
            nv_abd_pain_score = ap1.slider("Pain score", 0, 10, 5, key="nv_abd_sl")
            nv_abd_pain_loc   = ap2.radio("Location",
                ["Localized", "Diffuse"], index=None, key="nv_abd_loc")
            nv_abd_pain_char  = ap3.radio("Character",
                ["Constant", "Intermittent"], index=None, key="nv_abd_char")

    # Section 7: Associated symptoms
    with st.container(border=True):
        st.markdown("""
        <div class="card-hdr">
          <div class="icon-box">🔍</div>
          <div><div class="card-title">Associated symptoms</div>
               <div class="card-sub">Infection, neurologic, GI/hepatic, irAE screen</div></div>
        </div>""", unsafe_allow_html=True)

        st.markdown("**Infection / sepsis**")
        INFX = ["Fever", "Chills", "Rigors", "New cough",
                "Shortness of breath", "Burning with urination", "Port redness / pain"]
        nv_infx = []
        ix1, ix2 = st.columns(2)
        for i, s in enumerate(INFX):
            if (ix1 if i % 2 == 0 else ix2).checkbox(s, key=f"nv_infx_{i}"):
                nv_infx.append(s)

        st.markdown("**Neurologic**")
        NEURO = ["Headache", "Severe headache", "Vision changes", "Confusion / AMS",
                 "Weakness", "New numbness", "Seizure", "Neck stiffness", "Photophobia"]
        nv_neuro = []
        nx1, nx2 = st.columns(2)
        for i, s in enumerate(NEURO):
            if (nx1 if i % 2 == 0 else nx2).checkbox(s, key=f"nv_neuro_{i}"):
                nv_neuro.append(s)

        st.markdown("**GI / hepatic**")
        GI = ["Diarrhea", "Severe abdominal pain", "Early satiety", "Weight loss",
              "Jaundice", "Dark urine", "Right upper quadrant pain", "Increased bruising"]
        nv_gi = []
        gi1, gi2 = st.columns(2)
        for i, s in enumerate(GI):
            if (gi1 if i % 2 == 0 else gi2).checkbox(s, key=f"nv_gi_{i}"):
                nv_gi.append(s)

        st.markdown("**Immunotherapy-related toxicity (irAE) screen**")
        IRAE = ["Severe fatigue", "Dizziness", "Mood / behavioral changes",
                "Feeling cold / cold intolerance", "Polyuria / polydipsia", "New rash"]
        nv_irae = []
        ir1, ir2 = st.columns(2)
        for i, s in enumerate(IRAE):
            if (ir1 if i % 2 == 0 else ir2).checkbox(s, key=f"nv_irae_{i}"):
                nv_irae.append(s)

    # Section 8: Medication review
    with st.container(border=True):
        st.markdown("""
        <div class="card-hdr">
          <div class="icon-box">💊</div>
          <div><div class="card-title">Antiemetics tried</div>
               <div class="card-sub">Select all — complete details for each selected</div></div>
        </div>""", unsafe_allow_html=True)

        am1, am2 = st.columns(2)
        for i, (key, label) in enumerate(NV_ANTIEMETIC_KEYS):
            (am1 if i % 2 == 0 else am2).checkbox(label, key=key, on_change=on_nv_med)
        am1.checkbox("Nothing tried yet", key="nv_med_nothing", on_change=on_nv_nothing)

        selected_meds = [(key, label) for key, label in NV_ANTIEMETIC_KEYS
                         if st.session_state[key]]
        nv_meds_detail = {}
        if selected_meds:
            st.markdown("---")
            for key, label in selected_meds:
                st.markdown(f"**{label}**")
                d1, d2, d3, d4 = st.columns([1.2, 1.2, 1, 2])
                dose      = d1.text_input("Dose",       placeholder="e.g. 8 mg",  key=f"{key}_dose",  label_visibility="collapsed")
                time_taken = d2.text_input("Last dose",  placeholder="e.g. 2 pm", key=f"{key}_time",  label_visibility="collapsed")
                num_doses  = d3.text_input("# doses",   placeholder="e.g. 2",     key=f"{key}_ndose", label_visibility="collapsed")
                response   = d4.selectbox("Response", [
                    "", "Significant improvement", "Partial improvement",
                    "No improvement", "Symptoms worsened",
                ], key=f"{key}_resp", label_visibility="collapsed")
                kept_down  = st.checkbox("Able to keep this medication down?", key=f"{key}_kept")
                nv_meds_detail[label] = {
                    "dose": dose, "time": time_taken,
                    "doses": num_doses, "response": response, "kept_down": kept_down,
                }

        st.markdown("**Other medications that may be contributing**")
        CONTRIB = ["Opioids", "Antibiotics", "Iron supplements", "NSAIDs",
                   "Supplements / herbals", "Recently started new medication"]
        nv_contrib = []
        cm1, cm2 = st.columns(2)
        for i, s in enumerate(CONTRIB):
            if (cm1 if i % 2 == 0 else cm2).checkbox(s, key=f"nv_contrib_{i}"):
                nv_contrib.append(s)
        nv_contrib_note = st.text_input("Specify if recently started or other",
            placeholder="e.g. started metformin 3 days ago")

    # Section 9: Safety flags (auto-computed + manual)
    auto_flags = []

    if nv_blood_present == "Yes" or any(x in nv_emesis_appearance
            for x in ["Bright red blood", "Coffee-ground appearance"]):
        auto_flags.append("Blood in vomit or coffee-ground emesis")
    if "Feculent / foul smelling" in nv_emesis_appearance:
        auto_flags.append("Feculent / foul-smelling emesis")
    if nv_vomit_24h >= 6:
        auto_flags.append(f"Vomiting 6+ times in 24 hours ({nv_vomit_24h} episodes)")
    if nv_fluid_tol == "Nothing":
        auto_flags.append("Unable to keep any fluids down")
    if nv_oral_meds_ok == "No":
        auto_flags.append("Unable to take oral medications")
    if nv_oral_chemo_ok == "No":
        auto_flags.append("Unable to retain oral cancer therapy")
    if nv_urine in ["No urine >8 hours", "No urine >12 hours"]:
        auto_flags.append(f"No urine output — {nv_urine}")
    if len(nv_dehydration) >= 3:
        auto_flags.append(f"Multiple dehydration symptoms ({len(nv_dehydration)} present)")
    if "Fever" in nv_infx:
        f_txt = "Fever present"
        if nv_neutropenia:
            f_txt += " with neutropenia risk — febrile neutropenia protocol"
        auto_flags.append(f_txt)
    if nv_abd_pain_score is not None and nv_abd_pain_score >= 7:
        auto_flags.append(f"Severe abdominal pain ({nv_abd_pain_score}/10)")
    if ("Distension" in nv_bowel_sx or "Hard abdomen" in nv_bowel_sx) and nv_pass_gas == "No":
        auto_flags.append("Possible bowel obstruction — distension with no flatus")
    if nv_constipation == "Severe — no BM in 3+ days" and nv_pass_gas == "No":
        auto_flags.append("No BM in 3+ days with no flatus — obstruction concern")
    neuro_urgent = [s for s in nv_neuro if s in
        ["Severe headache", "Seizure", "Confusion / AMS", "Vision changes"]]
    if neuro_urgent:
        auto_flags.append(f"Urgent neurologic symptoms: {', '.join(neuro_urgent)}")
    if nv_irae:
        auto_flags.append(f"Possible irAE: {', '.join(nv_irae)}")

    MANUAL_FLAGS = [
        "Signs of aspiration", "Unable to sit up / stand",
        "Recent head trauma", "Port access concern", "Other urgent concern",
    ]

    with st.container(border=True):
        st.markdown("""
        <div class="card-hdr">
          <div class="icon-box danger">⚠️</div>
          <div><div class="card-title">Safety flags</div>
               <div class="card-sub">Auto-detected above — add any additional below</div></div>
        </div>""", unsafe_allow_html=True)

        if auto_flags:
            for f in auto_flags:
                st.markdown(f'<div class="auto-flag">🚨 {f}</div>', unsafe_allow_html=True)
            st.write("")

        manual_flags = []
        mf1, mf2 = st.columns(2)
        for i, opt in enumerate(MANUAL_FLAGS):
            if (mf1 if i % 2 == 0 else mf2).checkbox(opt, key=f"nv_flag_{i}"):
                manual_flags.append(opt)

    all_nv_flags = auto_flags + manual_flags

    with st.container(border=True):
        st.markdown("""
        <div class="card-hdr">
          <div class="icon-box">📝</div>
          <div><div class="card-title">Nurse note</div>
               <div class="card-sub">Free-text observations</div></div>
        </div>""", unsafe_allow_html=True)
        nv_nurse_note = st.text_area(
            "note", label_visibility="collapsed",
            placeholder="Additional observations, prior episodes, recent labs, patient demeanor…",
            key="nv_nurse_note",
        )

    nv_required_ok = bool(age is not None and dx and tx and nv_type and nv_onset)
    generate = st.button("✨  Generate provider summary", type="primary",
                         use_container_width=True, disabled=not nv_required_ok,
                         key="nv_generate")
    if not nv_required_ok:
        st.caption("Complete required fields (age, diagnosis, treatment, symptom type, onset) to enable.")

    if generate:
        med_parts = []
        if st.session_state.get("nv_med_nothing"):
            med_parts.append("nothing tried")
        else:
            for label, d in nv_meds_detail.items():
                p = label
                if d["dose"]:     p += f" {d['dose']}"
                if d["time"]:     p += f" (last dose {d['time']})"
                if d["doses"]:    p += f" x{d['doses']} doses"
                if d["response"]: p += f" — {d['response']}"
                if not d["kept_down"]: p += " (unable to keep down)"
                med_parts.append(p)
        med_summary = "; ".join(med_parts) if med_parts else "none documented"

        assoc_all = nv_infx + nv_neuro + nv_gi + nv_irae

        prompt = (
            "You are a clinical documentation assistant helping oncology nurses write SBAR-style "
            "triage summaries. Write in professional clinical language, past tense, third person. "
            "Use these labeled sections: SITUATION, BACKGROUND, ASSESSMENT, RED FLAGS (omit if none). "
            "Be concise — 6–8 sentences total. Do not add recommendations or diagnoses.\n\n"
            f"TRIAGE DATA\n\n"
            f"SITUATION\n"
            f"Patient: {int(age)} y/o with {dx}, on {tx}"
            f"{f', last treatment {last_tx}' if last_tx else ''}. "
            f"Calling with: {nv_type or 'nausea/vomiting'}, onset {nv_onset}. "
            f"Onset character: {nv_onset_char or 'not specified'}. "
            f"Trajectory: {nv_trajectory or 'not specified'}.\n\n"
            f"BACKGROUND\n"
            f"Regimen: {nv_regimen or 'not specified'}. "
            f"Cycle {nv_cycle or '?'}, Day {nv_day or '?'}. "
            f"Route: {nv_route or 'not specified'}. "
            f"Antiemetic premeds received: {'yes' if nv_premeds else 'no'}. "
            f"Neutropenia risk: {'yes' if nv_neutropenia else 'no'}. "
            f"Oral cancer meds: {nv_oral_chemo_meds or 'none listed'}. "
            f"Pattern: {', '.join(nv_pattern) if nv_pattern else 'not specified'}. "
            f"{f'Relieving factors: {nv_relieving}.' if nv_relieving else ''}\n\n"
            f"ASSESSMENT\n"
            f"Nausea severity: {f'{nv_nausea_score}/10' if nv_nausea_score is not None else 'N/A'}. "
            f"Vomiting: {nv_vomit_24h} episodes/24h, {nv_vomit_48h}/48h. "
            f"Volume: {nv_emesis_volume or 'not specified'}. "
            f"Emesis appearance: {', '.join(nv_emesis_appearance) if nv_emesis_appearance else 'not assessed'}. "
            f"Food tolerance: {nv_food_tol or 'not specified'}. "
            f"Fluid tolerance: {nv_fluid_tol or 'not specified'}. "
            f"Last fluids kept down: {nv_last_fluid or 'not specified'}. "
            f"Urine output: {nv_urine or 'not specified'}. "
            f"Dehydration symptoms: {', '.join(nv_dehydration) if nv_dehydration else 'none'}. "
            f"Oral meds tolerated: {nv_oral_meds_ok or 'unknown'}. "
            f"Oral cancer therapy retained: {nv_oral_chemo_ok or 'N/A'}. "
            f"Last BM: {nv_last_bm or 'not reported'}. Passing gas: {nv_pass_gas or 'unknown'}. "
            f"Bowel symptoms: {', '.join(nv_bowel_sx) if nv_bowel_sx else 'none'}. "
            f"Abdominal pain: {f'{nv_abd_pain_score}/10, {nv_abd_pain_loc}, {nv_abd_pain_char}' if nv_abd_pain_score is not None else 'none'}. "
            f"Associated symptoms: {', '.join(assoc_all) if assoc_all else 'none'}. "
            f"Antiemetics tried: {med_summary}. "
            f"Contributing meds: {', '.join(nv_contrib) if nv_contrib else 'none'}. "
            f"Functional impact: {nv_impact or 'not specified'}.\n\n"
            f"RED FLAGS: {', '.join(all_nv_flags) if all_nv_flags else 'none identified'}.\n\n"
            f"Nurse note: {nv_nurse_note or 'none'}.\n\n"
            "Write the SBAR provider summary now:"
        )

        api_key = os.getenv("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY", None)
        if not api_key:
            st.error("⚠️ ANTHROPIC_API_KEY not set.")
        else:
            with st.spinner("Generating summary…"):
                try:
                    client = anthropic.Anthropic(api_key=api_key)
                    msg = client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=500,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    st.session_state["summary"] = msg.content[0].text
                    st.session_state["summary_had_flags"] = bool(all_nv_flags)
                except Exception as e:
                    st.session_state["summary"] = f"API error: {e}"
                    st.session_state["summary_had_flags"] = False

# ─────────────────────────────────────────────────────────────────────────────
# SHARED: PROVIDER SUMMARY OUTPUT
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
