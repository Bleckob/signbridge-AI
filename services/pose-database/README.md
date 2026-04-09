# pose-database

Sign pose storage, user auth, session management, and privacy enforcement for SignBridge AI.
This service owns all Supabase data assets and is the legal privacy boundary of the system.

---

## What this service does

- Stores 300+ ASL sign poses as MediaPipe quaternion keyframes in Supabase
- Manages user authentication (anonymous + email/password)
- Tracks session start/end for organisations
- Enforces NDPA 2023 compliance — zero audio or transcript data is ever stored

---

## Owned by

**Isaac** — Task 05  
Connects to: Amos (gloss sync), David (bone names), Blessing (API key validation + backend queries)

---

## Setup

### 1. Prerequisites

- Python 3.11.x (required — MediaPipe does not support 3.12+)
- Access to the Supabase project (request invite from Blessing)

### 2. Create and activate virtual environment
```bash
cd services/pose-database
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up your .env file

Create a `.env` file inside `services/pose-database/`. Never commit this file.
```bash
cp .env.example .env
```

Then fill in the values — get them from Blessing or the team Notion page:
```
SUPABASE_URL = https://fcepkutnrpantadbdcch.supabase.co

SUPABASE_ANON_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZjZXBrdXRucnBhbnRhZGJkY2NoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ5MTY4NjUsImV4cCI6MjA5MDQ5Mjg2NX0.G7DsJViYw4OWJO6xCjFPnmtokUe6d2oF5AUXNlc2P0c

SUPABASE_SERVICE_ROLE_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZjZXBrdXRucnBhbnRhZGJkY2NoIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDkxNjg2NSwiZXhwIjoyMDkwNDkyODY1fQ.0nkvVplN0ijQ87C6xwXrx-9zbogfQhBhylL2CXvLgQM

REDIS_URL = redis://default:9YCXQUtZP3sqL15zLIPkOhQSHZ2smHBC@redis-13800.c73.us-east-1-2.ec2.cloud.redislabs.com:13800

SENTRY_DSN = https://your-sentry-dsn
```

### 5. Set up the database

Step 1 — paste schema.sql into Supabase SQL editor and run it
        (creates tables, enables RLS, attaches all policies)

Step 2 — run this to populate bone names from bone_names.py

```bash
python setup_db.py
```

Step 3 — enable Anonymous + Email/Password Auth in the dashboard
        Authentication → Providers → toggle each one on

---

## Environment variables

| Variable | Where to get it |
|---|---|
| `SUPABASE_URL` | Blessing / Supabase dashboard → Settings → API |
| `SUPABASE_ANON_KEY` | Blessing / Supabase dashboard → Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase dashboard → Settings → API (keep secret) |
| `REDIS_URL` | Blessing (Upstash, set up in her Week 1) |
| `SENTRY_DSN` | Blessing (configured during CI setup) |

---

## Database schema

Three tables live in this service. See `schema.sql` for the full definitions.

| Table | Purpose |
|---|---|
| `sign_poses` | Core pose store — gloss, quaternion keyframes, NMM tags, bone names |
| `organisations` | Registered orgs with API keys (used by Blessing's backend) |
| `sessions` | Session start/end timestamps per org — no audio, no transcript |

**Critical:** The `sessions` and `organisations` tables must never have `audio`, `audio_data`, `transcript`, or `speech_text` columns. This is a legal requirement under NDPA 2023.

---

## Running the scripts

### Extract a sign pose from video and upload to Supabase
```bash
python extract_poses.py --video path/to/sign.mp4 --gloss HELP --nmm '["eyebrows_up"]'
```

### Run the privacy enforcement test
```bash
pytest privacy_test.py -v
```

This test queries every table and asserts that zero rows contain audio or transcript data. It must pass before any release.

### Validate query latency
```bash
python -c "from latency_check import run; run()"
```

All `sign_poses` gloss lookups must return in under 50ms.

---

## Privacy & NDPA 2023

SignBridge operates in every form of human interaction and is bound by the Nigeria Data Protection Act 2023.

**What this service stores:**
- Sign pose keyframes (non-personal, derived from reference videos)
- Organisation metadata and API keys
- Session timestamps (start and end only)

**What this service never stores:**
- Audio recordings
- Speech transcripts
- Any individual-identifiable information

The `privacy_test.py` script is the automated proof of compliance. It runs in CI on every push via Blessing's GitHub Actions workflow.

For the full data flow audit see `PRIVACY_AUDIT.md`.  
For the human-readable privacy statement see `PRIVACY_STATEMENT.md`.

---

## Dependencies

See `requirements.txt` for pinned versions. Key packages:

| Package | Purpose |
|---|---|
| `mediapipe` | Extracts hand and body landmarks from video |
| `opencv-python` | Reads video files frame by frame |
| `supabase` | Python client for all Supabase queries and inserts |
| `numpy` | Quaternion math for keyframe conversion |
| `python-dotenv` | Loads the .env file |
| `pytest` | Runs the privacy test and unit tests |

---

## Key files
```
pose-database/
├── schema.sql            # All CREATE TABLE statements — run once in Supabase
├── extract_poses.py      # Video → MediaPipe → Supabase pipeline
├── auth_provider.tsx     # Supabase Auth context (used by David's frontend)
├── validate_api_key.py   # API key checker (used by Blessing's backend)
├── privacy_test.py       # NDPA 2023 compliance test
├── HOW_TO_ADD_SIGNS.md   # Guide for adding new signs after launch
├── PRIVACY_AUDIT.md      # Full data flow audit report
└── PRIVACY_STATEMENT.md  # Human-readable privacy statement
```

---

## Contacts & dependencies

| Who | What is needed from other team members |
|---|---|
| **Blessing** | Supabase project invite, Redis URL, Sentry DSN, backend pose query integration |
| **Amos** | Weekly gloss sync — NMM tags must match what the NLP engine outputs |
| **David** | Bone naming convention locked on Day 1, sign validation in Week 4 |