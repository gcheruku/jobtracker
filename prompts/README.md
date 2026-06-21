# Prompts & references

The prompts used to build JobTrack (and one reference file), kept for provenance.

| File | What it specifies |
|------|-------------------|
| [build_prompt.md](build_prompt.md) | Original spec: decoupled FastAPI + React job-tracking dashboard, built from the figma design. |
| [figma_design.png](figma_design.png) | The base UI design referenced by `build_prompt.md`. |
| [job_retrieval_prompt.md](job_retrieval_prompt.md) | Gmail "Job alerts" ingestion: scheduled + manual fetch, parse, dedup. |
| [offline_job_match.md](offline_job_match.md) | Offline resume↔JD match via sentence-transformers. |
| [reference_email_parsers.py](reference_email_parsers.py) | Reference parser (from a previous project) for Indeed/Glassdoor alert formats; its approach is adapted in `backend/app/services/alert_parsers.py`. |
