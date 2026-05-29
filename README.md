# OncoTriage Assistant

A symptom screener for oncology nurses doing after-hours triage. You walk through a structured intake form, and it generates a clean clinical summary you can paste straight into the EHR or read off to a provider.

**[Live demo →](https://oncology-triage-assistant-evaizat8jgk7yalym7gpeh.streamlit.app/)**

---

## Why I built this

After-hours triage calls are fast and high-stakes. A lot of nurses (myself included) end up writing free-text notes on the fly, and it's easy to miss things — when the patient last took something, whether the pain is new or chronic, what the trajectory has been. The summary ends up inconsistent depending on who took the call.

This tool guides you through the intake systematically, flags anything urgent, and spits out a standardized summary. No more starting from a blank box.

---

## Tech stack

| Layer | Technology |
|---|---|
| UI & hosting | [Streamlit](https://streamlit.io) (Python) |
| AI summarization | [Anthropic API](https://docs.anthropic.com) — claude-sonnet-4-6 |
| Auth | `ANTHROPIC_API_KEY` via `.env` (local) or Streamlit Secrets (cloud) |
| Deployment | Streamlit Community Cloud (free tier) |

---

## How the prompt works

The model is instructed to act as a clinical documentation assistant — not a clinician. It won't offer diagnoses or recommendations. The output is always past tense, third person, one paragraph — the format you'd expect in a triage note. All the form fields get passed in as labeled values so the model isn't guessing at anything. If a safety flag is checked, it shows up verbatim in the summary and triggers an "Urgent flags present" badge in the UI.

---

## What's in it right now

- Headache screener (full intake)
- Face pain scale — 6 illustrated faces that sync with the 0–10 slider
- Medication timing fields that only appear when a medication was actually taken
- Safety flag detection with a red urgent badge on the summary
- Copy button on the generated summary

Seven more symptom screeners are stubbed in with "coming soon" badges: nausea/vomiting, fever/chills, shortness of breath, fatigue, diarrhea, bleeding, muscle pain.

---

## Run it locally

```bash
git clone https://github.com/saramaknojia94-ux/oncology-triage-assistant
cd oncology-triage-assistant

pip install -r requirements.txt

# Create .env with your Anthropic API key
echo ANTHROPIC_API_KEY=sk-ant-... > .env

streamlit run app.py
```

---

## Deploy to Streamlit Cloud

1. Push to GitHub (`.env` is gitignored — don't commit it)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → pick your repo → `app.py`
3. Under **Advanced settings → Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
4. Deploy
