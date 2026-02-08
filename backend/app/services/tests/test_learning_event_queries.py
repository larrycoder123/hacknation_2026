"""Tests for learning_event_queries.list_learning_events."""

from unittest.mock import MagicMock, patch

import pytest

from app.schemas.learning import LearningEventListResponse
from app.services.learning_event_queries import list_learning_events


# ── Helpers ──────────────────────────────────────────────────────────


def _chain_mock():
    m = MagicMock()
    for method in ("select", "eq", "is_", "in_", "order", "range",
                    "maybe_single", "single", "update", "insert", "delete"):
        getattr(m, method).return_value = m
    m.execute.return_value = MagicMock(data=[], count=0)
    return m


def _make_event_row(**overrides):
    defaults = {
        "event_id": "LE-aabbccddeeff",
        "trigger_ticket_number": "CS-TEST01",
        "detected_gap": "Missing KB for date advance",
        "event_type": "GAP",
        "proposed_kb_article_id": None,
        "flagged_kb_article_id": None,
        "draft_summary": "Draft about date advance",
        "final_status": None,
        "reviewer_role": None,
        "event_timestamp": "2026-01-01T00:00:00Z",
    }
    defaults.update(overrides)
    return defaults


def _make_kb_row(**overrides):
    defaults = {
        "kb_article_id": "KB-001",
        "title": "Date Advance Guide",
        "body": "Steps to advance date",
        "tags": "date",
        "module": "Property Management",
        "category": "Advance Property Date",
        "status": "Draft",
    }
    defaults.update(overrides)
    return defaults


# ── Tests ────────────────────────────────────────────────────────────


class TestListLearningEvents:
    @patch("app.services.learning_event_queries.get_supabase")
    def test_returns_empty_list(self, mock_get_sb):
        sb = MagicMock()
        le_chain = _chain_mock()
        le_chain.execute.return_value = MagicMock(data=[], count=0)
        sb.table.return_value = le_chain
        mock_get_sb.return_value = sb

        result = list_learning_events()
        assert isinstance(result, LearningEventListResponse)
        assert result.total_count == 0
        assert result.events == []

    @patch("app.services.learning_event_queries.get_supabase")
    def test_returns_events_with_kb_data(self, mock_get_sb):
        sb = MagicMock()
        tables = {}

        def _table(name):
            if name not in tables:
                tables[name] = _chain_mock()
            return tables[name]

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        event_row = _make_event_row(proposed_kb_article_id="KB-001")
        tables["learning_events"] = _chain_mock()
        tables["learning_events"].execute.return_value = MagicMock(
            data=[event_row], count=1
        )

        kb_row = _make_kb_row()
        tables["knowledge_articles"] = _chain_mock()
        tables["knowledge_articles"].execute.return_value = MagicMock(
            data=[kb_row]
        )

        tables["tickets"] = _chain_mock()
        tables["tickets"].execute.return_value = MagicMock(
            data=[{"ticket_number": "CS-TEST01", "subject": "Date issue",
                   "description": "Cannot advance", "resolution": "Used wizard"}]
        )

        result = list_learning_events()
        assert result.total_count == 1
        assert result.events[0].event_id == "LE-aabbccddeeff"
        assert result.events[0].proposed_article is not None
        assert result.events[0].proposed_article.kb_article_id == "KB-001"
        assert result.events[0].trigger_ticket_subject == "Date issue"

    @patch("app.services.learning_event_queries.get_supabase")
    def test_pending_filter_uses_is_null(self, mock_get_sb):
        sb = MagicMock()
        le_chain = _chain_mock()
        sb.table.return_value = le_chain
        mock_get_sb.return_value = sb

        list_learning_events(status="pending")
        le_chain.is_.assert_called_with("final_status", "null")

    @patch("app.services.learning_event_queries.get_supabase")
    def test_approved_filter(self, mock_get_sb):
        sb = MagicMock()
        le_chain = _chain_mock()
        sb.table.return_value = le_chain
        mock_get_sb.return_value = sb

        list_learning_events(status="approved")
        le_chain.eq.assert_any_call("final_status", "Approved")

    @patch("app.services.learning_event_queries.get_supabase")
    def test_rejected_filter(self, mock_get_sb):
        sb = MagicMock()
        le_chain = _chain_mock()
        sb.table.return_value = le_chain
        mock_get_sb.return_value = sb

        list_learning_events(status="rejected")
        le_chain.eq.assert_any_call("final_status", "Rejected")

    @patch("app.services.learning_event_queries.get_supabase")
    def test_event_type_filter(self, mock_get_sb):
        sb = MagicMock()
        le_chain = _chain_mock()
        sb.table.return_value = le_chain
        mock_get_sb.return_value = sb

        list_learning_events(event_type="CONTRADICTION")
        le_chain.eq.assert_any_call("event_type", "CONTRADICTION")

    @patch("app.services.learning_event_queries.get_supabase")
    def test_pagination(self, mock_get_sb):
        sb = MagicMock()
        le_chain = _chain_mock()
        sb.table.return_value = le_chain
        mock_get_sb.return_value = sb

        list_learning_events(limit=10, offset=20)
        le_chain.range.assert_called_with(20, 29)

    @patch("app.services.learning_event_queries.get_supabase")
    def test_no_kb_fetch_when_no_ids(self, mock_get_sb):
        sb = MagicMock()
        tables = {}

        def _table(name):
            if name not in tables:
                tables[name] = _chain_mock()
            return tables[name]

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        # Event with no KB references
        event_row = _make_event_row()
        tables["learning_events"] = _chain_mock()
        tables["learning_events"].execute.return_value = MagicMock(
            data=[event_row], count=1
        )

        # tickets table for trigger_ticket_number
        tables["tickets"] = _chain_mock()

        result = list_learning_events()
        assert result.total_count == 1
        # knowledge_articles table should not have been accessed
        assert "knowledge_articles" not in tables
