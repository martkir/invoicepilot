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


@dataclass(frozen=True)
class Job:
    id: str
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
    """Raised by start() when a scan is already running.

    Two scans would download the same attachments twice and write the same
    invoice folders from two threads, so only one runs at a time.
    """

    def __init__(self, job: Job) -> None:
        super().__init__(f"A scan is already running ({job.id}).")
        self.job = job


def _put(job: Job) -> None:
    with _LOCK:
        _JOBS[job.id] = job


def get(job_id: str) -> Job | None:
    with _LOCK:
        return _JOBS.get(job_id)


def start(*, limit: int, follow_links: bool) -> Job:
    """Kick off a scan in the background and return its handle immediately.

    Raises ScanInProgress if one is already running.
    """
    job = Job(id=uuid.uuid4().hex)
    # Claimed under the lock rather than checked and then claimed, so two
    # requests arriving together cannot both find the field clear.
    with _LOCK:
        current = next((j for j in _JOBS.values() if j.status == "running"), None)
        if current is not None:
            raise ScanInProgress(current)
        _JOBS[job.id] = job

    def run() -> None:
        def on_progress(progress: Progress) -> None:
            current = get(job.id)
            if current:
                _put(replace(current, progress=progress))

        try:
            result = scan_all(limit=limit, follow_links=follow_links, on_progress=on_progress)
        except Exception as exc:  # noqa: BLE001 — the failure belongs in the job, not a traceback
            log.warning("scan %s failed: %s", job.id, exc)
            _put(replace(job, status="error", detail=str(exc)))
            return
        _put(replace(job, status="done", result=result))

    threading.Thread(target=run, name=f"scan-{job.id[:8]}", daemon=True).start()
    return job
