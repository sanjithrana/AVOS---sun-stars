from fastapi.testclient import TestClient

from src.main import app
from tests.conftest import requires_db

pytestmark = requires_db


client = TestClient(app)


def test_create_project_then_get_project():
    # POST /api/v1/projects
    create_response = client.post(
        "/api/v1/projects",
        json={
            "name": "Integration Test Project",
            "topic": "Flowers",
            "duration": 45,
            "aspect_ratio": "9:16",
        },
    )

    # POST must create the project.
    assert create_response.status_code == 201

    created = create_response.json()

    project_id = created["id"]

    assert project_id
    assert created["name"] == "Integration Test Project"
    assert created["topic"] == "Flowers"
    assert created["duration_seconds"] == 45
    assert created["aspect_ratio"] == "9:16"
    assert created["status"] == "planning"

    # GET /api/v1/projects/{project_id}
    get_response = client.get(
        f"/api/v1/projects/{project_id}"
    )

    # GET must return the persisted project.
    assert get_response.status_code == 200

    fetched = get_response.json()

    # The same project must come back from the database.
    assert fetched["id"] == project_id
    assert fetched["name"] == created["name"]
    assert fetched["topic"] == created["topic"]
    assert fetched["duration_seconds"] == created["duration_seconds"]
    assert fetched["aspect_ratio"] == created["aspect_ratio"]
    assert fetched["status"] == created["status"]
    assert fetched["budget_limit"] == created["budget_limit"]
    assert fetched["budget_spent"] == created["budget_spent"]
    assert fetched["created_at"] == created["created_at"]
    assert fetched["updated_at"] == created["updated_at"]


def test_create_project_malformed_input_returns_validation_error():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Integration Test Project",
            "topic": "Flowers",
            "duration": 0,
            "aspect_ratio": "9:16",
        },
    )

    # Validation must be a client error, never an internal server error.
    assert response.status_code == 422
    assert response.status_code != 500

    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
        }
    }


def test_create_project_unknown_field_returns_validation_error():
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Integration Test Project",
            "topic": "Flowers",
            "duration": 45,
            "aspect_ratio": "9:16",
            "unknown_field": "must be rejected",
        },
    )

    assert response.status_code == 422
    assert response.status_code != 500

    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
        }
    }
