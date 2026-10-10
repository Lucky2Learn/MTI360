"""Status transition tables (Phase 02-1; ADR-0020 §1, §4).

A business status machine is one explicit, immutable table of allowed moves,
declared in the owning module's ``domain.py`` and unit-tested pair by pair::

    COURSE_TRANSITIONS = TransitionTable(
        {CourseStatus.DRAFT: {CourseStatus.ACTIVE, CourseStatus.ARCHIVED}, ...}
    )

Services ask :meth:`TransitionTable.allows` before changing a status; the API
lists :meth:`TransitionTable.targets` for the UI (a hint only: the server
decides). Same-status moves are never allowed.
"""

from collections.abc import Iterable, Mapping
from types import MappingProxyType


class TransitionTable[S]:
    def __init__(self, moves: Mapping[S, Iterable[S]]) -> None:
        self._moves: Mapping[S, frozenset[S]] = MappingProxyType(
            {
                source: frozenset(t for t in targets if t != source)
                for source, targets in moves.items()
            }
        )

    def allows(self, source: S, target: S) -> bool:
        return target in self._moves.get(source, frozenset())

    def targets(self, source: S) -> frozenset[S]:
        return self._moves.get(source, frozenset())
