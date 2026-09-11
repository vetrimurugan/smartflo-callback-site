# Smartflo instant callback site

## Local run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Set the same environment variables in Render before launching the service. The Smartflo token remains server-side and is never sent to the browser.

## Render deployment

Create a new Web Service from this directory or repository. Render detects `render.yaml`; use the requested values in its Environment page:

- `SMARTFLO_API_TOKEN`: Smartflo API token
- `SMARTFLO_AGENT_NUMBER`: registered sales-agent mobile number, Smartflo Agent ID, or extension
- `SMARTFLO_CALLER_ID`: a DID assigned to the Smartflo account (optional)

Use Smartflo's regular `click_to_call` service. It calls the agent first and, once answered, dials the customer and bridges the call.
