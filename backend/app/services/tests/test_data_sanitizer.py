"""Tests for Presidio-based data sanitization utilities."""

from unittest.mock import patch, MagicMock

import pytest
from app.services.data_sanitizer import (
    sanitize_text,
    sanitize_messages,
    sanitize_resolution_notes,
    get_detected_entities,
)
from app.schemas.messages import Message


class TestSanitizeText:
    """Test cases for text sanitization using Presidio."""

    def test_sanitize_email(self):
        """Email addresses should be redacted."""
        text = "Contact me at john.doe@example.com for more info."
        result = sanitize_text(text)
        assert "[EMAIL_REDACTED]" in result
        assert "john.doe@example.com" not in result

    def test_sanitize_multiple_emails(self):
        """Multiple email addresses should all be redacted."""
        text = "Email john@test.com or jane@domain.org"
        result = sanitize_text(text)
        assert result.count("[EMAIL_REDACTED]") == 2
        assert "john@test.com" not in result
        assert "jane@domain.org" not in result

    def test_sanitize_phone_us_standard(self):
        """US phone numbers should be redacted."""
        text = "Call me at 555-123-4567"
        result = sanitize_text(text)
        assert "[PHONE_REDACTED]" in result
        assert "555-123-4567" not in result

    def test_sanitize_phone_parentheses(self):
        """Phone numbers with parentheses should be redacted."""
        text = "My number is (555) 123-4567"
        result = sanitize_text(text)
        assert "[PHONE_REDACTED]" in result
        assert "(555) 123-4567" not in result

    def test_sanitize_credit_card(self):
        """Credit card numbers should be redacted."""
        text = "Card number: 4111-1111-1111-1111"
        result = sanitize_text(text)
        assert "[CARD_REDACTED]" in result
        assert "4111" not in result

    def test_sanitize_credit_card_spaces(self):
        """Credit card numbers with spaces should be redacted."""
        text = "Pay with 4111 1111 1111 1111"
        result = sanitize_text(text)
        assert "[CARD_REDACTED]" in result

    def test_sanitize_ssn(self):
        """SSN should be redacted."""
        text = "SSN: 123-45-6789"
        result = sanitize_text(text)
        assert "[SSN_REDACTED]" in result
        assert "123-45-6789" not in result

    def test_sanitize_ip_address(self):
        """IP addresses should be redacted."""
        text = "Connecting from 192.168.1.100"
        result = sanitize_text(text)
        assert "[IP_REDACTED]" in result
        assert "192.168.1.100" not in result

    def test_sanitize_person_name(self):
        """Person names should be detected and redacted by Presidio NLP."""
        text = "Hi, my name is John Smith and I need help."
        result = sanitize_text(text)
        # Presidio should detect "John Smith" as a PERSON entity
        assert "[NAME_REDACTED]" in result
        assert "John Smith" not in result

    def test_sanitize_location(self):
        """Locations should be redacted."""
        text = "I live in New York City."
        result = sanitize_text(text)
        # Presidio should detect "New York City" as a LOCATION
        assert "[LOCATION_REDACTED]" in result

    def test_preserves_non_sensitive_content(self):
        """Non-sensitive content should be preserved."""
        text = "The system shows an Error 505 on the certifications page."
        result = sanitize_text(text)
        # Should be mostly unchanged (no obvious PII)
        assert "Error 505" in result
        assert "certifications page" in result

    def test_empty_text(self):
        """Empty text should return empty string."""
        assert sanitize_text("") == ""

    def test_none_text(self):
        """None should return None."""
        result = sanitize_text(None)  # type: ignore
        assert result is None

    def test_combined_pii(self):
        """Multiple types of PII should all be redacted."""
        text = (
            "Customer John Smith (john.smith@example.com) called from 555-123-4567 "
            "with SSN 123-45-6789 from IP 10.0.0.1"
        )
        result = sanitize_text(text)
        
        # Check that various PII types are redacted
        assert "[EMAIL_REDACTED]" in result
        assert "[PHONE_REDACTED]" in result
        assert "[SSN_REDACTED]" in result
        assert "[IP_REDACTED]" in result
        
        # Original values should be gone
        assert "john.smith@example.com" not in result
        assert "555-123-4567" not in result
        assert "123-45-6789" not in result
        assert "10.0.0.1" not in result

    def test_score_threshold(self):
        """Higher score threshold should reduce false positives."""
        text = "Please call the office."
        # With default threshold, might detect "office" as something
        result_low = sanitize_text(text, score_threshold=0.3)
        result_high = sanitize_text(text, score_threshold=0.8)
        # Higher threshold should be more conservative
        assert len(result_high) >= len(result_low) or result_high == result_low


class TestSanitizeMessages:
    """Test cases for message list sanitization."""

    def test_sanitize_single_message(self):
        """Single message should be sanitized."""
        messages = [
            Message(
                id="m1",
                conversation_id="1024",
                sender="customer",
                content="My email is test@example.com",
                timestamp="10:00 AM",
            )
        ]
        result = sanitize_messages(messages)
        
        assert len(result) == 1
        assert "[EMAIL_REDACTED]" in result[0].content
        assert "test@example.com" not in result[0].content
        # Metadata should be preserved
        assert result[0].id == "m1"
        assert result[0].sender == "customer"

    def test_sanitize_multiple_messages(self):
        """Multiple messages should all be sanitized."""
        messages = [
            Message(
                id="m1",
                conversation_id="1024",
                sender="customer",
                content="Call me at 555-123-4567",
                timestamp="10:00 AM",
            ),
            Message(
                id="m2",
                conversation_id="1024",
                sender="agent",
                content="Contact us at support@company.com",
                timestamp="10:05 AM",
            ),
        ]
        result = sanitize_messages(messages)
        
        assert len(result) == 2
        assert "[PHONE_REDACTED]" in result[0].content
        assert "[EMAIL_REDACTED]" in result[1].content

    def test_original_messages_unchanged(self):
        """Original message list should not be modified."""
        messages = [
            Message(
                id="m1",
                conversation_id="1024",
                sender="customer",
                content="Email: test@example.com",
                timestamp="10:00 AM",
            )
        ]
        original_content = messages[0].content
        
        sanitize_messages(messages)
        
        assert messages[0].content == original_content


class TestSanitizeResolutionNotes:
    """Test cases for resolution notes sanitization."""

    def test_sanitize_notes_with_pii(self):
        """Notes with PII should be sanitized."""
        notes = "Customer John called from 555-123-4567 about billing."
        result = sanitize_resolution_notes(notes)
        assert result is not None
        assert "[PHONE_REDACTED]" in result
        assert "555-123-4567" not in result

    def test_sanitize_notes_none(self):
        """None notes should return None."""
        assert sanitize_resolution_notes(None) is None


class TestGetDetectedEntities:
    """Test cases for the entity detection function."""

    def test_detect_email(self):
        """Should detect email entities."""
        text = "Email me at alice@test.com"
        entities = get_detected_entities(text)
        
        assert len(entities) >= 1
        email_entities = [e for e in entities if e["entity_type"] == "EMAIL_ADDRESS"]
        assert len(email_entities) == 1
        assert email_entities[0]["text"] == "alice@test.com"

    def test_detect_phone(self):
        """Should detect phone entities."""
        text = "Call 555-123-4567"
        entities = get_detected_entities(text)
        
        phone_entities = [e for e in entities if e["entity_type"] == "PHONE_NUMBER"]
        assert len(phone_entities) >= 1

    def test_detect_multiple_entities(self):
        """Should detect multiple entity types."""
        text = "John Smith's email is john@test.com and SSN is 123-45-6789"
        entities = get_detected_entities(text)
        
        entity_types = {e["entity_type"] for e in entities}
        assert "EMAIL_ADDRESS" in entity_types
        assert "US_SSN" in entity_types

    def test_empty_text(self):
        """Empty text should return empty list."""
        assert get_detected_entities("") == []

    def test_no_pii(self):
        """Text without PII should return empty or minimal results."""
        text = "The system is working correctly."
        entities = get_detected_entities(text, score_threshold=0.7)
        # Should have no or very few high-confidence matches
        assert len(entities) <= 1


class TestPresidioFailures:
    """Test Presidio exception handlers (lines 211-213, 232-234, 319-321)."""

    @patch("app.services.data_sanitizer._get_analyzer")
    def test_sanitize_text_analysis_failure_returns_original(self, mock_get_analyzer):
        """When Presidio analyzer.analyze raises, original text is returned."""
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = RuntimeError("NLP model failed")
        mock_get_analyzer.return_value = mock_analyzer

        result = sanitize_text("My email is test@example.com")
        assert result == "My email is test@example.com"

    @patch("app.services.data_sanitizer._get_anonymizer")
    @patch("app.services.data_sanitizer._get_analyzer")
    def test_sanitize_text_anonymization_failure_returns_original(
        self, mock_get_analyzer, mock_get_anonymizer
    ):
        """When Presidio anonymizer.anonymize raises, original text is returned."""
        mock_analyzer = MagicMock()
        mock_result = MagicMock()
        mock_result.entity_type = "EMAIL_ADDRESS"
        mock_analyzer.analyze.return_value = [mock_result]
        mock_get_analyzer.return_value = mock_analyzer

        mock_anonymizer = MagicMock()
        mock_anonymizer.anonymize.side_effect = RuntimeError("Anonymization failed")
        mock_get_anonymizer.return_value = mock_anonymizer

        result = sanitize_text("My email is test@example.com")
        assert result == "My email is test@example.com"

    @patch("app.services.data_sanitizer._get_analyzer")
    def test_get_detected_entities_analysis_failure_returns_empty(self, mock_get_analyzer):
        """When Presidio analyzer.analyze raises in get_detected_entities, returns []."""
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = RuntimeError("NLP model failed")
        mock_get_analyzer.return_value = mock_analyzer

        result = get_detected_entities("My email is test@example.com")
        assert result == []
