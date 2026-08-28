# Microsoft Learn web chat

This project provides a browser chat interface that grounds answers in the
Microsoft Learn MCP server at `https://learn.microsoft.com/api/mcp`.

## Prerequisites

- Python 3.10 or newer
- An API key for an OpenAI-compatible chat-completions provider
- Network access to Microsoft Learn

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
streamlit run app.py
```

Set `MODEL_API_KEY` in `.env`. `MODEL_BASE_URL` supports compatible providers,
and `MODEL_NAME` selects the deployed model. The Microsoft Learn MCP URL and
timeout can also be overridden there.

The model key is used only by the server-side Streamlit process. Do not put it
in browser code or commit `.env`.

## Tests

```powershell
python -m unittest discover -s tests -v
```
