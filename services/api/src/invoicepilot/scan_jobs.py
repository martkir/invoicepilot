"""In-flight scan jobs.

A scan takes long enough that a request cannot wait for it — attachment
downloads, invoice2data over every candidate, and optionally a fetch out to the
vendor for each linked PDF. So POST /scan starts one of these and returns an
id, and the client polls.

State lives in memory rather than Postgres because it is worth nothing once the
process ends: an interrupted scan is not resumable, and the invoices it did
file are already committed. One consequence worth knowing in development —
`run_api.sh` runs uvicorn with --reload, so saving a file mid-scan restarts the
process and the job disappears with it.

Every job belongs to a workspace. Scanning is self-serve on a public URL, so
"one scan at a time" is now one per workspace rather than one per process — one
visitor's scan must not lock out everybody else's. What stays global is the
worker count, because the threads and the Unipile quota they spend are shared.
"""

import threading
import uuid
from dataclasses import dataclass, replace

from invoicepilot.core.logging import get_logger
from invoicepilot.process import Progress, ScanResult, scan_all

log = get_logger(__name__)

# Jobs are never evicted. A scan record is a few hundred bytes and the process
# is restarted often enough that this cannot grow unbounded in practice.
_JOBS: dict[str, "Job"] = {}
_LOCK = threading.Lock()

# How many scans may run at once across every workspace. A scan is minutes of
# attachment downloads and PDF parsing, so without a ceiling a handful of
# visitors starting one together is enough to exhaust the threadpool the rest
# of the API answers from. Queued rather than refused: the job is already
# accepted at this point and the client is polling it.
MAX_CONCURRENT_SCANS = 3
_WORKERS = threading.Semaphore(MAX_CONCURRENT_SCANS)


@dataclass(frozen=True)
class Job:
    id: str
    workspace_id: str
    status: str = "running"
    result: ScanResult | None = None
    detail: str | None = None
    # The last report from the running scan, and None once there is a result.
    progress: Progress | None = None

    @property
    def counts(self) -> ScanResult:
        """How far the scan has got, whether or not it has finished.

        A poller wants the same two numbers throughout, so a running job
        answers from its last progress report rather than with the zeros a
        missing result would give. The fields a scan only knows at the end —
        mailboxes, errors, invoices_new — keep their empty defaults until then,
        which is what makes one shape serve both states.
        """
        if self.result:
            return self.result
        if self.progress is None:
            return ScanResult()
        return ScanResult(
            messages_scanned=self.progress.messages_scanned,
            invoices_found=self.progress.invoices_found,
        )


class ScanInProgress(RuntimeError):
    """Raised by start() when this workspace already has a scan running.

    Two scans of the same mailbox would download the same attachments twice and
    write the same invoice folders from two threads, so a workspace runs one at
    a time. Two *different* workspaces are no such conflict — separate
    mailboxes, separate rows, separate folders — and are allowed to overlap.
    """

    def __init__(self, job: Job) -> None:
        super().__init__(f"A scan is already running ({job.id}).")
        self.job = job


def _put(job: Job) -> None:
    with _LOCK:
        _JOBS[job.id] = job


def _peek(job_id: str) -> Job | None:
    """The job as it stands, with no ownership check — for the scan's own thread."""
    with _LOCK:
        return _JOBS.get(job_id)


def get(job_id: str, workspace_id: str) -> Job | None:
    """One workspace's job. Another workspace's id reads as missing.

    A job id is a uuid4 and so not realistically guessable, but the check costs
    a comparison and means a leaked id discloses nothing — the scan's counts
    say how much mail a stranger has and how much of it is invoices.
    """
    with _LOCK:
        job = _JOBS.get(job_id)
    return job if job and job.workspace_id == workspace_id else None


def start(workspace_id: str, allowed: list[str], *, follow_links: bool) -> Job:
    """Kick off a scan in the background and return its handle immediately.

    Raises ScanInProgress if this workspace already has one running.
    """
    job = Job(id=uuid.uuid4().hex, workspace_id=workspace_id)
    # Claimed under the lock rather than checked and then claimed, so two
    # requests arriving together cannot both find the workspace clear.
    with _LOCK:
        current = next(
            (j for j in _JOBS.values() if j.status == "running" and j.workspace_id == workspace_id),
            None,
        )
        if current is not None:
            raise ScanInProgress(current)
        _JOBS[job.id] = job

    def run() -> None:
        def on_progress(progress: Progress) -> None:
            current = _peek(job.id)
            if current:
                _put(replace(current, progress=progress))

        # Waits its turn when the box is already busy scanning. The job exists
        # and reports "running" throughout, which is what the client polls.
        with _WORKERS:
            try:
                result = scan_all(
                    workspace_id, allowed, follow_links=follow_links, on_progress=on_progress
                )
            except Exception as exc:  # noqa: BLE001 — the failure belongs in the job, not a traceback
                log.warning("scan %s failed: %s", job.id, exc)
                _put(replace(job, status="error", detail=str(exc)))
                return
        _put(replace(job, status="done", result=result))

    threading.Thread(target=run, name=f"scan-{job.id[:8]}", daemon=True).start()
    return job
