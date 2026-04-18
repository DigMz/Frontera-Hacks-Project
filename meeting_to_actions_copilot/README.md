# Meeting-to-Actions Copilot

Paste meeting notes/transcripts and get a summary, decisions, and structured action items. Exports Markdown + CSV.

## Setup

```bash
cd meeting_to_actions_copilot
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Option A: OpenAI-compatible endpoint (your rgvaiclass.com key)

```bash
setx OPENAI_API_KEY "your_key_here"
setx OPENAI_BASE_URL "https://YOUR_PROVIDER_HOST/v1"
```

In the app sidebar, set the model to whatever your provider supports (e.g. `gpt-5.2`).

Option B: Anthropic/Claude

```bash
setx ANTHROPIC_API_KEY "your_key_here"
```

## Run

```bash
streamlit run app.py
```

## Notes

- If `ANTHROPIC_API_KEY` is not set, the app falls back to a lightweight heuristic extractor so you can still demo the UI.
- If `OPENAI_API_KEY` + `OPENAI_BASE_URL` are set, those are used first.
