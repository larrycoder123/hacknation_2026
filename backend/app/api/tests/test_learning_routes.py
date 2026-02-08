"""Tests for learning API routes using FastAPI TestClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.schemas.learning import (
    LearningEventDetail,
    LearningEventListResponse,
    LearningEventRecord,
    SelfLearningResult,
)

client = TestClient(app)


# ── GET /api/learning-events ─────────────────────────────────────────


class TestGetLearningEvents:
    @patch("app.api.learning_routes.list_learning_events")
    def test_returns_events(self, mock_list):
        mock_list.return_value = LearningEventListResponse(
            events=[], total_count=0
        )
        resp = client.get("/api/learning-events")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 0

    @patch("app.api.learning_routes.list_learning_events")
    def test_passes_filters(self, mock_list):
        mock_list.return_value = LearningEventListResponse(
            events=[], total_count=0
        )
        resp = client.get(
            "/api/learning-events?status=pending&event_type=GAP&limit=10&offset=5"
        )
        assert resp.status_code == 200
        mock_list.assert_called_once_with(
            status="pending", event_type="GAP", limit=10, offset=5
        )

    @patch("app.api.learning_routes.list_learning_events")
    def test_db_error_returns_502(self, mock_list):
        mock_list.side_effect = APIError(
            {"message": "connection error", "code": "PGRST301", "details": None, "hint": None}
        )
        resp = client.get("/api/learning-events")
        assert resp.status_code == 502

    @patch("app.api.learning_routes.list_learning_events")
    def test_unexpected_error_returns_500(self, mock_list):
        mock_list.side_effect = RuntimeError("boom")
        resp = client.get("/api/learning-events")
        assert resp.status_code == 500


# ── POST /api/tickets/{ticket_number}/learn ──────────────────────────


class TestPostConversationLearn:
    @patch("app.api.learning_routes.learning_service.run_post_conversation_learning",
           new_callable=AsyncMock)
    def test_success(self, mock_learn):
        mock_learn.return_value = SelfLearningResult(
            ticket_number="CS-TEST01",
            retrieval_logs_processed=3,
            confidence_updates=[],
            gap_classification="SAME_KNOWLEDGE",
        )
        resp = client.post("/api/tickets/CS-TEST01/learn")
        assert resp.status_code == 200
        assert resp.json()["ticket_number"] == "CS-TEST01"

    @patch("app.api.learning_routes.learning_service.run_post_conversation_learning",
           new_callable=AsyncMock)
    def test_not_found(self, mock_learn):
        mock_learn.side_effect = APIError(
            {"message": "0 rows", "code": "PGRST116", "details": None, "hint": None}
        )
        resp = client.post("/api/tickets/CS-NONE01/learn")
        assert resp.status_code == 404

    @patch("app.api.learning_routes.learning_service.run_post_conversation_learning",
           new_callable=AsyncMock)
    def test_db_error(self, mock_learn):
        mock_learn.side_effect = APIError(
            {"message": "connection error", "code": "PGRST301", "details": None, "hint": None}
        )
        resp = client.post("/api/tickets/CS-TEST01/learn")
        assert resp.status_code == 502

    @patch("app.api.learning_routes.learning_service.run_post_conversation_learning",
           new_callable=AsyncMock)
    def test_unexpected_error(self, mock_learn):
        mock_learn.side_effect = RuntimeError("boom")
        resp = client.post("/api/tickets/CS-TEST01/learn")
        assert resp.status_code == 500


# ── POST /api/learning-events/{event_id}/review ─────────────────────


class TestReviewLearningEvent:
    @patch("app.api.learning_routes.learning_service.review_learning_event",
           new_callable=AsyncMock)
    def test_approve(self, mock_review):
        mock_review.return_value = LearningEventRecord(
            event_id="LE-aabbccddeeff",
            trigger_ticket_number="CS-TEST01",
            detected_gap="Missing KB",
            event_type="GAP",
            draft_summary="Draft",
            final_status="Approved",
            reviewer_role="Tier 3 Support",
        )
        payload = {"decision": "Approved", "reviewer_role": "Tier 3 Support"}
        resp = client.post("/api/learning-events/LE-aabbccddeeff/review", json=payload)
        assert resp.status_code == 200
        assert resp.json()["final_status"] == "Approved"

    @patch("app.api.learning_routes.learning_service.review_learning_event",
           new_callable=AsyncMock)
    def test_reject(self, mock_review):
        mock_review.return_value = LearningEventRecord(
            event_id="LE-aabbccddeeff",
            trigger_ticket_number="CS-TEST01",
            detected_gap="Missing KB",
            event_type="GAP",
            draft_summary="Draft",
            final_status="Rejected",
            reviewer_role="Tier 3 Support",
        )
        payload = {"decision": "Rejected", "reviewer_role": "Tier 3 Support"}
        resp = client.post("/api/learning-events/LE-aabbccddeeff/review", json=payload)
        assert resp.status_code == 200
        assert resp.json()["final_status"] == "Rejected"

    def test_invalid_event_id_format(self):
        payload = {"decision": "Approved", "reviewer_role": "Tier 3 Support"}
        resp = client.post("/api/learning-events/bad-id/review", json=payload)
        assert resp.status_code == 422

    @patch("app.api.learning_routes.learning_service.review_learning_event",
           new_callable=AsyncMock)
    def test_not_found(self, mock_review):
        mock_review.side_effect = APIError(
            {"message": "0 rows", "code": "PGRST116", "details": None, "hint": None}
        )
        payload = {"decision": "Approved", "reviewer_role": "Tier 3 Support"}
        resp = client.post("/api/learning-events/LE-aabbccddeeff/review", json=payload)
        assert resp.status_code == 404

    @patch("app.api.learning_routes.learning_service.review_learning_event",
           new_callable=AsyncMock)
    def test_db_error(self, mock_review):
        mock_review.side_effect = APIError(
            {"message": "connection error", "code": "PGRST301", "details": None, "hint": None}
        )
        payload = {"decision": "Approved", "reviewer_role": "Tier 3 Support"}
        resp = client.post("/api/learning-events/LE-aabbccddeeff/review", json=payload)
        assert resp.status_code == 502

    @patch("app.api.learning_routes.learning_service.review_learning_event",
           new_callable=AsyncMock)
    def test_unexpected_error(self, mock_review):
        """Non-APIError exceptions return 500."""
        mock_review.side_effect = RuntimeError("something unexpected")
        payload = {"decision": "Approved", "reviewer_role": "Tier 3 Support"}
        resp = client.post("/api/learning-events/LE-aabbccddeeff/review", json=payload)
        assert resp.status_code == 500
