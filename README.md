# Finlyzer — AI-Powered Banking Complaint Analyzer

Finlyzer uses NLP and Machine Learning to analyze customer complaints, uncover root causes, and help banking teams resolve issues faster.

## Features

- **Complaint clustering** — K-Means groups similar complaints automatically
- **Sentiment analysis** — DistilBERT-powered complaint sentiment scoring
- **Topic modeling** — LDA surfaces recurring root cause themes
- **Interactive dashboard** — Streamlit + Plotly visualizations
- **Call log** — Agents can log calls and outcomes per complaint
- **Role-based access** — Admin and Viewer roles with session management
- **Audit logging** — All sensitive actions are logged with user context

## Project structure

```
Finlyzer/
├── .github/workflows/ci.yaml   # GitHub Actions CI
├── .streamlit/config.toml      # Streamlit server config
├── data/
│   └── failed_transactions.csv # Complaint dataset
├── src/
│   ├── auth.py                 # Authentication & RBAC
│   ├── clustering.py           # K-Means complaint clustering
│   ├── dashboard.py            # Main Streamlit app
│   ├── data_input.py           # CSV/Excel loader
│   ├── db.py                   # SQLite persistence
│   ├── nlp_engine.py           # Sentiment, LDA, keyword extraction
│   ├── preprocessing.py        # Text cleaning, lemmatization, PII redaction
│   └── utils.py                # Atomic file writes, logging
├── tests/
│   └── test_core.py            # Unit tests (pytest)
├── conftest.py                 # pytest path setup
├── requirements.txt
└── setup.sh                    # spaCy model download (Streamlit Cloud)
```

## Local setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/Finlyzer.git
cd Finlyzer

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Configure passwords
cp .env.example .env
# Edit .env and set STREAMLIT_PASSWORD and STREAMLIT_ADMIN_PASSWORD

# Run the app
streamlit run src/dashboard.py
```

## Running tests

```bash
python -m pytest tests/ -v
```

## Deployment (Streamlit Community Cloud)

1. Push to GitHub (public repo)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. New app → Repo: `Finlyzer` | Branch: `main` | Main file: `src/dashboard.py`
4. Advanced settings → Secrets → add `STREAMLIT_PASSWORD` and `STREAMLIT_ADMIN_PASSWORD`
5. Deploy

## Environment variables

| Variable | Description |
|---|---|
| `STREAMLIT_PASSWORD` | Password for viewer access |
| `STREAMLIT_ADMIN_PASSWORD` | Password for admin access (bulk actions, agent override) |

## Tech stack

Python · Streamlit · Pandas · scikit-learn · spaCy · Hugging Face Transformers · Plotly · SQLite
