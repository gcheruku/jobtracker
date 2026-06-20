"""Load the resume text used for match scoring (cached after first read)."""
from __future__ import annotations

from functools import lru_cache

from ..config import RESUME_DOCX_PATH
from ..logging_config import logger


@lru_cache(maxsize=1)
def resume_text() -> str:
    path = RESUME_DOCX_PATH
    if not path.exists():
        logger.warning("Resume not found at %s — scoring will be skipped", path)
        return ""
    try:
        import docx

        doc = docx.Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        logger.info("Loaded resume (%d chars) from %s", len(text), path.name)
        return text
    except Exception:
        logger.exception("Failed to read resume at %s", path)
        return ""
