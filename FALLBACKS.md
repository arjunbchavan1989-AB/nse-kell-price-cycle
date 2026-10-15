# Daily EOD refresh and guarded fallbacks

All times are Asia/Kolkata:

- 19:30 primary: cron `0 14 * * *` UTC.
- 19:45 fallback: cron `15 14 * * *` UTC.
- 20:00 fallback: cron `30 14 * * *` UTC.

Each scheduled execution reads only this repository's own snapshot and verifies
the most recent completed NSE session from the dated official index archive.
Acquisition is skipped only when that session already matches a valid,
independently acquired snapshot. Build time alone is not proof of fresh prices.
Bootstrap/dependent snapshots and invalid/future timestamps cannot satisfy the
guard. A missing weekday archive is conservatively retried, not assumed to be
a holiday; known weekend sessions can reuse the latest verified completed day.
Thus a weekday holiday can cause extra checks rather than a false fresh result.

Manual `refresh_data=true` always forces acquisition. Manual false remains a
UI-only deployment. The job summary records the guard's decision. Publication
still runs after a fresh-data skip so an earlier failed Pages deploy can recover.
Existing scanner quality gates remain authoritative and retain the last good
snapshot if validation fails.

Concurrency is serialized per repository. Overlapping triggers do not run two
acquisitions in parallel. A later queued check rereads current `main`, then
checks freshness again after the preceding run finishes.

These backups improve resilience, but they use the same best-effort GitHub
scheduler. They do not guarantee publication at an exact minute:
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
