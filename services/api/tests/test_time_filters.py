import os
from collections.abc import Iterator
from uuid import uuid4

import httpx
import psycopg
import pytest


API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://safesite:safesite_dev_password@postgres:5432/safesite",
)


@pytest.fixture
def camera_id() -> Iterator[str]:
    test_camera_id = f"test-camera-{uuid4().hex}"
    yield test_camera_id
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            "DELETE FROM violations WHERE camera_id = %s",
            (test_camera_id,),
        )


def create_violation(camera_id: str, occurred_at: str, track_id: int) -> None:
    response = httpx.post(
        f"{API_BASE_URL}/violations",
        json={
            "occurred_at": occurred_at,
            "camera_id": camera_id,
            "track_id": track_id,
            "violation_type": "NO_HELMET",
            "confidence": 0.9,
            "frame_uri": f"silver/{camera_id}/{track_id}.jpg",
        },
        timeout=10,
    )
    assert response.status_code == 201


def test_filters_violations_by_time_range(camera_id: str) -> None:
    create_violation(camera_id, "2026-08-05T10:00:00Z", 1)
    create_violation(camera_id, "2026-08-05T12:00:00Z", 2)

    response = httpx.get(
        f"{API_BASE_URL}/violations",
        params={
            "camera_id": camera_id,
            "occurred_from": "2026-08-05T11:00:00Z",
            "occurred_to": "2026-08-05T13:00:00Z",
        },
        timeout=10,
    )

    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["track_id"] == 2


def test_rejects_reversed_time_range() -> None:
    response = httpx.get(
        f"{API_BASE_URL}/violations",
        params={
            "occurred_from": "2026-08-05T13:00:00Z",
            "occurred_to": "2026-08-05T11:00:00Z",
        },
        timeout=10,
    )

    assert response.status_code == 422
    assert "occurred_from" in response.json()["detail"]


def test_camera_filter_treats_sql_as_plain_text() -> None:
    response = httpx.get(
        f"{API_BASE_URL}/violations",
        params={"camera_id": "camera-01' OR '1'='1"},
        timeout=10,
    )

    assert response.status_code == 200
    assert response.json() == []

