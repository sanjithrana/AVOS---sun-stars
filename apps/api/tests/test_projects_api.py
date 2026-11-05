import pytest
from fastapi.testclient import TestClient

from src.main import app
from tests.conftest import requires_db


client = TestClient(app)


@requires_db
def test_create_project():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Flower Adventure",
            "topic": "Flowers",
            "duration": 45,
            "aspect_ratio": "9:16",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Flower Adventure"
    assert data["topic"] == "Flowers"
    assert data["duration_seconds"] == 45
    assert data["aspect_ratio"] == "9:16"
    assert data["status"] == "planning"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_project_validation():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Flower Adventure",
            "topic": "Flowers",
            "duration": 0,
            "aspect_ratio": "9:16",
        },
    )

    assert response.status_code == 422

    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
        }
    }


def test_create_project_rejects_unknown_fields():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Flower Adventure",
            "topic": "Flowers",
            "duration": 45,
            "aspect_ratio": "9:16",
            "unknown_field": "not allowed",
        },
    )

    assert response.status_code == 422

    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
        }
    }


def test_create_project_rejects_missing_required_field():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Flower Adventure",
            "topic": "Flowers",
            "aspect_ratio": "9:16",
        },
    )

    assert response.status_code == 422

    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
        }
    }


def test_create_project_rejects_invalid_duration_type():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Flower Adventure",
            "topic": "Flowers",
            "duration": "not-a-number",
            "aspect_ratio": "9:16",
        },
    )

    assert response.status_code == 422

    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
        }
    }


def test_create_project_rejects_empty_name():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "",
            "topic": "Flowers",
            "duration": 45,
            "aspect_ratio": "9:16",
        },
    )

    assert response.status_code == 422

    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
        }
    }


def test_create_project_rejects_negative_duration():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Flower Adventure",
            "topic": "Flowers",
            "duration": -10,
            "aspect_ratio": "9:16",
        },
    )

    assert response.status_code == 422

    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
        }
    }


@requires_db
def test_get_project():
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Flower Adventure",
            "topic": "Flowers",
            "duration": 45,
            "aspect_ratio": "9:16",
        },
    )

    assert create_response.status_code == 201

    project_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/projects/{project_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == project_id
    assert data["name"] == "Flower Adventure"
    assert data["topic"] == "Flowers"
    assert data["duration_seconds"] == 45
    assert data["aspect_ratio"] == "9:16"


@requires_db
def test_get_project_not_found():
    project_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(
        f"/api/v1/projects/{project_id}"
    )

    assert response.status_code == 404

    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Project not found.",
            "project_id": project_id,
        }
    }


def test_validation_error_uses_avos_error_envelope():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Flower Adventure",
            "topic": "Flowers",
            "duration": 0,
            "aspect_ratio": "9:16",
        },
    )

    assert response.status_code == 422

    data = response.json()

    assert data == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
        }
    }


@requires_db
def test_not_found_uses_avos_error_envelope():
    project_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(
        f"/api/v1/projects/{project_id}"
    )

    assert response.status_code == 404

    data = response.json()

    assert data == {
        "error": {
            "code": "not_found",
            "message": "Project not found.",
            "project_id": project_id,
        }
    }


@requires_db
def test_list_projects_returns_created_projects_newest_first():
    first = client.post(
        "/api/v1/projects",
        json={"name": "First", "topic": "Bees", "duration": 30, "aspect_ratio": "9:16"},
    ).json()
    second = client.post(
        "/api/v1/projects",
        json={"name": "Second", "topic": "Rain", "duration": 20, "aspect_ratio": "16:9"},
    ).json()

    response = client.get("/api/v1/projects")

    assert response.status_code == 200
    ids = [p["id"] for p in response.json()]
    assert ids.index(second["id"]) < ids.index(first["id"])


@requires_db
def test_create_project_accepts_optional_budget_limit():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Budgeted",
            "topic": "Clouds",
            "duration": 30,
            "aspect_ratio": "9:16",
            "budget_limit": 2.5,
        },
    )

    assert response.status_code == 201
    assert response.json()["budget_limit"] == 2.5
    assert response.json()["created_at"].endswith("Z") or "+00:00" in response.json()["created_at"]


def test_frontend_payload_shape_is_what_backend_accepts():
    """Guards the contract the New Project form sends. The old form sent
    description/target_duration/status/progress/... and got a 422."""
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "x",
            "description": "AI production about x",
            "target_duration": 30,
            "aspect_ratio": "9:16",
        },
    )
    assert response.status_code == 422
