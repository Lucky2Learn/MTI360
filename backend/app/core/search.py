"""Text search helpers shared by list queries (T01-08; moved to core in Phase 02-1)."""


def escape_like(value: str) -> str:
    r"""``value`` as a literal inside an ``ILIKE`` pattern (escape character ``\``)."""
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
