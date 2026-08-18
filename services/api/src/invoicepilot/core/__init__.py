"""Cross-cutting plumbing: settings, database, logging.

Nothing in this package may import from the domain modules (gmail, drive,
process, ...). It is a leaf — the domain imports core, never the reverse.
"""
