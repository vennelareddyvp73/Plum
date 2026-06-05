# Setup Guide & Project Status

---

## Prerequisites — Install These First

### 1. Python 3.11+
Download from https://www.python.org/downloads/  
During install: check **"Add Python to PATH"**  
Verify: open Command Prompt and run `python --version`

### 2. Node.js 18+
Download from https://nodejs.org (LTS version)  
Verify: `node --version`

### 3. PostgreSQL 14+
Download from https://www.postgresql.org/download/windows/  
Use the installer — it sets up everything including pgAdmin  
Default username: `postgres`, set a password during install — remember it  
Verify: `psql --version`

### 4. Poppler (required for PDF uploads)
1. Download the latest Windows binaries from: https://github.com/oschwartz10612/poppler-windows/releases  
   Get the file named `Release-xx.xx.x-0.zip`
2. Extract the zip — you'll get a folder like `poppler-24.08.0`
3. Copy that folder to `C:\Program Files\poppler`
4. Add `C:\Program Files\poppler\Library\bin` to your system PATH:  
   - Search "environment variables" in the Start menu  
   - Click "Edit the system environment variables"  
   - Click "Environment Variables"  
   - Under "System variables", select `Path` → Edit → New  
   - Paste `C:\Program Files\poppler\Library\bin`  
   - Click OK on all dialogs  
5. Open a **new** Command Prompt and verify: `pdftoppm -v`

### 5. Groq API Key (free)
Sign up at https://console.groq.com and create an API key.

---

## Setup (Windows — Command Prompt)

Open Command Prompt (`Win + R` → type `cmd` → Enter), then run these commands one by one:

```
cd path\to\plum-claims\backend
```

```
copy .env.example .env
```

Open `backend\.env` in Notepad and fill in:
```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/plum_claims
GROQ_API_KEY=gsk_your_key_here
```

Create the database (replace `YOUR_PASSWORD`):
```
psql -U postgres -c "CREATE DATABASE plum_claims;"
```

Set up Python environment:
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Build the frontend:
```
cd ..\frontend
npm install
npm run build
xcopy /E /I /Y dist ..\backend\static
cd ..\backend
```

Start the server:
```
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 in your browser. The app is running.

> Tables are created automatically on first start. Test members EMP001–EMP010 are seeded automatically.

---

## Every Time You Start (after first setup)

```
cd path\to\plum-claims\backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

---

## Running the Tests

With the server running, open a second Command Prompt:

```
cd path\to\plum-claims\backend
venv\Scripts\activate
python run_tests.py
```

To run a single case:
```
python run_tests.py --case TC001
```

---

## What Is Done

### Core Application
- Vision LLM extracts structured data from uploaded images and PDFs (one LLM call per document)
- Text-based submission endpoint for testing without real scanned documents
- Aggregator merges all document JSONs into a unified claim dict
- Rule engine runs 19 deterministic checks — no LLM involved
- LLM generates plain-English explanations for every rule violation
- Final LLM step checks medical necessity and fraud signals
- LangGraph pipeline wiring: extract → aggregate → rules → violation path or adjudication path

### Rules (all 19 implemented)
BELOW_MIN_AMOUNT, LATE_SUBMISSION, MISSING_DOCUMENTS, INVALID_PRESCRIPTION, DOCTOR_REG_INVALID, DATE_MISMATCH, ILLEGIBLE_DOCUMENTS, PATIENT_MISMATCH, MEMBER_NOT_COVERED, POLICY_INACTIVE, WAITING_PERIOD (5 periods), COSMETIC_PROCEDURE, EXCLUDED_CONDITION, PRE_AUTH_MISSING, PER_CLAIM_EXCEEDED, ANNUAL_LIMIT_EXCEEDED, SUB_LIMIT_EXCEEDED, DUPLICATE_CLAIM, SUSPICIOUS_PATTERN

### Storage
- PostgreSQL — 4 tables: members, claims, documents, decisions
- Every extracted document JSON stored in full
- Every decision stored with all fields (amounts, deductions, reasoning, fraud flags, confidence)
- Appeals stored and retrievable

### API
All endpoints working: submit, test-submit, get claim, list claims, appeal, list members, member stats, policy, health check

### Frontend (4 pages)
- New Claim — file upload, 3-step flow
- Claim Detail — decision card, extracted document fields, confidence bars, appeal button
- Claim History — member lookup, YTD stats, claims table
- Policy — full policy terms viewer

### Tests
- 10 test cases written and runnable via `run_tests.py`

---

## What Is Remaining

### 1. Deployment
The app runs locally only. The assignment asks for a live URL.

Easiest option — **Railway** (~10 minutes):
1. Push the repo to GitHub
2. Go to https://railway.app → New Project → Deploy from GitHub repo
3. Add a PostgreSQL plugin inside Railway
4. Set environment variables in Railway dashboard:
   - `DATABASE_URL` — Railway provides this automatically when you add Postgres
   - `GROQ_API_KEY` — your Groq key
5. Set the start command to: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Build the frontend once locally (`npm run build`), copy `dist/` into `backend/static/`, commit and push

Railway will detect Python, install `requirements.txt`, and start the server.

### 2. Architecture Diagram
The assignment asks for one. The full pipeline flow is written out in `PROJECT_DEEP_DIVE.md` — you can convert that into a diagram using draw.io or any tool.

### 3. Demo Video (5–10 minutes)
Suggested flow:
- Submit TC001 via the UI (show upload → processing → decision card)
- Submit TC002 to show partial approval
- Open Claim History, look up EMP001
- Open the Policy page
- Run `python run_tests.py` in the terminal showing results
- Briefly explain: vision LLM → rules engine → adjudication LLM → PostgreSQL

---

## Troubleshooting

**`psql` not recognized:**  
PostgreSQL's bin folder is not in PATH. Add `C:\Program Files\PostgreSQL\16\bin` to PATH (same steps as poppler above, but for PostgreSQL).

**`venv\Scripts\activate` gives a permissions error:**  
Run this once in PowerShell as Administrator:
```
Set-ExecutionPolicy RemoteSigned
```
Then retry activation in Command Prompt (not PowerShell).

**`pdf2image` error about poppler:**  
Poppler is not in PATH. Re-check the poppler setup steps above and open a fresh Command Prompt after adding to PATH.

**Database connection refused:**  
PostgreSQL service isn't running. Open Services (`Win + R` → `services.msc`), find `postgresql-x64-16`, right-click → Start.

**`GROQ_API_KEY` error on startup:**  
The `.env` file is missing or in the wrong place. It must be at `backend\.env` (not the project root).

**Port 8000 already in use:**  
```
uvicorn app.main:app --reload --port 8001
```
Then open http://localhost:8001.

**Frontend shows blank page:**  
The static files weren't copied. Run from the project root:
```
cd frontend && npm run build && xcopy /E /I /Y dist ..\backend\static
```