"""tests/test_api.py — REFERENCE for Week 3 Lab Step 2 sub-step 2b (API tests).

Uses FastAPI's TestClient. No mocking needed for these — they test the
validation surface, not the LLM. The underlying W2 pipeline runs in
`use_fake=True` mode (the default) so any actual /ask call would use canned
fake answers — but these tests never reach an LLM call.

Run with:
    pytest tests/test_api.py -v
"""
from fastapi.testclient import TestClient
from api.main import app


client = TestClient(app)


def test_ask_rejects_missing_question():
    """POST /ask with empty body -> 422 Unprocessable Entity."""
    response = client.post("/ask", json={})
    assert response.status_code == 422
    body = response.json()
    detail_text = str(body.get("detail", ""))
    assert "question" in detail_text.lower()


def test_health_returns_ok():
    """GET /health -> 200 OK with the expected body."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
