"""Data sanitization utilities using Microsoft Presidio for PII detection.

This module provides functions to sanitize text content before it is processed
or stored, ensuring that personal identifiable information (PII) and other
sensitive data is detected and redacted using NLP-powered analysis.

Uses Microsoft Presidio with spaCy NLP backend for accurate entity recognition.
"""

import logging
from typing import List, Optional

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from ..schemas.messages import Message

logger = logging.getLogger(__name__)


# Lazy initialization to avoid loading models at import time
_analyzer: Optional[AnalyzerEngine] = None
_anonymizer: Optional[AnonymizerEngine] = None


def _create_custom_recognizers() -> list:
    """Create custom pattern recognizers for enhanced PII detection."""
    from presidio_analyzer import Pattern, PatternRecognizer
    
    recognizers = []
    
    # Enhanced SSN recognizer with common formats
    # Presidio's default SSN recognizer is conservative; this catches more variants
    ssn_patterns = [
        Pattern(
            name="ssn_with_dashes",
            regex=r"\b\d{3}-\d{2}-\d{4}\b",
            score=0.85,
        ),
        Pattern(
            name="ssn_with_spaces",
            regex=r"\b\d{3}\s\d{2}\s\d{4}\b",
            score=0.85,
        ),
        Pattern(
            name="ssn_no_separator",
            regex=r"\b\d{9}\b",
            score=0.3,  # Lower score for 9 digits without context
        ),
    ]
    ssn_recognizer = PatternRecognizer(
        supported_entity="US_SSN",
        patterns=ssn_patterns,
        name="CustomSSNRecognizer",
    )
    recognizers.append(ssn_recognizer)
    
    # Account number recognizer (generic patterns)
    account_patterns = [
        Pattern(
            name="account_with_prefix",
            regex=r"\b(?:account|acct|acc)[\s#:]*\d{4,}\b",
            score=0.7,
        ),
        Pattern(
            name="customer_id",
            regex=r"\b(?:customer|cust)[\s#:]*(?:id|number|no|#)?[\s:]*\d{4,}\b",
            score=0.7,
        ),
        Pattern(
            name="property_id",
            regex=r"\b(?:property|prop)[\s#:]*(?:id|number|no|#)?[\s:]*\d{4,}\b",
            score=0.7,
        ),
    ]
    account_recognizer = PatternRecognizer(
        supported_entity="ACCOUNT_NUMBER",
        patterns=account_patterns,
        name="AccountNumberRecognizer",
    )
    recognizers.append(account_recognizer)
    
    return recognizers


def _get_analyzer() -> AnalyzerEngine:
    """Get or create the Presidio analyzer engine (lazy initialization)."""
    global _analyzer
    if _analyzer is None:
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        logger.info("Initializing Presidio AnalyzerEngine with spaCy en_core_web_sm...")
        provider = NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        })
        _analyzer = AnalyzerEngine(nlp_engine=provider.create_engine())

        # Register custom recognizers for enhanced detection
        for recognizer in _create_custom_recognizers():
            _analyzer.registry.add_recognizer(recognizer)
            logger.debug("Registered custom recognizer: %s", recognizer.name)

    return _analyzer


def _get_anonymizer() -> AnonymizerEngine:
    """Get or create the Presidio anonymizer engine (lazy initialization)."""
    global _anonymizer
    if _anonymizer is None:
        _anonymizer = AnonymizerEngine()
    return _anonymizer


# All PII entity types that Presidio can detect
# See: https://microsoft.github.io/presidio/supported_entities/
SUPPORTED_ENTITIES = [
    # Personal identifiers
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "LOCATION",
    "DATE_TIME",
    
    # Financial
    "CREDIT_CARD",
    "IBAN_CODE",
    "US_BANK_NUMBER",
    "CRYPTO",
    
    # Government IDs
    "US_SSN",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "UK_NHS",
    "US_ITIN",
    
    # Technical
    "IP_ADDRESS",
    "URL",
    
    # Medical
    "MEDICAL_LICENSE",
    "NRP",  # National Registration/ID number
    
    # Custom (registered via custom recognizers)
    "ACCOUNT_NUMBER",
]


# Map entity types to human-readable placeholder tokens
ENTITY_PLACEHOLDER_MAP = {
    "PERSON": "[NAME_REDACTED]",
    "EMAIL_ADDRESS": "[EMAIL_REDACTED]",
    "PHONE_NUMBER": "[PHONE_REDACTED]",
    "CREDIT_CARD": "[CARD_REDACTED]",
    "US_SSN": "[SSN_REDACTED]",
    "US_ITIN": "[ITIN_REDACTED]",
    "US_PASSPORT": "[PASSPORT_REDACTED]",
    "US_DRIVER_LICENSE": "[LICENSE_REDACTED]",
    "US_BANK_NUMBER": "[BANK_ACCOUNT_REDACTED]",
    "IBAN_CODE": "[IBAN_REDACTED]",
    "IP_ADDRESS": "[IP_REDACTED]",
    "LOCATION": "[LOCATION_REDACTED]",
    "DATE_TIME": "[DATE_REDACTED]",
    "URL": "[URL_REDACTED]",
    "CRYPTO": "[CRYPTO_REDACTED]",
    "UK_NHS": "[NHS_REDACTED]",
    "MEDICAL_LICENSE": "[MEDICAL_LICENSE_REDACTED]",
    "NRP": "[ID_REDACTED]",
    "ACCOUNT_NUMBER": "[ACCOUNT_REDACTED]",
}

# Default placeholder for any entity type not in the map
DEFAULT_PLACEHOLDER = "[PII_REDACTED]"


def sanitize_text(
    text: str,
    customer_name: Optional[str] = None,
    additional_names: Optional[List[str]] = None,
    language: str = "en",
    score_threshold: float = 0.4,
) -> str:
    """Remove PII and sensitive information from text content using Presidio.
    
    Args:
        text: The text content to sanitize.
        customer_name: Optional customer name (used as hint, Presidio will detect names via NLP).
        additional_names: Optional list of additional names (used as hints).
        language: Language code for analysis (default: "en").
        score_threshold: Minimum confidence score for PII detection (0.0-1.0).
    
    Returns:
        Sanitized text with PII replaced by descriptive placeholder tokens.
    
    Note:
        The customer_name and additional_names parameters are kept for API
        compatibility but Presidio's NLP engine will detect names automatically.
        These can be used for logging or additional custom logic if needed.
    """
    if not text:
        return text if text is not None else None  # type: ignore
    
    analyzer = _get_analyzer()
    anonymizer = _get_anonymizer()
    
    # Analyze text for PII entities
    try:
        results: List[RecognizerResult] = analyzer.analyze(
            text=text,
            entities=SUPPORTED_ENTITIES,
            language=language,
            score_threshold=score_threshold,
        )
    except Exception as e:
        logger.warning("Presidio analysis failed, returning original text: %s", e)
        return text
    
    if not results:
        return text
    
    # Build operator config with custom placeholders per entity type
    operators = {}
    for entity_type in set(r.entity_type for r in results):
        placeholder = ENTITY_PLACEHOLDER_MAP.get(entity_type, DEFAULT_PLACEHOLDER)
        operators[entity_type] = OperatorConfig("replace", {"new_value": placeholder})
    
    # Anonymize the text
    try:
        anonymized_result = anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators,
        )
        return anonymized_result.text
    except Exception as e:
        logger.warning("Presidio anonymization failed, returning original text: %s", e)
        return text


def sanitize_messages(
    messages: List[Message],
    customer_name: Optional[str] = None,
) -> List[Message]:
    """Sanitize a list of conversation messages using Presidio.
    
    Creates new Message objects with sanitized content.
    
    Args:
        messages: List of Message objects to sanitize.
        customer_name: Optional customer name (Presidio detects names automatically).
    
    Returns:
        New list of Message objects with sanitized content.
    """
    sanitized_messages = []
    
    for msg in messages:
        # Sanitize the message content
        sanitized_content = sanitize_text(msg.content, customer_name=customer_name)
        
        # Create a new message with sanitized content
        sanitized_msg = Message(
            id=msg.id,
            conversation_id=msg.conversation_id,
            sender=msg.sender,
            content=sanitized_content,
            timestamp=msg.timestamp,
        )
        sanitized_messages.append(sanitized_msg)
    
    return sanitized_messages


def sanitize_resolution_notes(
    notes: Optional[str],
    customer_name: Optional[str] = None,
) -> Optional[str]:
    """Sanitize resolution notes text using Presidio.
    
    Args:
        notes: Optional resolution notes to sanitize.
        customer_name: Optional customer name (Presidio detects names automatically).
    
    Returns:
        Sanitized notes or None if input was None.
    """
    if notes is None:
        return None
    
    return sanitize_text(notes, customer_name=customer_name)


def get_detected_entities(
    text: str,
    language: str = "en",
    score_threshold: float = 0.4,
) -> List[dict]:
    """Analyze text and return detected PII entities (without redacting).
    
    Useful for auditing or logging what PII was detected.
    
    Args:
        text: Text to analyze.
        language: Language code (default: "en").
        score_threshold: Minimum confidence score.
    
    Returns:
        List of dicts with entity_type, start, end, score, and matched text.
    """
    if not text:
        return []
    
    analyzer = _get_analyzer()
    
    try:
        results = analyzer.analyze(
            text=text,
            entities=SUPPORTED_ENTITIES,
            language=language,
            score_threshold=score_threshold,
        )
    except Exception as e:
        logger.warning("Presidio analysis failed: %s", e)
        return []
    
    return [
        {
            "entity_type": r.entity_type,
            "start": r.start,
            "end": r.end,
            "score": round(r.score, 3),
            "text": text[r.start:r.end],
        }
        for r in results
    ]
