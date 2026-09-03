# SkillSwap India — Startup Homepage

Modern startup-style homepage layered onto the existing Flask + HTML SkillSwap application.

## Run

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Deployment

Build command:
`pip install -r requirements.txt`

Start command:
`gunicorn app:app`

The homepage redesign is presentation-only and keeps the existing Flask/API application.
