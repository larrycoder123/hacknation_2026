"""Tests for conversation API routes using FastAPI TestClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.conversations import Conversation
from app.schemas.messages import Message
from app.schemas.tickets import Ticket
from app.schemas.learning import SelfLearningResult

client = TestClient(app)


# ── Fixtures ─────────────────────────────────────────────────────────

MOCK_CONV = Conversation(
    id="1024",
    customer_name="Jane Doe",
    subject="Cannot access property certifications",
    priority="Medium",
    status="Open",
    time_ago="5m",
)

MOCK_MSG = Message(
    id="msg-1",
    conversation_id="1024",
    sender="customer",
    content="I can't access certifications.",
    timestamp="2026-01-01T10:00:00Z",
)


# ── GET /api/conversations ───────────────────────────────────────────


class TestGetConversations:
    def test_returns_list(self):
        resp = client.get("/api/conversations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ── GET /api/conversations/{id} ──────────────────────────────────────


class TestGetConversation:
    @patch("app.api.conversation_routes.MOCK_CONVERSATIONS", {"1024": MOCK_CONV})
    def test_found(self):
        resp = client.get("/api/conversations/1024")
        assert resp.status_code == 200
        assert resp.json()["id"] == "1024"

    @patch("app.api.conversation_routes.MOCK_CONVERSATIONS", {})
    def test_not_found(self):
        resp = client.get("/api/conversations/9999")
        assert resp.status_code == 404


# ── GET /api/conversations/{id}/messages ─────────────────────────────


class TestGetMessages:
    @patch("app.api.conversation_routes.MOCK_MESSAGES", {"1024": [MOCK_MSG]})
    @patch("app.api.conversation_routes.MOCK_CONVERSATIONS", {"1024": MOCK_CONV})
    def test_returns_messages(self):
        resp = client.get("/api/conversations/1024/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["sender"] == "customer"

    @patch("app.api.conversation_routes.MOCK_CONVERSATIONS", {})
    def test_not_found(self):
        resp = client.get("/api/conversations/9999/messages")
        assert resp.status_code == 404


# ── GET /api/conversations/{id}/suggested-actions ────────────────────


class TestGetSuggestedActions:
    @patch("app.api.conversation_routes.MOCK_CONVERSATIONS", {"1024": MOCK_CONV})
    @patch("app.api.conversation_routes.MOCK_MESSAGES", {"1024": [MOCK_MSG]})
    @patch("app.api.conversation_routes.MOCK_SUGGESTIONS", [])
    def test_returns_actions_from_rag(self):
        """When RAG succeeds, returns RAG-derived actions."""
        mock_result = MagicMock()
        mock_hit = MagicMock()
        mock_hit.source_type = "SCRIPT"
        mock_hit.source_id = "SCRIPT-001"
        mock_hit.rerank_score = 0.9
        mock_hit.similarity = 0.85
        mock_hit.title = "Date Script"
        mock_hit.content = "Short content"
        mock_result.top_hits = [mock_hit]

        with patch("app.rag.agent.graph.run_rag", return_value=mock_result):
            resp = client.get("/api/conversations/1024/suggested-actions")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["type"] == "script"

    @patch("app.api.conversation_routes.MOCK_CONVERSATIONS", {"1024": MOCK_CONV})
    @patch("app.api.conversation_routes.MOCK_MESSAGES", {"1024": [MOCK_MSG]})
    @patch("app.api.conversation_routes.MOCK_SUGGESTIONS", [{"id": "mock", "type": "action", "confidence_score": 0.5, "title": "Mock", "description": "d", "content": "c", "source": "s"}])
    def test_falls_back_on_rag_failure(self):
        """When RAG throws, falls back to mock suggestions."""
        with patch("app.rag.agent.graph.run_rag", side_effect=RuntimeError("fail")):
            resp = client.get("/api/conversations/1024/suggested-actions")
            assert resp.status_code == 200

    @patch("app.api.conversation_routes.MOCK_CONVERSATIONS", {})
    def test_not_found(self):
        resp = client.get("/api/conversations/9999/suggested-actions")
        assert resp.status_code == 404


# ── POST /api/conversations/{id}/close ───────────────────────────────


class TestCloseConversation:
    @patch("app.api.conversation_routes.MOCK_CONVERSATIONS", {"1024": MOCK_CONV})
    @patch("app.api.conversation_routes.MOCK_MESSAGES", {"1024": [MOCK_MSG]})
    def test_close_without_ticket(self):
        """Close with create_ticket=false, no ticket generation."""
        payload = {
            "conversation_id": "1024",
            "resolution_type": "Not Applicable",
            "create_ticket": False,
        }
        resp = client.post("/api/conversations/1024/close", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["ticket"] is None

    @patch("app.api.conversation_routes.MOCK_CONVERSATIONS", {"1024": MOCK_CONV})
    @patch("app.api.conversation_routes.MOCK_MESSAGES", {"1024": [MOCK_MSG]})
    @patch("app.services.ticket_service.generate_ticket", new_callable=AsyncMock)
    @patch("app.services.ticket_service.save_ticket_to_db")
    @patch("app.services.learning_service.run_post_conversation_learning", new_callable=AsyncMock)
    def test_close_with_ticket_and_learning(self, mock_learn, mock_save, mock_gen):
        ticket = Ticket(
            subject="Test", description="Desc", resolution="Fixed", tags=["t"]
        )
        mock_gen.return_value = ticket
        mock_save.return_value = "CS-AABBCCDD"
        mock_learn.return_value = SelfLearningResult(
            ticket_number="CS-AABBCCDD",
            retrieval_logs_processed=0,
            confidence_updates=[],
            gap_classification="SAME_KNOWLEDGE",
        )

        payload = {
            "conversation_id": "1024",
            "resolution_type": "Resolved Successfully",
            "create_ticket": True,
        }
        resp = client.post("/api/conversations/1024/close", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticket"]["ticket_number"] == "CS-AABBCCDD"
        assert data["learning_result"]["gap_classification"] == "SAME_KNOWLEDGE"

    @patch("app.api.conversation_routes.MOCK_CONVERSATIONS", {"1024": MOCK_CONV})
    @patch("app.api.conversation_routes.MOCK_MESSAGES", {"1024": [MOCK_MSG]})
    @patch("app.services.ticket_service.generate_ticket", new_callable=AsyncMock)
    def test_close_warns_on_save_failure(self, mock_gen):
        ticket = Ticket(
            subject="Test", description="Desc", resolution="Fixed", tags=["t"]
        )
        mock_gen.return_value = ticket

        with patch("app.services.ticket_service.save_ticket_to_db",
                   side_effect=RuntimeError("DB down")):
            payload = {
                "conversation_id": "1024",
                "resolution_type": "Resolved Successfully",
                "create_ticket": True,
            }
            resp = client.post("/api/conversations/1024/close", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["warnings"]) > 0
            assert "could not be saved" in data["warnings"][0]

    @patch("app.api.conversation_routes.MOCK_CONVERSATIONS", {})
    def test_close_not_found(self):
        payload = {
            "conversation_id": "9999",
            "resolution_type": "Not Applicable",
            "create_ticket": False,
        }
        resp = client.post("/api/conversations/9999/close", json=payload)
        assert resp.status_code == 404
