# Planted demo scenario (`Jibril1001/test_repo`)

This repo is the **investigation target** for Incident Detective. It was
seeded with a reproducible "mystery" so the agent has a real culprit to find.

## Commits

Backdated history (8 filler commits + 1 culprit):

| Date (UTC)        | Commit message |
|-------------------|----------------|
| 2026-10-16 14:36  | Add project overview and usage |
| 2026-10-16 20:36  | Pin service dependencies |
| 2026-10-17 02:36  | Add checkout package skeleton |
| 2026-10-17 08:36  | Add payment gateway client |
| 2026-10-17 16:36  | Add auth token service |
| 2026-10-17 23:36  | Add search relevance module |
| 2026-10-18 05:36  | Centralize logging configuration |
| 2026-10-18 18:36  | Tune search relevance weights |
| **2026-10-19 11:09** | **Reduce payment client timeout from 30s to 3s** ← culprit |

**Culprit SHA:** `e2c335c89c067216c7ed423288d048ec8fa0f3f0`
(force-updated dates; touches `checkout/payment_client.py`, changing `TIMEOUT_S`
from `30.0` to `3.0`).
This SHA is written to `data/demo_sha.txt` and used as the `commit_sha` of the
planted `checkout` deploy row in `data/seed.py`.

## Issues (created via GitHub API)

- #1 Intermittent payment failures at checkout
- #2 Checkout latency spiked this morning
- #3 Payment gateway timeouts under load

## Recreating from scratch

If the repo is ever reset, the planting steps are:

1. Create the files listed above (see the git history for exact contents).
2. Commit them with the dates above (`GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE`).
3. Update `data/demo_sha.txt` with the new culprit SHA.
4. Create the three issues (see `issues.ps1` used during setup).
