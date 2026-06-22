# JobTrack backend — FastAPI + SQLite (+ sentence-transformers).
FROM python:3.12-slim

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code only — personal data (db, secrets, resume, .env) is mounted at /data.
COPY app ./app

# Everything stateful lives on the mounted /data volume.
ENV JOBTRACKER_DATABASE_URL=sqlite:////data/jobs.db \
    GMAIL_CREDENTIALS_PATH=/data/secrets/credentials.json \
    GMAIL_TOKEN_PATH=/data/secrets/token.json \
    RESUME_DOCX_PATH=/data/Resume.docx \
    JOBTRACKER_RESUME_DIR=/data/uploads/resumes \
    HF_HOME=/data/hf-cache \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# No --reload in production (the in-process scheduler would double-start).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
