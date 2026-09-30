"""Reusable WHERE / ORDER fragments for the jobs table. Only constants and bound parameters."""

from __future__ import annotations

from dataclasses import dataclass

NOT_HIDDEN = "status!='ignored'"
TOP_MATCH = "stage='scored' AND verdict='apply' AND status=''"
GOOD_MATCH = "stage='scored' AND verdict IN ('apply','maybe')"

# key, label, WHERE
JOB_TABS = [
    ("best", "Top matches", f"stage='scored' AND verdict='apply' AND {NOT_HIDDEN}"),
    ("maybe", "Worth a look", f"stage='scored' AND verdict='maybe' AND {NOT_HIDDEN}"),
    ("rated", "All rated", f"stage='scored' AND verdict!='error' AND {NOT_HIDDEN}"),
    ("waiting", "Not rated yet", f"stage IN ('queued','batched') AND {NOT_HIDDEN}"),
    ("filtered", "Filtered out", "stage IN ('rejected','duplicate')"),
    ("hidden", "Hidden", "status='ignored'"),
]
TAB_WHERE = {key: where for key, _, where in JOB_TABS}
DEFAULT_TAB = "best"
LIST_LIMIT = 200


@dataclass
class JobListFilter:
    tab: str = DEFAULT_TAB
    search: str = ""
    work_type: str = ""
    source: str = ""
    sort: str = "best"

    def __post_init__(self):
        if self.tab not in TAB_WHERE:
            self.tab = DEFAULT_TAB

    def where(self) -> tuple[str, list]:
        clauses, params = [TAB_WHERE[self.tab]], []
        if self.work_type:
            clauses.append("work_type=?")
            params.append(self.work_type)
        if self.source:
            clauses.append("source=?")
            params.append(self.source)
        if self.search:
            clauses.append("(title LIKE ? OR company LIKE ? OR location LIKE ?)")
            params.extend([f"%{self.search}%"] * 3)
        return " AND ".join(clauses), params

    def order(self) -> str:
        if self.sort == "new":
            return "posted_at DESC"
        if self.tab in ("waiting", "filtered"):
            return "kw_score DESC, posted_at DESC"
        return "score DESC, posted_at DESC"
