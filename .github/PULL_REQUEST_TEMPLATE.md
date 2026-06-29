## Summary

What does this PR change, and why?

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactor / tech debt
- [ ] CI / deployment

## How was this tested?

- [ ] Backend starts cleanly (`uvicorn app.main:app`), `/docs` loads
- [ ] Frontend builds (`npm run build`) and runs (`npm run dev`)
- [ ] Manual verification of the affected flow (describe below)

Describe your testing:

## Checklist

- [ ] Routers stayed thin; logic lives in `services/`
- [ ] Config additions go through `app/config.py`
- [ ] Graceful degradation preserved (no key → clear message, no crash)
- [ ] No secrets, real resume, or `jobs.db` committed
- [ ] Docs / CHANGELOG updated if behavior changed

## Related issues

Closes #
