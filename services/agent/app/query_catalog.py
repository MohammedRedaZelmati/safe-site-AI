from dataclasses import dataclass
import re
from typing import Any


FORBIDDEN_WORDS = {
    "alter",
    "copy",
    "create",
    "delete",
    "drop",
    "grant",
    "insert",
    "revoke",
    "truncate",
    "update",
}


@dataclass(frozen=True)
class QueryPlan:
    intent: str
    sql: str
    parameters: list[Any]


TOTAL = "SELECT COUNT(*)::bigint AS total FROM violations"
BY_TYPE = """SELECT violation_type, COUNT(*)::bigint AS count
FROM violations
GROUP BY violation_type
ORDER BY count DESC, violation_type"""
BY_CAMERA = """SELECT camera_id, COUNT(*)::bigint AS count
FROM violations
GROUP BY camera_id
ORDER BY count DESC, camera_id"""
CAMERA_TOTAL = "SELECT COUNT(*)::bigint AS total FROM violations WHERE camera_id = %s"
TOP_TYPE = """SELECT violation_type, COUNT(*)::bigint AS count
FROM violations
GROUP BY violation_type
ORDER BY count DESC, violation_type
LIMIT 1"""
RECENT = """SELECT id, occurred_at, camera_id, track_id, violation_type, confidence, frame_uri
FROM violations
ORDER BY occurred_at DESC
LIMIT %s"""


APPROVED_SQL = {TOTAL, BY_TYPE, BY_CAMERA, CAMERA_TOTAL, TOP_TYPE, RECENT}


def normalize_question(question: str) -> str:
    return " ".join(question.strip().lower().split())


def contains_forbidden_request(question: str) -> bool:
    words = set(re.findall(r"[a-z_]+", normalize_question(question)))
    return bool(words & FORBIDDEN_WORDS)


def plan_question(question: str) -> QueryPlan | None:
    normalized = normalize_question(question)
    if contains_forbidden_request(normalized):
        return None
    if any(word in normalized for word in ("recent", "latest", "last")):
        match = re.search(r"\b(\d{1,3})\b", normalized)
        limit = min(50, max(1, int(match.group(1)))) if match else 10
        return QueryPlan("recent_violations", RECENT, [limit])
    if "most common" in normalized or "top violation" in normalized:
        return QueryPlan("top_violation_type", TOP_TYPE, [])
    if "by camera" in normalized or "each camera" in normalized or "per camera" in normalized:
        return QueryPlan("violations_by_camera", BY_CAMERA, [])
    if "by type" in normalized or "each type" in normalized or "per type" in normalized:
        return QueryPlan("violations_by_type", BY_TYPE, [])
    camera_match = re.search(r"\b(camera[-_][a-z0-9_-]+)\b", normalized)
    if camera_match and any(phrase in normalized for phrase in ("how many", "count", "total")):
        return QueryPlan("camera_total", CAMERA_TOTAL, [camera_match.group(1)])
    if any(phrase in normalized for phrase in ("how many violations", "total violations", "number of violations")):
        return QueryPlan("total_violations", TOTAL, [])
    if "summary" in normalized and "violation" in normalized:
        return QueryPlan("violations_by_type", BY_TYPE, [])
    return None


def validate_plan(plan: QueryPlan) -> None:
    normalized = " ".join(plan.sql.strip().split()).lower()
    if plan.sql not in APPROVED_SQL:
        raise ValueError("SQL is not in the approved query catalog")
    if not normalized.startswith("select "):
        raise ValueError("Only SELECT queries are allowed")
    if ";" in plan.sql:
        raise ValueError("Multiple SQL statements are not allowed")
    if any(re.search(rf"\b{word}\b", normalized) for word in FORBIDDEN_WORDS):
        raise ValueError("Write operations are forbidden")
    if not re.search(r"\bfrom\s+violations\b", normalized):
        raise ValueError("Only the violations table may be queried")
