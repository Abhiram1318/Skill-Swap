# SkillSwap India 🇮🇳

A Flask + HTML skill-exchange website based on the supplied SkillSwap project.

## Stack

- Python / Flask
- SQLite
- HTML/CSS/JavaScript
- Werkzeug password hashing
- Gunicorn for production

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Project structure

```text
SkillSwap/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
└── templates/
    └── index.html
```

## Deploying

This project is suitable for a Flask web service host such as Render.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
gunicorn app:app
```

Set a strong `SECRET_KEY` environment variable in production.

### Database note

The supplied backend uses SQLite. SQLite is excellent for local development and demos, but many cloud hosts use ephemeral filesystems. For a production app with important user data, migrate the database to managed PostgreSQL before launch.
