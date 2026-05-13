## Summary

<!-- 1-3 bullets on what changed and why. -->

## Linked issue

Closes #

## Tests
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated (if crossing a boundary)
- [ ] `uv run pytest` passes locally

## Docs
- [ ] Function docstrings (Google style) on any new/changed code
- [ ] README / PROJECT_PLAN updated if user-facing behavior or stack changed

## Pre-merge deploy steps

The deploy workflow auto-runs on push to `main`, so out-of-band ops must
happen **before** the merge to avoid serving requests against missing
infra. See [`infra/README.md` § "Out-of-band deploy steps"](../infra/README.md#out-of-band-deploy-steps)
for the playbook.

- [ ] No Firestore composite indexes added — *or* indexes deployed via
      `gcloud firestore indexes composite create` (one-time, then READY)
- [ ] No new denormalized fields read by queries — *or* a backfill
      script lives under `backend/scripts/` and is **run before merge**
      so old docs don't disappear from the new query path
- [ ] No new env vars / secrets / Cloud Run settings — *or* applied via
      `gcloud run services update` and recorded in `infra/README.md`
- [ ] If any of the above don't apply, leave them unchecked and explain
      in the Summary why this PR is safe to auto-deploy

