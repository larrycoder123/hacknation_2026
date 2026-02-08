"""Tests for ticket_service: format_conversation, generate_ticket, save_ticket_to_db."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from postgrest.exceptions import APIError

from app.schemas.messages import Message
from app.schemas.tickets import Ticket
from app.services.ticket_service import (
    _format_conversation,
    _generate_ticket_number,
    save_ticket_to_db,
    generate_ticket,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_messages():
    return [
        Message(id="m1", conversation_id="c1", sender="customer",
                content="I can't advance the date.", timestamp="2026-01-01T10:00:00Z"),
        Message(id="m2", conversation_id="c1", sender="agent",
                content="Let me help.", timestamp="2026-01-01T10:01:00Z"),
    ]


def _make_ticket(**overrides):
    defaults = dict(
        subject="Cannot advance date",
        description="Tenant cannot advance property date",
        resolution="Used the date advance wizard",
        tags=["date", "property"],
    )
    defaults.update(overrides)
    return Ticket(**defaults)


def _chain_mock():
    m = MagicMock()
    for method in ("select", "eq", "is_", "in_", "order", "maybe_single",
                    "single", "update", "insert", "upsert", "delete"):
        getattr(m, method).return_value = m
    m.execute.return_value = MagicMock(data=[])
    return m


# ── _format_conversation ─────────────────────────────────────────────


class TestFormatConversation:
    def test_basic(self):
        messages = _make_messages()
        result = _format_conversation(messages)
        assert "CUSTOMER" in result
        assert "SUPPORT AGENT" in result
        assert "I can't advance the date." in result

    def test_with_resolution_notes(self):
        messages = _make_messages()
        result = _format_conversation(messages, resolution_notes="Fixed it.")
        assert "AGENT RESOLUTION NOTES" in result
        assert "Fixed it." in result

    def test_empty_messages(self):
        result = _format_conversation([])
        assert "CONVERSATION:" in result

    def test_system_sender(self):
        messages = [
            Message(id="m1", conversation_id="c1", sender="system",
                    content="Ticket created.", timestamp="2026-01-01T10:00:00Z"),
        ]
        result = _format_conversation(messages)
        assert "SYSTEM" in result


# ── _generate_ticket_number ──────────────────────────────────────────


class TestGenerateTicketNumber:
    def test_format(self):
        tn = _generate_ticket_number()
        assert tn.startswith("CS-")
        assert len(tn) == 11  # CS- + 8 hex chars

    def test_uniqueness(self):
        numbers = {_generate_ticket_number() for _ in range(100)}
        assert len(numbers) == 100


# ── generate_ticket (async LLM call) ────────────────────────────────


class TestGenerateTicket:
    @pytest.mark.asyncio
    async def test_calls_llm_and_returns_ticket(self):
        ticket = _make_ticket()
        with patch("app.services.ticket_service.generate_structured_output",
                   new_callable=AsyncMock, return_value=ticket) as mock_llm:
            result = await generate_ticket(
                conversation_id="c1",
                conversation_subject="Date issue",
                messages=_make_messages(),
            )
            assert result.subject == "Cannot advance date"
            mock_llm.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_merges_custom_tags(self):
        ticket = _make_ticket(tags=["date"])
        with patch("app.services.ticket_service.generate_structured_output",
                   new_callable=AsyncMock, return_value=ticket):
            result = await generate_ticket(
                conversation_id="c1",
                conversation_subject="Date issue",
                messages=_make_messages(),
                custom_tags=["urgent", "date"],
            )
            assert "urgent" in result.tags
            assert "date" in result.tags


# ── save_ticket_to_db ────────────────────────────────────────────────


class TestSaveTicketToDb:
    @patch("app.services.ticket_service.get_supabase")
    def test_happy_path(self, mock_get_sb):
        sb = MagicMock()
        tables = {}

        def _table(name):
            if name not in tables:
                tables[name] = _chain_mock()
            return tables[name]

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        ticket = _make_ticket()
        tn = save_ticket_to_db(ticket, "conv-1", "Medium")

        assert tn.startswith("CS-")
        # tickets insert was called
        tables["tickets"].insert.assert_called_once()

    @patch("app.services.ticket_service.get_supabase")
    def test_retries_on_ticket_collision(self, mock_get_sb):
        sb = MagicMock()
        tables = {}

        def _table(name):
            if name not in tables:
                tables[name] = _chain_mock()
            return tables[name]

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        # First tickets insert fails with 23505, second succeeds
        ticket_chain = _chain_mock()
        error = APIError({"message": "duplicate key", "code": "23505", "details": None, "hint": None})
        ticket_chain.insert.return_value = ticket_chain
        ticket_chain.execute.side_effect = [error, MagicMock(data=[])]
        tables["tickets"] = ticket_chain

        ticket = _make_ticket()
        tn = save_ticket_to_db(ticket, "conv-1", "Medium")
        assert tn.startswith("CS-")
        assert ticket_chain.execute.call_count == 2

    @patch("app.services.ticket_service.get_supabase")
    def test_raises_after_max_retries(self, mock_get_sb):
        sb = MagicMock()
        tables = {}

        def _table(name):
            if name not in tables:
                tables[name] = _chain_mock()
            return tables[name]

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        ticket_chain = _chain_mock()
        error = APIError({"message": "duplicate key", "code": "23505", "details": None, "hint": None})
        ticket_chain.insert.return_value = ticket_chain
        ticket_chain.execute.side_effect = error
        tables["tickets"] = ticket_chain

        ticket = _make_ticket()
        with pytest.raises(APIError):
            save_ticket_to_db(ticket, "conv-1", "Medium")

    @patch("app.services.ticket_service.get_supabase")
    def test_raises_non_duplicate_error_immediately(self, mock_get_sb):
        sb = MagicMock()
        tables = {}

        def _table(name):
            if name not in tables:
                tables[name] = _chain_mock()
            return tables[name]

        sb.table.side_effect = _table
        mock_get_sb.return_value = sb

        ticket_chain = _chain_mock()
        non_dup_error = APIError({"message": "connection error", "code": "PGRST301", "details": None, "hint": None})
        ticket_chain.insert.return_value = ticket_chain
        ticket_chain.execute.side_effect = non_dup_error
        tables["tickets"] = ticket_chain

        ticket = _make_ticket()
        with pytest.raises(APIError, match="connection error"):
            save_ticket_to_db(ticket, "conv-1", "Medium")