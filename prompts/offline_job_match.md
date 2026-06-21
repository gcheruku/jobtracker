# Offline Semantic Job Match

Score how well the resume matches each job **offline**, using sentence-embedding
similarity instead of an LLM call — so most jobs get a match score for free
(no API cost), and the LLM is reserved for the on-demand "Compare with Resume".

## Requirements
1. After jobs are retrieved, compute the resume↔job-description match with
   **semantic similarity via `sentence-transformers`**.
2. This needs the full job description, so **pull it from the posting link**.
3. **Run during Fetch**, and show the task running until it finishes.
4. Provide a **separate task** to run it on all existing jobs that **do not have
   an LLM match score**.
5. If a job already has an LLM match score, **skip** the semantic similarity.

## How it's implemented
- **Model:** `all-MiniLM-L6-v2` (configurable via `SEMANTIC_MODEL`); the resume is
  embedded once and cached, each JD is embedded, and the score is the cosine
  similarity scaled to 0–100. See `backend/app/services/semantic.py`.
- **JD source:** fetched from the job's link (`services/jd_fetch.py`), with
  LinkedIn rewritten to its public guest view and Glassdoor's React markup
  handled; JSON-LD `JobPosting` is preferred.
- **During Fetch:** each newly-ingested job is scored inline; the "Fetch alerts"
  button shows progress until done.
- **Batch task:** Settings → *Offline semantic matching → Run semantic matching*
  scores active-board jobs that lack any score, with a live progress bar. Inactive
  jobs are skipped, and every attempt is recorded so un-scorable links (closed /
  blocked postings with no fetchable JD) aren't retried forever.
- **Precedence:** the card shows the detailed Compare score if present, else the
  semantic score (marked with `≈`), else the initial ingestion score.
