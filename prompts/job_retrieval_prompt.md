# Job Retrieval from Gmail

Ingest job alerts from Gmail (Dice, LinkedIn, Glassdoor, Indeed) into the
tracker, on a schedule and on demand.

## Inputs / setup
- `backend/.env` holds the Google and OpenAI keys; the Google API key is used for
  job-fit comparison (Gemini).
- `Resume.docx` (repo root) is the resume scored against each job description.
- `backend/secrets/{credentials.json,token.json}` authorize read-only Gmail access.
- Gmail has a **`Job alerts`** label with alerts from Dice, LinkedIn, Glassdoor,
  and Indeed.

## Requirements
1. A **background task that runs every 4 hours**.
2. The task **fetches the latest `Job alerts` emails and extracts job info**.
3. Use the **latest discovery timestamp in the database** as the watermark — only
   fetch alerts delivered after it.
4. **Save the latest fetch timestamp** for the next run.
5. **Dedup by the posting link** — some alerts are resent (and the same role is
   often listed as multiple distinct postings).
6. A **manual "Fetch alerts" button** in the UI to trigger ingestion on demand.

See `backend/app/services/{gmail_client,email_parser,alert_parsers,ingest}.py`
and `backend/app/scheduler.py`.
