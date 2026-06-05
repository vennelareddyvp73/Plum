# Plum OPD Claims — Full Project Deep Dive

Everything about the codebase: folder structure, what every file does, the overall flow, system design decisions, and the small details that might look arbitrary but aren't.

---

## Folder Structure

```
plum-claims/
├── backend/
│   ├── app/
│   │   ├── api/            ← HTTP layer (FastAPI routers)
│   │   ├── db/             ← Database layer (models, CRUD, seed)
│   │   ├── pipeline/       ← LangGraph AI pipeline
│   │   ├── schemas/        ← Pydantic data contracts
│   │   ├── services/       ← Business logic (rules, extraction, aggregation)
│   │   ├── config.py       ← Settings + policy loader
│   │   └── main.py         ← FastAPI app entry point
│   ├── policy_terms.json   ← The policy rules source of truth
│   ├── requirements.txt
│   ├── run_tests.py        ← 10-case test suite
│   └── .env / .env.example
├── frontend/
│   └── src/
│       ├── pages/          ← Full-page React components
│       ├── components/     ← Reusable UI components
│       └── App.jsx         ← Router + nav
├── setup.sh                ← One-shot setup script
└── README.md
```

---

## Backend

### `app/main.py`

The FastAPI application entry point. Three things happen here:

**1. Routers mounted:**
```python
app.include_router(claims_router)     # POST /api/claims/submit, GET /api/claims/{id}
app.include_router(test_router)       # POST /api/claims/test-submit
app.include_router(members_router)    # GET /api/members, /api/members/{id}/stats, /api/policy
```

**2. Startup lifespan:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)   # creates tables if not exist
    seed()                                   # inserts EMP001–EMP010 if missing
    yield
```
`create_all` is idempotent — safe to run every restart. `seed()` is wrapped in try/except so a DB issue never crashes the app start.

**3. Frontend serving:**
At the bottom, if a `static/` folder exists (built frontend), FastAPI serves it. The catch-all route `/{full_path:path}` returns `index.html` for every non-API path — this is what lets React Router work in production (all client-side routes return the React app).

---

### `app/config.py`

Two responsibilities:

**Settings (via pydantic-settings):**
```python
class Settings(BaseSettings):
    database_url: str = "postgresql://..."
    groq_api_key: str = ""
    model_config = {"env_file": ".env"}
```
`pydantic-settings` reads from `.env` automatically. The defaults allow the app to start even without a `.env` (it'll fail at DB connection, but it won't crash at import time).

**Policy loader:**
```python
_policy_path = Path(__file__).parent.parent / "policy_terms.json"
with open(_policy_path) as _f:
    POLICY: dict = json.load(_f)
```
The policy is loaded once at import time into a module-level `POLICY` dict. Every other file (`rules_engine.py`, `adjudicator.py`, `members.py`) imports this constant — so changing `policy_terms.json` is all you need to update limits, sub-limits, waiting periods, etc. No code changes required.

The underscore-prefixed `_policy_path` and `_f` are private to this module — the convention of leading `_` signals "not intended for import by other modules."

---

### `app/db/database.py`

SQLAlchemy setup:
```python
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

`get_db()` is a FastAPI dependency that yields a session and always closes it:
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
Used in every API endpoint as `db: Session = Depends(get_db)`. FastAPI calls `get_db()`, passes the session, and the `finally` ensures cleanup even if an exception is thrown.

`Base = DeclarativeBase()` — the SQLAlchemy 2.0 style base class all models inherit from.

---

### `app/db/models.py`

Four tables:

**`Member`** — the insured employees. Fields: `id` (e.g. EMP001), `name`, `policy_start_date`, `policy_end_date`, `is_active`, `join_date`. `join_date` is used by the rules engine to calculate whether waiting periods are satisfied.

**`Claim`** — one row per submitted claim. `id` is `CLM_XXXXXXXX` (vision submissions) or `TST_XXXXXXXX` (test-submit). Starts as `PENDING`, updated to final decision status after pipeline runs. `flagged_for_review` and `review_notes` are set when the user clicks "Request Manual Review" post-decision.

**`Document`** — one row per uploaded file within a claim. Stores:
- `file_path` — where the uploaded image/PDF lives on disk
- `ocr_text` — only populated for test-submit (the raw text input)
- `extracted_json` — the full structured JSON the LLM extracted (all fields)
- `extraction_confidence` — 0–1 float from the LLM

**`Decision`** — one row per claim (one-to-one). Stores the complete adjudication output: decision type, amounts, deductions, rejection reasons, violation reasoning (LLM explanations), fraud flags, medical necessity verdict, confidence score, notes, next steps.

All `created_at` columns use `default=datetime.utcnow` — evaluated at insert time, not at class definition time (this is why it's `default=datetime.utcnow`, not `default=datetime.utcnow()`).

---

### `app/db/crud.py`

Pure database functions, no business logic. Key ones:

**`get_ytd_approved`** — sums approved amounts for a member in the current year, excluding the current claim. Used by the rules engine to check ANNUAL_LIMIT.
```python
extract("year", Claim.treatment_date) == tx_date.year
```

**`get_same_day_claims_count`** — counts total claims for this member on the same treatment date. Called AFTER `create_claim`, so the count includes the current submission. Threshold in rules engine accounts for this.

**`get_existing_bill_numbers`** — scans all existing document `extracted_json` blobs for `bill_number` fields. Used to detect DUPLICATE_CLAIM.

**`flag_for_review`** — sets `flagged_for_review=True` and `status=MANUAL_REVIEW` on appeal. The claims table already has this column so no migration needed.

---

### `app/db/seed.py`

Seeds EMP001–EMP010 matching the 10 test cases in `test_cases.json`. EMP005 (Vikram Joshi) has `join_date=2024-09-01` — this is intentional, it's the member used for TC005 (diabetes waiting period test, joins Sep 1, treatment Oct 15 = 44 days, which is < 90-day diabetes wait).

All other members join Jan 1, 2024, well before any test treatment dates.

---

### `app/schemas/documents.py`

Pydantic v2 models for each of the 4 document types. These define what the LLM is expected to return.

**Why everything is `Optional`:** The LLM may return `null` for fields it can't read (illegible handwriting, B2B pharmacy bills with no patient name, etc.). If fields were required (`str` instead of `Optional[str]`), Pydantic would throw a `ValidationError` and the whole claim would crash. Making them Optional means partial/illegible docs pass validation and instead trigger the `ILLEGIBLE_DOCUMENTS` rule via the low `extraction_confidence` score.

**`extraction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)`** — `ge` and `le` are Pydantic v2 constraints (greater-than-or-equal, less-than-or-equal). The default of 0.5 is intentionally neutral — not so low it triggers the illegibility rule, not so high it masks a real issue.

**`is_generic: Optional[bool]`** — `True` if the medicine is a generic salt (Paracetamol), `False` if branded (Crocin). Drives the 30% branded drug copay calculation.

**`is_covered: Optional[bool]`** in `BillLineItem` — `False` means the LLM flagged this item as cosmetic/excluded. Used in the COSMETIC_PROCEDURE partial approval calculation to find which items to deduct.

---

### `app/schemas/decisions.py`

Pydantic model for the decision output. Not directly used for DB storage (the DB models do that), but serves as documentation of the decision shape and is useful if you ever want to add response validation to the API.

---

### `app/services/extractor.py`

The document intelligence layer. Handles two modes:

**Vision mode** (`extract_document_from_image`): for real uploads
1. Load image or PDF (`_load_image`) — PDFs are converted to PIL Images via pdf2image at 150 DPI; multi-page PDFs are stitched vertically into one tall image
2. Resize and encode to base64 JPEG (`_image_to_b64`) — max dimension 1600px, quality 85. This balances token cost vs. legibility
3. Send to `meta-llama/llama-4-scout-17b-16e-instruct` (Groq's vision model) with image + instructions
4. Parse response JSON, validate with Pydantic, return dict

**Text mode** (`extract_document`): for test-submit (no images)
Same prompts, same models, but sends raw text to `llama-3.3-70b-versatile` (text-only LLM).

**Why leading underscores on module-level variables:**
```python
_client: Optional[Groq] = None
_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
_SCHEMAS = {...}
_INSTRUCTIONS = {...}
_FEW_SHOT = {...}
```
The single underscore convention means "private to this module — don't import these directly." Only `extract_document_from_image` and `extract_document` are meant to be used externally. The dicts and model names are implementation details.

**`_client` lazy initialization:**
```python
def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client
```
The Groq client is created on first use, not at import time. This matters because at import time, the `.env` file might not be loaded yet (especially during testing). Lazy init ensures the API key is always available when the client is actually needed.

**System prompt structure per doc type:**
```
[Task-specific instructions + rules]
[JSON Schema the model must populate]
[One-shot example of perfect output]
```
The few-shot example shows the model exactly what valid JSON looks like for Indian medical documents — realistic names, proper registration formats, nested structures. This significantly improves extraction accuracy vs. just giving the schema alone.

---

### `app/services/aggregator.py`

Takes up to 4 extracted doc dicts and merges them into one unified claim dict that the rules engine can work with.

Key aggregations:
- **`amounts_by_category`** — built from `medical_bill.items[].category` + `medical_bill.consultation_fee`. Also adds `pharmacy_bill.total_amount` to the pharmacy bucket
- **`branded_drug_amount`** — sum of items where `is_branded=True` in pharmacy bill; used to calculate the 30% copay
- **`total`** — uses `claim_amount` passed by user if provided, else falls back to summing bill totals
- **`doc_dates`** — list of dates from all submitted docs; if they span >1 day, DATE_MISMATCH fires
- **`patient_names`** — names extracted from all docs; fuzzy-matched by rules engine
- **`avg_extraction_confidence`** — mean confidence across all submitted docs; if <0.5, ILLEGIBLE_DOCUMENTS fires
- **`raw_docs`** — the full original extracted dicts stored inside the aggregated claim so the violation node can access individual item amounts when calculating partial approval for cosmetic items

---

### `app/services/rules_engine.py`

Pure Python, zero LLM calls. Takes the aggregated claim and runs 19 deterministic checks.

**Module-level constants (all underscore-prefixed):**
```python
_DR_REG   = re.compile(r"^[A-Z]+/\d+/\d{4}$")
_AYUR_REG = re.compile(r"^AYUR/[A-Z]+/\d+/\d{4}$")
```
Compiled regex patterns for doctor registration validation. Pre-compiling at module level (not inside the function) means the regex is only compiled once, not on every call.

```python
_DIABETES_KW  = {"diabetes", "diabetic", "metformin", ...}
_HYPER_KW     = {"hypertension", "amlodipine", ...}
...
```
Sets (not lists) because `in` on a set is O(1), vs O(n) for a list. For small keyword counts this doesn't matter much, but it's the right data structure.

**The `_add` inner function:**
```python
def _add(code: str, desc: str, **kw):
    violations.append(code)
    details.append({"rule_code": code, "description": desc, **kw})
```
Defined inside `run_rules` so it has access to `violations` and `details` via closure. `**kw` lets callers attach extra context (e.g., `value=7500, limit=5000` for PER_CLAIM_EXCEEDED) without changing the signature.

**Rule ordering matters:**
- Rule 1 (BELOW_MIN_AMOUNT) runs before rules that check amounts — no point checking sub-limits on a ₹200 claim
- Rule 8–11 (member/policy/waiting) are nested — MEMBER_NOT_COVERED fires first; only if member exists do policy/waiting checks run
- Waiting period uses `elif` chains: initial 30-day takes priority; only if past 30 days does it check for condition-specific waits (diabetes 90d, hypertension 90d, maternity 270d, joint 730d)

**`_contains_any(text, keywords)`:** Returns the matching keyword (not just True/False) so the violation description can say *which* keyword triggered it (e.g., "cosmetic procedure detected ('botox')").

**Copay is not a violation:**
```python
# --- Copay / discount (not rejections) ---
if claim.get("is_network_hospital"):
    copay["network_discount"] = ...
else:
    copay["copay"] = ...
```
Copay is returned separately as a dict. It gets applied in `adjudication_llm_node` (clean path) as a deduction, not as a rejection reason. Network hospitals get a 20% discount; all others pay 10% copay. Both are mutually exclusive.

---

### `app/services/adjudicator.py`

LLM-based reasoning. Two functions:

**`explain_violations`** — called on the violation path. Takes the list of rule violation dicts, asks the LLM to write one empathetic 1–2 sentence explanation per violation with actionable guidance. Returns a list of `{rule_code, explanation}` pairs shown in the frontend.

**`run_final_adjudication`** — called on the clean path. Sends the full aggregated claim + policy summary to the LLM with three evaluation axes:
1. Medical necessity (does the diagnosis justify the treatment?)
2. Fraud signals (unusual patterns?)
3. Cross-document consistency (does the prescription diagnosis match the bill items?)

The LLM returns one of four decisions: APPROVED / PARTIAL / REJECTED / MANUAL_REVIEW.

**`_POLICY_SUMMARY`** is a compact one-line string injected into the final adjudication prompt:
```python
_POLICY_SUMMARY = (
    f"Policy: Plum OPD Advantage | "
    f"Annual limit: ₹{POLICY['coverage_details']['annual_limit']} | ..."
)
```
Pre-built at import time from the live policy values — always stays in sync with `policy_terms.json`.

**`lean_claim`:**
```python
lean_claim = {k: v for k, v in claim.items() if k != "raw_docs"}
```
The full aggregated claim includes `raw_docs` (the original extracted dicts for all 4 docs). This is needed internally but would add thousands of tokens to the LLM prompt unnecessarily. It's stripped before sending.

---

### `app/pipeline/graph.py`

The LangGraph state machine. Defines the flow as a directed acyclic graph (DAG).

**`PipelineState` (TypedDict):**
A TypedDict is a Python dict with type hints — used here instead of a Pydantic model because LangGraph requires the state to be a plain dict. Every node receives the full state and returns a dict of fields to update.

```python
files: Dict[str, str]       # doc_type → file path on disk (vision mode)
ocr_texts: Dict[str, str]   # doc_type → raw text (text mode)
```
Exactly one of these is populated per pipeline run. `extract_node` checks which one is populated and routes accordingly.

**Node flow:**
```
extract_node
    ↓
aggregate_node
    ↓
rules_node
    ↓ (conditional)
    ├── violations exist → violation_llm_node
    └── no violations   → adjudication_llm_node
```

**`_COSMETIC_KW` at module level (line 21):**
```python
_COSMETIC_KW = {"whitening", "bleaching", "cosmetic", ...}
```
Used inside `violation_llm_node` for calculating cosmetic item amounts to deduct in partial approval. Defined at module level (with `_` prefix) to avoid recreating the set on every call.

**Violation path decision logic:**
```python
manual_review_codes = {"SUSPICIOUS_PATTERN"}
soft_codes          = {"COSMETIC_PROCEDURE", "SUB_LIMIT_EXCEEDED"}
review_codes        = codes & manual_review_codes
hard_codes          = codes - soft_codes - manual_review_codes
```
- `SUSPICIOUS_PATTERN` → always MANUAL_REVIEW (fraud indicators need human eyes)
- `COSMETIC_PROCEDURE` or `SUB_LIMIT_EXCEEDED` alone → PARTIAL (deduct the excess, approve the rest)
- Anything else → REJECTED

**Why copay isn't applied on the violation path:** If a claim has rule violations (e.g., late submission), it gets rejected regardless of whether it's at a network hospital. Copay/discounts only apply to legitimate claims that pass all rules.

---

### `app/api/claims.py`

The real submission endpoint. Handles multipart file uploads.

**`_ALLOWED_MIME`** — whitelist of accepted file types. Includes `image/jpg` explicitly because some browsers send this instead of `image/jpeg`.

**Upload flow:**
1. Generate `claim_id = f"CLM_{uuid4().hex[:8].upper()}"` — 8 hex chars ≈ 4 billion combinations
2. Create a directory `uploads/{claim_id}/` for this claim's files
3. Save each file as `{claim_id}/{doc_type}.{ext}` (e.g., `CLM_A1B2C3D4/prescription.jpg`)
4. Create the DB claim record immediately (status=PENDING)
5. Run the pipeline
6. Store each extracted document and the decision in DB
7. Update claim status to final decision

**Why create the DB record before running the pipeline:** The pipeline may take 5–15 seconds. If the server crashes mid-run, the claim is at least recorded. The status stays PENDING and can be investigated.

---

### `app/api/test_submit.py`

Identical flow to `claims.py` but accepts JSON body with raw text instead of file uploads. The `ocr_texts` dict is populated instead of `files`, so `extract_node` routes to text mode (uses `llama-3.3-70b-versatile` instead of the vision model). 

Claim IDs are prefixed `TST_` instead of `CLM_` so you can tell test submissions apart in the DB.

---

### `app/api/members.py`

Three endpoints:
- `GET /api/members` — returns all seeded members for the member ID dropdown
- `GET /api/members/{id}/stats` — YTD approved, remaining limit, sub-limits for the Claim History stats cards
- `GET /api/policy` — returns the full `policy_terms.json` for the Policy page

---

### `run_tests.py`

A standalone script (not a pytest suite) that hits the live `/api/claims/test-submit` endpoint with pre-written text representations of all 10 test cases. Each case has `expected_decision` and optionally `expected_approved` and `expected_rules`.

TC008 (fraud detection) has a `note` instead of `expected_decision` because it requires pre-existing same-day claims to trigger — you need to submit other claims for EMP008 first.

Run with: `python run_tests.py` or `python run_tests.py --case TC005`

---

## Frontend

### `App.jsx`

React Router setup with 4 routes:

| Path | Component | Purpose |
|------|-----------|---------|
| `/` | `NewClaim` | Submit a new claim |
| `/claims/:claimId` | `ClaimDetail` | View decision for a specific claim |
| `/history` | `ClaimHistory` | Look up all claims by member ID |
| `/policy` | `Policy` | Browse the full policy terms |

The nav highlights the active link using `useLocation()`.

---

### `pages/NewClaim.jsx`

3-step flow: Member Details → Upload Documents → Processing.

State: `files` object with 4 keys (`prescription`, `pharmacy_bill`, `diagnosis_test`, `medical_bill`), all null initially. `handleFile(docType, file)` updates whichever one was selected.

On submit: builds a `FormData`, appends all non-null files, POSTs to `/api/claims/submit`. On success, navigates to `/claims/{claimId}` passing the decision in `location.state` so the detail page can show it immediately without a second fetch.

Status message still shows "Running AI document extraction…" during the ~5–15 second pipeline run.

---

### `pages/ClaimDetail.jsx`

Fetches `GET /api/claims/{claimId}` and shows:
1. **DecisionCard** — the adjudication result
2. **Extracted Document Data** — per-doc structured fields with confidence bars
3. **Claim Details** — member ID, treatment date, amounts

`useEffect` tries to use `location.state.decision` first (immediately available after submit) while also firing the API fetch in parallel — so the page renders instantly after submit, then updates with full data when the fetch completes.

`DOC_FIELDS` maps each doc type to a list of `[label, extractorFn]` pairs. The extractor functions are called with `extracted_data` and return the display value (or null to skip the row). This avoids showing empty fields for data the LLM couldn't extract.

---

### `pages/ClaimHistory.jsx`

Member lookup + stats. Fires two requests in parallel via `Promise.allSettled`:
```javascript
const [claimsRes, statsRes] = await Promise.allSettled([
    axios.get('/api/claims', { params: { member_id: id } }),
    axios.get(`/api/members/${id}/stats`),
])
```
`allSettled` (not `all`) means if stats fail, claims still show — and vice versa.

`MemberStats` shows a progress bar where: green = <60% used, amber = 60–80%, red = >80%.

---

### `pages/Policy.jsx`

Fetches `/api/policy` (returns the live `policy_terms.json`) and renders it as structured cards. Because it reads from the live policy, any change to `policy_terms.json` is automatically reflected here without frontend changes.

---

### `components/DecisionCard.jsx`

Handles all 4 decision states with color coding:
- APPROVED: green
- REJECTED: red
- PARTIAL: amber
- MANUAL_REVIEW: blue

Shows:
- Claimed/approved amounts with deduction breakdown
- Confidence bar (green >80%, amber >60%, red otherwise)
- Rejection reasons with LLM-written explanations
- Fraud flags (if any)
- Manual review reasons (if any)
- Medical necessity verdict (from LLM)
- Notes + next steps
- "Request Manual Review" appeal button (visible on non-APPROVED decisions)

---

### `components/DocumentUpload.jsx`

Reusable file picker used 4 times in `NewClaim`. Handles drag-and-drop and click-to-browse. Accepts images and PDFs.

---

## Overall System Flow

```
User uploads files (or submits text via test-submit)
           │
           ▼
    FastAPI /api/claims/submit
           │
           ├─ Save files to disk (uploads/{claim_id}/)
           ├─ Create Claim record in DB (status=PENDING)
           ├─ Load member, YTD totals, same-day count from DB
           │
           ▼
    LangGraph Pipeline
    ┌─────────────────────────────────────────────────────┐
    │                                                     │
    │  extract_node                                       │
    │    vision mode: image → base64 → vision LLM → JSON │
    │    text mode:   raw text → text LLM → JSON         │
    │    (one LLM call per document type submitted)       │
    │                         │                           │
    │                         ▼                           │
    │  aggregate_node                                     │
    │    merges all 4 doc JSONs → unified claim dict      │
    │    computes: amounts by category, avg confidence,   │
    │    branded drug total, doc dates, patient names     │
    │                         │                           │
    │                         ▼                           │
    │  rules_node                                         │
    │    runs 19 deterministic checks (no LLM)            │
    │    returns: violations[], violation_details[], copay│
    │                         │                           │
    │          ┌──────────────┴───────────────┐          │
    │          │                              │          │
    │    violations?                    no violations     │
    │          │                              │          │
    │          ▼                              ▼          │
    │  violation_llm_node          adjudication_llm_node  │
    │    LLM explains each rule       LLM checks:         │
    │    violation in plain English   - medical necessity │
    │                                 - fraud signals     │
    │    SUSPICIOUS_PATTERN→         - cross-doc match    │
    │      MANUAL_REVIEW                                  │
    │    soft violations only→       → APPROVED           │
    │      PARTIAL (deduct excess)   → PARTIAL            │
    │    any hard violation→         → REJECTED           │
    │      REJECTED                  → MANUAL_REVIEW      │
    │                                                     │
    └─────────────────────────────────────────────────────┘
           │
           ▼
    Store in DB:
    - Document records (file_path, extracted_json, extraction_confidence)
    - Decision record (all 13 fields)
    - Update Claim status + approved_amount
           │
           ▼
    Return {claim_id, decision} to frontend
```

---

## Key Design Decisions

**Why LangGraph instead of plain functions?** LangGraph gives a named, inspectable graph with clean state passing between nodes. The conditional edge (`_route`) makes the two paths explicit. For a more complex pipeline (e.g., adding a human-in-the-loop node later), LangGraph is designed for it.

**Why Groq instead of OpenAI?** Groq's inference is significantly faster (useful for the 5-second scoring guideline). The Llama 4 Scout vision model on Groq is free-tier accessible for development.

**Why `rapidfuzz` for patient name matching?** Simple string equality would fail on "Rajesh Kumar" vs "Rajesh Kumar " (trailing space) or "R. Kumar" vs "Rajesh Kumar". `fuzz.token_sort_ratio` normalizes whitespace and is order-insensitive, so "Kumar Rajesh" and "Rajesh Kumar" score 100.

**Why `policy_terms.json` as the source of truth?** All limits, sub-limits, waiting periods, and copay percentages are read from this file at startup. The rules engine, adjudicator, and frontend policy page all derive their values from it. Changing the policy = changing the JSON. No code edits needed.

**Why store `extracted_json` as a JSON column?** The schema for each document type has ~15–20 fields with nested lists. Normalizing this into relational tables would require 8+ tables and complex joins. The JSON column lets you store whatever the LLM returns and query it if needed later.

---

## Coding Principles — The "Why" Behind Every Pattern

This section explains every recurring coding convention in the codebase. If you see a pattern and wonder why it was written that way, the answer is here.

---

### 1. Leading Underscore `_` on Variables and Functions

You'll see this everywhere:

```python
_client: Optional[Groq] = None          # extractor.py
_VISION_MODEL = "meta-llama/..."         # extractor.py
_SCHEMAS = {...}                          # extractor.py
_DR_REG = re.compile(...)               # rules_engine.py
_policy_path = Path(...)                 # config.py
_add = lambda ...                        # inside run_rules()
```

**The rule:** A single leading underscore means "this is private — do not import or use this from outside this module (or outside this function)."

Python does not enforce access control like Java's `private` keyword. The underscore is purely a convention, but it's universally understood. It communicates two things:
1. **To a reader:** "This is an implementation detail. You don't need to know how it works, just use the public functions."
2. **To a linter/IDE:** Most IDEs won't auto-suggest `_`-prefixed names when you type `from module import ...`. It's a hint to stay out.

**Concrete examples in this project:**

`_client` in `extractor.py` — the Groq client object. External code should call `extract_document_from_image()`, not reach in and grab the client directly. If Groq ever changes their SDK, only `extractor.py` needs updating.

`_SCHEMAS`, `_INSTRUCTIONS`, `_FEW_SHOT` — internal lookup dicts that map doc type strings to their Pydantic classes and prompt text. These are wired together inside `_build_system()`. External code just calls `extract_document()`.

`_add` inside `run_rules()` — a closure (see section 5). Not accessible from outside the function at all.

`_f` in `config.py` — the file handle used to read `policy_terms.json`. It's immediately consumed and never needed again. The underscore signals throwaway variable.

**Double underscore `__`** (not used here but worth knowing) — Python actually enforces this one. `__name` triggers name mangling and genuinely can't be accessed from outside the class in normal usage. Single underscore is convention; double underscore is enforcement.

---

### 2. Module-Level Constants vs. Re-computing Inside Functions

In `rules_engine.py`:
```python
# At module level, outside any function
_DR_REG   = re.compile(r"^[A-Z]+/\d+/\d{4}$")
_AYUR_REG = re.compile(r"^AYUR/[A-Z]+/\d+/\d{4}$")

_DIABETES_KW = {"diabetes", "diabetic", "metformin", ...}
_COSMETIC_KW = {"whitening", "bleaching", "cosmetic", ...}
```

**Why not define these inside `run_rules()`?**

`run_rules()` is called once per claim submission. If you defined `_DR_REG = re.compile(...)` inside the function, Python would recompile the regex every single call. `re.compile` is not free — it parses the pattern string and builds an internal finite automaton. Doing it once at module load time (which happens once when the server starts) and reusing it is the correct approach.

Same logic for the keyword sets. A `set` literal constructed inside a function is rebuilt every call. At module level it's built once.

**The principle: compute once, reuse many times.** Anything that doesn't change between calls belongs at the top of the file, not inside the function.

---

### 3. Lazy Initialization (The `_get_client()` Pattern)

```python
_client: Optional[Groq] = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client
```

This pattern — initialize only on first use — is called **lazy initialization**.

**Why not just do `_client = Groq(api_key=settings.groq_api_key)` at module level?**

Two reasons:

1. **Timing:** When Python imports `extractor.py`, it runs all module-level code immediately. At that moment, `settings.groq_api_key` might be an empty string — the `.env` file might not be loaded yet depending on import order. With lazy init, the client is created only when the first actual extraction call happens, by which time everything is guaranteed to be loaded.

2. **Test isolation:** In tests, you might want to import the module without triggering a real Groq client creation (which would fail if there's no API key). Lazy init means importing the module is always safe.

The `global _client` line is needed because Python distinguishes between reading a global variable (allowed inside a function without declaration) and writing to it (requires `global` declaration). Without it, `_client = Groq(...)` would create a new local variable instead of updating the module-level one.

---

### 4. `Optional[str] = None` Everywhere in Schemas

In `documents.py`:
```python
class PrescriptionData(BaseModel):
    doctor_name: Optional[str] = None
    patient_name: Optional[str] = None
    diagnosis: Optional[str] = None
    ...
```

**Why not `doctor_name: str` (required)?**

Pydantic v2 validates every field. If `doctor_name` is declared as `str` and the LLM returns `{"doctor_name": null, ...}`, Pydantic raises a `ValidationError` and the entire extraction fails. The claim would error out.

The LLM correctly returns `null` for fields it can't read — a handwritten prescription where the doctor's name is illegible should not cause the entire claim to fail. It should extract what it can, set confidence low, and let the rules engine decide what to do (ILLEGIBLE_DOCUMENTS rule fires if avg confidence < 0.5).

**`Optional[str]` is literally `Union[str, None]`** — it tells Pydantic "this field can be a string or null, and null is fine." The `= None` is the default value, so if the LLM omits the field entirely, it defaults to `None` rather than erroring.

**The principle:** Be strict about structure (always return a valid Pydantic object), be lenient about content (individual fields can be absent). This is sometimes called the Robustness Principle or Postel's Law: "be conservative in what you send, liberal in what you accept."

---

### 5. Closures — The `_add` Inner Function

In `run_rules()`:
```python
def run_rules(...):
    violations: List[str] = []
    details: List[Dict] = []

    def _add(code: str, desc: str, **kw):
        violations.append(code)
        details.append({"rule_code": code, "description": desc, **kw})

    # ... 19 rules each calling _add(...)
```

`_add` is defined inside `run_rules`. It's a **closure** — a function that "closes over" the variables from its enclosing scope. `_add` can see and modify `violations` and `details` even though they're not passed as arguments.

**Why this instead of `violations.append(code); details.append({...})` inline?**

Without `_add`, every rule would be:
```python
violations.append("LATE_SUBMISSION")
details.append({"rule_code": "LATE_SUBMISSION", "description": "..."})
```

That's two lines per rule, always in sync. If you ever change the structure of `details` (e.g., add a `severity` field), you'd have to update all 19 rules. With `_add`, you change one place.

It's also less error-prone — you can't accidentally append to `violations` without appending to `details`, or vice versa.

The `**kw` (keyword arguments catch-all) lets some rules pass extra structured data:
```python
_add("PER_CLAIM_EXCEEDED", "...", value=7500, limit=5000)
```
This gets merged into the details dict and can be used by downstream logic or displayed in the UI.

---

### 6. `**kw` — Variable Keyword Arguments

```python
def _add(code: str, desc: str, **kw):
    details.append({"rule_code": code, "description": desc, **kw})
```

`**kw` collects any extra keyword arguments into a dict. `**kw` in the `dict()` call then spreads them back in. So:

```python
_add("SUB_LIMIT_EXCEEDED", "Dental exceeded", category="dental", value=12000, limit=10000)
# → {"rule_code": "SUB_LIMIT_EXCEEDED", "description": "Dental exceeded",
#    "category": "dental", "value": 12000, "limit": 10000}
```

This pattern gives flexibility without changing the function signature every time a new rule needs to attach different metadata. Rules that don't need extra context just call `_add("CODE", "description")`.

---

### 7. TypedDict for Pipeline State

```python
class PipelineState(TypedDict):
    claim_id: str
    files: Dict[str, str]
    violations: List[str]
    decision: Optional[Dict]
    ...
```

LangGraph requires the state to be a dict (or TypedDict). **Why TypedDict instead of a Pydantic `BaseModel`?**

LangGraph merges partial updates from each node. When `extract_node` returns `{"prescription": {...}}`, LangGraph merges that into the existing state dict. Pydantic models are immutable after creation — you can't merge partial updates into them cleanly. TypedDict is just a regular Python dict with type hints layered on top, so LangGraph can manipulate it freely.

The type hints still give you IDE autocompletion and type-checker warnings inside the node functions.

---

### 8. `default=datetime.utcnow` vs `default=datetime.utcnow()`

In `models.py`:
```python
created_at = Column(DateTime, default=datetime.utcnow)    # ✅ correct
created_at = Column(DateTime, default=datetime.utcnow())  # ❌ wrong
```

The difference is subtle but critical. The parentheses `()` call the function. Without them, you're passing the function itself as a reference.

- `default=datetime.utcnow()` — evaluated once when Python imports the file. Every row gets the same timestamp: the server start time.
- `default=datetime.utcnow` — SQLAlchemy receives the function object and calls it fresh for each new row. Each row gets its actual creation time.

This is a very common Python gotcha with mutable or time-dependent defaults.

---

### 9. Sets for Keyword Lookup

```python
_DIABETES_KW = {"diabetes", "diabetic", "type 1 diabetes", "metformin", "glimepiride", "insulin"}
```

A `set` (curly braces, no key-value pairs) instead of a `list`. Both support `in` checks:
```python
"diabetes" in _DIABETES_KW   # works on both set and list
```

**Why set?** `in` on a `list` is O(n) — it scans every element until it finds a match. `in` on a `set` is O(1) — it hashes the value and does a direct lookup. For 6 keywords this doesn't matter at all, but it's the semantically correct choice: a collection of unique lookup values with no order is a set by definition, not a list.

---

### 10. `coalesce` in SQL Aggregation

```python
result = db.query(func.coalesce(func.sum(Claim.approved_amount), 0)).filter(...)
```

`SUM()` on an empty result set returns `NULL` in SQL, not 0. If a member has no approved claims yet, `SUM(approved_amount)` would return `NULL`, and then `float(None)` in Python would raise a `TypeError`.

`COALESCE(SUM(...), 0)` — "use the sum, but if it's NULL, use 0 instead." Guaranteed to return a number.

---

### 11. `Promise.allSettled` vs `Promise.all`

In `ClaimHistory.jsx`:
```javascript
const [claimsRes, statsRes] = await Promise.allSettled([
    axios.get('/api/claims', ...),
    axios.get(`/api/members/${id}/stats`),
])
```

**`Promise.all`** — if any promise rejects, the whole thing throws. If `/api/members/{id}/stats` fails (member not found), you'd lose the claims list too, even though it succeeded.

**`Promise.allSettled`** — waits for all promises to settle (resolve or reject) and gives you both results. The status field tells you whether each one succeeded. This way, if stats fail you still show the claims table, and vice versa.

---

### 12. Inline Styles in React (`const s = {...}`)

All frontend components use a single `const s = {...}` style object at the top:
```javascript
const s = {
  heading: { fontSize: 24, fontWeight: 700 },
  btn: { background: '#6d28d9', ... },
  barFill: pct => ({ width: `${pct}%`, ... }),   // ← function for dynamic styles
}
```

**Why not CSS files or Tailwind?**

For an assignment that needs to be self-contained and easy to run, inline styles eliminate the CSS tooling dependency. Everything is co-located with the component — no jumping between files to understand what something looks like.

**The `s` convention:** Short for "styles." Using `s.heading`, `s.btn` throughout the component is concise and readable. The object is defined outside the component function so it's not recreated on every render.

**Function values** like `barFill: pct => (...)` handle dynamic styles (colors that change based on a percentage) without needing string concatenation in JSX. Used for things like the confidence bar color changing from green → amber → red.

---

### 13. The `lean_claim` Pattern

In `adjudicator.py`:
```python
lean_claim = {k: v for k, v in claim.items() if k != "raw_docs"}
```

The aggregated claim dict includes `raw_docs` — the full original extracted JSON from all 4 documents. This can be thousands of tokens. Sending it all to the LLM is wasteful and expensive.

The `lean_claim` dict comprehension creates a copy of `claim` with `raw_docs` stripped. Everything the LLM needs for adjudication (diagnosis, amounts, dates, patient names, doctor info) is at the top level of the claim dict. The raw docs are only needed internally (e.g., to find individual bill item amounts in the violation node).

**The principle:** Only send the LLM what it actually needs. Fewer tokens = faster response + lower cost.

---

### 14. `try/except` in `extract_node`

```python
try:
    extracted[doc_type] = extract_document_from_image(doc_type, file_path)
except Exception as e:
    print(f"[extract] vision failed for {doc_type}: {e}")
    extracted[doc_type] = None
```

If the LLM call for one document fails (network timeout, model error, malformed response), the extraction for that document is set to `None`. The pipeline continues with the other documents.

Without this, a single bad document would crash the entire pipeline and the user would get a 500 error with no useful feedback. With it, the pipeline continues, the failing document is treated as absent, and if it was required (e.g., prescription), the MISSING_DOCUMENTS rule fires with a clear explanation.

**The principle:** Fail gracefully at the component level, not catastrophically at the system level. Isolate failures to the smallest possible scope.

---

### 15. Why `response_format={"type": "json_object"}` on Every LLM Call

```python
response = _get_client().chat.completions.create(
    model=_TEXT_MODEL,
    response_format={"type": "json_object"},
    ...
)
```

Without this, an LLM might return:
```
Here's the extracted data from the prescription:
{"doctor_name": "Dr. Sharma", ...}
```

That markdown prose prefix would cause `json.loads()` to fail. `response_format={"type": "json_object"}` forces the model to return only valid JSON with no surrounding text. Groq supports this for all their models. This is why we never need to strip markdown code fences or parse around prose.

---

### 16. Separation of Concerns — Why the Pipeline Has 5 Separate Files

```
extractor.py    — LLM calls for extraction only
aggregator.py   — data merging only, no LLM, no DB
rules_engine.py — rule logic only, no LLM, no DB
adjudicator.py  — LLM calls for reasoning only
graph.py        — wires them together, no business logic itself
```

Each service file does exactly one thing. `rules_engine.py` has no idea the results came from a vision LLM — it just receives a dict and applies rules. `aggregator.py` doesn't know about LangGraph. This means:

- You can unit test `rules_engine.py` by passing any dict, no LLM mocking needed
- You can swap the LLM in `extractor.py` without touching anything else
- `graph.py` is purely orchestration — if you want to add a new node (e.g., an OCR fallback), you add it in `graph.py` and write a new service file; existing files stay untouched

**The principle:** Single Responsibility — each module has one reason to change.

---

### 17. Why `Base.metadata.create_all` at Startup (Not a Migration Tool)

```python
Base.metadata.create_all(bind=engine)
```

This creates all tables defined in `models.py` if they don't exist yet. It's idempotent — safe to call on every startup. Existing tables and data are untouched.

**Why not Alembic (the standard migration tool)?** Alembic is the right choice for production systems where the schema evolves over time and you need to track changes. For this assignment, the schema is fixed. `create_all` is simpler and sufficient — no migration files, no version tracking, just "create the tables if they aren't there."

---

### 18. `uuid4().hex[:8].upper()` for Claim IDs

```python
claim_id = f"CLM_{uuid4().hex[:8].upper()}"
# → "CLM_A1B2C3D4"
```

`uuid4()` generates a cryptographically random 128-bit UUID. `.hex` gives the 32-character hex string (no dashes). `[:8]` takes the first 8 characters. At 8 hex chars = 32 bits, there are ~4 billion possible IDs — collision probability is negligible for any realistic claim volume.

`.upper()` is purely aesthetic — `CLM_A1B2C3D4` is more readable than `CLM_a1b2c3d4` in the UI.

**Why not sequential integers?** Sequential IDs leak business information (claim #1000 tells a competitor you've processed 1000 claims). They're also harder to shard across databases. Random IDs are better practice for external-facing identifiers.

---

### 19. `elif` Chains in Waiting Period Logic (Not `if` Chains)

```python
if days_in < WAITING["initial"]:          # 30 days
    _waiting("initial", ...)
elif _contains_any(text, _DIABETES_KW):   # 90 days
    _waiting("diabetes", ...)
elif _contains_any(text, _HYPER_KW):      # 90 days
    _waiting("hypertension", ...)
elif _contains_any(text, _MATERNITY_KW):  # 270 days
    _waiting("maternity", ...)
elif _contains_any(text, _JOINT_KW):      # 730 days
    _waiting("joint_replace", ...)
```

**Why `elif` and not `if` for each?**

With `if` chains, every condition is evaluated independently. A diabetic patient who joins the scheme and submits a claim on day 10 would trigger both the initial waiting period (day 10 < 30) AND the diabetes waiting period (day 10 < 90) — two separate violation entries for what is really one problem.

With `elif`, only the first matching condition fires. The initial waiting period takes priority — it subsumes everything else for new members. Only once past 30 days do the condition-specific waits get checked. This mirrors how real insurance works: you don't get penalized twice for the same timing issue.

---

### 20. `model_validate` + `model_dump` Round-Trip

```python
validated = schema_class.model_validate(raw)    # dict → Pydantic model
return validated.model_dump()                    # Pydantic model → dict
```

This could have been written as just `return raw` (return the raw dict from the LLM). The round-trip through Pydantic serves two purposes:

1. **Validation:** If the LLM returns `{"extraction_confidence": 1.5}` (out of range), Pydantic raises a `ValidationError`. The `ge=0.0, le=1.0` constraint on the field is enforced here. If the LLM hallucinates a field name (`"doktor_name"` instead of `"doctor_name"`), it's silently ignored — only known fields survive.

2. **Normalization:** `model_dump()` returns a consistently structured dict with all fields present (None for missing ones), all types correct. The aggregator and rules engine can rely on a predictable structure, not whatever the LLM happened to return.

---

## System Design Principles

### Separation of AI and Rules

The hardest design decision was deciding what the LLM should do vs. what deterministic code should do.

**Rules engine (no LLM):** Anything that is objectively true or false — "is this date within 30 days?", "does this amount exceed ₹5000?", "does this regex match?" These have one correct answer. An LLM adds no value here and introduces non-determinism (the LLM might occasionally get a date calculation wrong).

**LLM (violation explanations):** The rules engine knows a violation happened. The LLM knows how to explain it in empathetic plain English that a claimant can act on. "MISSING_DOCUMENTS" is a code; "We couldn't find a prescription from a registered doctor. Please attach a valid prescription and resubmit." is what a person needs to read.

**LLM (final adjudication):** Medical necessity, fraud signals, and cross-document consistency require judgment — reasoning about whether a diagnosis makes sense given the patient's age, whether prescribed medicines align with the diagnosis, whether the pattern of claims looks unusual. These are inherently fuzzy and LLMs handle them better than hard rules.

**The division:** Deterministic questions → rules engine. Judgment calls and natural language → LLM. Never use an LLM where a calculation suffices. Never use a calculation where judgment is required.

---

### Fail Fast at Boundaries, Trust Internally

The API layer validates file types (MIME whitelist) and required fields. Inside the pipeline, components trust each other. `aggregator.py` doesn't re-validate that `prescription` is a dict — `extract_node` already ensured it. `rules_engine.py` doesn't re-validate amounts are floats — the aggregator already did `.get("total", 0)` with a numeric default.

**Why:** Defensive validation everywhere creates noise — code that checks for conditions that "can't happen." Validate at system boundaries (user input, LLM output), trust internal contracts.

---

### One Source of Truth for Policy

`policy_terms.json` → loaded into `POLICY` dict in `config.py` → imported by `rules_engine.py`, `adjudicator.py`, `aggregator.py`, `members.py`.

No hardcoded numbers anywhere in application code. `ANNUAL_LIMIT = POLICY["coverage_details"]["annual_limit"]` — one read, named constant reused everywhere. If Plum changes the annual limit from ₹50,000 to ₹75,000, one file changes and everything updates.

---

### Two Submission Paths, One Pipeline

`/api/claims/submit` (file upload) and `/api/claims/test-submit` (raw text) both invoke the same `pipeline.invoke(initial)`. The only difference is which fields of `PipelineState` are populated (`files` vs `ocr_texts`). `extract_node` checks which is populated and routes accordingly.

This means every bug fix, rule change, or LLM improvement to the pipeline automatically applies to both paths. No duplicated business logic.

---

### Frontend Reads Live Data

The Policy page fetches `/api/policy` (which returns `policy_terms.json`). The Claim History stats page fetches `/api/members/{id}/stats` (which reads from DB). Nothing is hardcoded in the frontend.

If the annual limit changes in the JSON, the Policy page shows the new value automatically. If a member's approved claims increase, the stats page shows the updated remaining limit.

**The principle:** The frontend is a display layer, not a data store. All source-of-truth data lives in the backend.