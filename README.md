# Oncology Nurse Triage Documentation Assistant

A structured symptom screener that helps oncology nurses collect a complete headache intake and generate a provider-ready clinical summary in seconds — reducing documentation burden and standardizing triage hand-offs.

**[Live demo →](https://your-app-name.streamlit.app)**

---

## The clinical problem it solves

Oncology nurses fielding after-hours triage calls often document in free text, which varies in completeness and format. Key details — safety flags, medication timing, pain trajectory — are easy to omit under time pressure. This tool guides the nurse through a structured screener, ensures no required field is skipped, and produces a consistent, provider-ready summary that can be pasted directly into the EHR or handed off verbally.

---

## Tech stack

| Layer | Technology |
|---|---|
| UI & hosting | [Streamlit](https://streamlit.io) (Python) |
| AI summarization | [Anthropic API](https://docs.anthropic.com) — claude-sonnet-4-6 |
| Auth | `ANTHROPIC_API_KEY` via `.env` (local) or Streamlit Secrets (cloud) |
| Deployment | Streamlit Community Cloud (free tier) |

---

## How the AI prompt was designed

The prompt is **role-scoped, format-constrained, and data-driven**:

1. **Role framing** — "You are a clinical documentation assistant…" constrains the model to documentation tasks only; it will not offer diagnoses or recommendations.
2. **Style rules** — past tense, third person, one paragraph, 3–5 sentences. This matches the format expected in oncology triage notes and keeps output paste-ready.
3. **Structured data injection** — all form fields are serialized as labeled key-value pairs. This gives the model a deterministic input format and prevents it from inferring missing data.
4. **Explicit scope boundary** — "Do not add recommendations or diagnoses" prevents the model from overstepping clinical boundaries — important for a nurse-facing tool.
5. **Safety flag forwarding** — if any safety flags are checked, they appear verbatim in the prompt and trigger an "Urgent flags present" badge in the UI. The model surfaces them in the summary without interpreting them.

---

## Features

- **Symptom selector** — headache screener active; 7 future symptoms shown with "soon" badges
- **Face pain scale** — 6 illustrated faces sync live with the 0–10 slider
- **Conditional medication timing** — time input and relief question appear only when a medication is selected (not for "nothing tried")
- **Safety flags** — any checked flag triggers a red "Urgent flags present" badge on the generated summary
- **Copy-to-clipboard** — native copy button on the summary code block

---

## Local setup

```bash
git clone https://github.com/your-username/oncology-triage-assistant
cd oncology-triage-assistant

pip install -r requirements.txt

# Create .env with your Anthropic API key
echo ANTHROPIC_API_KEY=sk-ant-... > .env

streamlit run app.py
```

---

## Deploying to Streamlit Cloud

1. Push this repo to GitHub (`.env` is gitignored — never commit it)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → select your repo → `app.py`
3. Under **Advanced settings → Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
4. Click **Deploy**

---

## Roadmap

Additional symptom screeners planned: nausea/vomiting, fever/chills, shortness of breath, fatigue, diarrhea, bleeding, muscle pain.
