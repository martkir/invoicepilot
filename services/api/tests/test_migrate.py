"""Moving the documents when the layout gained a workspace level.

The schema half of the migration is exercised against a real database in CI;
this half is pure filesystem and needs nothing, so it is tested on its own.
"""

import json
from pathlib import Path

from invoicepilot.migrate import relocate_documents


def a_tree(root: Path, mailbox: str, invoice: str) -> Path:
    """One filed invoice in the old flat layout: <root>/<mailbox>/<invoice>/."""
    folder = root / mailbox / invoice
    folder.mkdir(parents=True)
    (folder / "invoice.json").write_text(json.dumps({"invoice": {}}), encoding="utf-8")
    (folder / "invoice.pdf").write_bytes(b"%PDF-1.4 fake")
    return folder


def test_mailbox_folders_move_under_the_workspace(tmp_path: Path) -> None:
    a_tree(tmp_path, "me@example.com", "2026-08-03__acme__12eur__aaaaaa")
    a_tree(tmp_path, "other@example.com", "2026-07-01__bolt__3eur__bbbbbb")

    assert relocate_documents("ws-1", tmp_path) == 2

    moved = tmp_path / "ws-1"
    assert (moved / "me@example.com" / "2026-08-03__acme__12eur__aaaaaa" / "invoice.pdf").is_file()
    assert (
        moved / "other@example.com" / "2026-07-01__bolt__3eur__bbbbbb" / "invoice.json"
    ).is_file()
    # and nothing is left at the old depth
    assert not (tmp_path / "me@example.com").exists()


def test_a_second_run_moves_nothing(tmp_path: Path) -> None:
    """Idempotent, because the migration reruns on every container start."""
    a_tree(tmp_path, "me@example.com", "2026-08-03__acme__12eur__aaaaaa")

    assert relocate_documents("ws-1", tmp_path) == 1
    assert relocate_documents("ws-1", tmp_path) == 0
    assert (tmp_path / "ws-1" / "me@example.com").is_dir()
    # The workspace directory must not end up nested inside itself.
    assert not (tmp_path / "ws-1" / "ws-1").exists()


def test_directories_that_are_not_mailboxes_are_left_alone(tmp_path: Path) -> None:
    """Only folders holding invoice folders move; anything else is not ours."""
    a_tree(tmp_path, "me@example.com", "2026-08-03__acme__12eur__aaaaaa")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "scratch.txt").write_text("keep me", encoding="utf-8")

    assert relocate_documents("ws-1", tmp_path) == 1
    assert (tmp_path / "notes" / "scratch.txt").read_text(encoding="utf-8") == "keep me"


def test_an_absent_data_directory_is_not_an_error(tmp_path: Path) -> None:
    """A deployment that has never scanned has nothing on disk to move."""
    assert relocate_documents("ws-1", tmp_path / "nothing-here") == 0
