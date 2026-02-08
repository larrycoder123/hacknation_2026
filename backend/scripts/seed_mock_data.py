"""Seed mock data for testing the RAG pipeline end-to-end.

Inserts 5 retrieval_corpus entries (with real embeddings), plus enrichment
rows in scripts_master, conversations, and tickets.

All mock IDs contain "MOCK" for easy identification and cleanup.

Usage (from backend/):
    python scripts/seed_mock_data.py          # Insert mock data
    python scripts/seed_mock_data.py --clean   # Remove mock data
"""

import argparse
import sys
from pathlib import Path

# Ensure backend/ is on the path so app.* imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.core.config import settings  # noqa: E402
from app.rag.core.embedder import Embedder  # noqa: E402
from app.rag.core.supabase_client import get_supabase_client  # noqa: E402

# ---------------------------------------------------------------------------
# Mock data definitions
# ---------------------------------------------------------------------------

CORPUS_ENTRIES = [
    {
        "source_type": "SCRIPT",
        "source_id": "SCRIPT-MOCK-001",
        "title": "Advance Property Date Fix Script",
        "content": (
            "Run this backend data-fix script to resolve property date advance "
            "failures caused by data sync inconsistencies. The script updates the "
            "property date pointer in the accounting module after verifying no "
            "pending transactions exist.\n\n"
            "use <DATABASE>\ngo\n\n"
            "update propertydatesetting\n"
            "set current_period_date = <DATE>,\n"
            "    last_advanced_by = 'support_script',\n"
            "    updated_at = getdate()\n"
            "where site_name = <SITE_NAME>\n"
            "  and is_locked = 0\ngo"
        ),
        "category": "Advance Property Date",
        "module": "Accounting / Date Advance",
        "tags": "date-advance,month-end,backend-fix,PropertySuite",
    },
    {
        "source_type": "SCRIPT",
        "source_id": "SCRIPT-MOCK-002",
        "title": "Reset Certification Status Script",
        "content": (
            "Run this backend data-fix script to reset a stuck certification "
            "status. Use when a property certification shows 'Processing' for "
            "more than 24 hours due to a timeout in the compliance sync job.\n\n"
            "use <DATABASE>\ngo\n\n"
            "update certificationstatus\n"
            "set status = 'Pending_Review',\n"
            "    retry_count = 0,\n"
            "    updated_at = getdate()\n"
            "where site_name = <SITE_NAME>\n"
            "  and certification_id = <CERTIFICATION_ID>\ngo"
        ),
        "category": "Certifications",
        "module": "Compliance / Certifications",
        "tags": "certifications,compliance,backend-fix,PropertySuite",
    },
    {
        "source_type": "KB",
        "source_id": "KB-MOCK-000001",
        "title": "Troubleshooting Property Date Advance Issues",
        "content": (
            "When a property manager reports they cannot advance the property date, "
            "follow these steps:\n\n"
            "1. Verify the property ID and current period date in the admin panel.\n"
            "2. Check for pending transactions — the date cannot advance if "
            "unposted transactions exist.\n"
            "3. Confirm the accounting period is not locked by another user.\n"
            "4. If steps 1-3 are clear but the issue persists, escalate to Tier 3 "
            "to run the Advance Property Date Fix Script (SCRIPT-MOCK-001).\n\n"
            "Common error: 'Date advance blocked — pending items found.' "
            "Resolution: Post or void all pending transactions first."
        ),
        "category": "Advance Property Date",
        "module": "Accounting / Date Advance",
        "tags": "date-advance,troubleshooting,month-end,PropertySuite",
    },
    {
        "source_type": "KB",
        "source_id": "KB-MOCK-000002",
        "title": "Certification Compliance Guide",
        "content": (
            "This guide covers the certification compliance workflow in "
            "PropertySuite Affordable.\n\n"
            "Certifications must be submitted within 120 days of the effective "
            "date. The system tracks cert status as: Draft → Submitted → "
            "Processing → Approved/Rejected.\n\n"
            "If a certification is stuck in 'Processing' for more than 24 hours, "
            "this usually indicates a timeout in the compliance sync job. "
            "Escalate to Tier 3 for the Reset Certification Status Script.\n\n"
            "Common issues:\n"
            "- Missing tenant income documentation → cert rejected\n"
            "- TRACS file submission errors → check file format\n"
            "- Property date must be current before submitting certs"
        ),
        "category": "Certifications",
        "module": "Compliance / Certifications",
        "tags": "certifications,compliance,TRACS,PropertySuite",
    },
    {
        "source_type": "TICKET_RESOLUTION",
        "source_id": "CS-MOCK0001",
        "title": "Unable to advance property date after month-end close",
        "content": (
            "Customer reported they could not advance the property date for "
            "Heritage Point (site HPTMN01) after completing month-end close. "
            "The system showed 'Date advance blocked' even though all "
            "transactions were posted.\n\n"
            "Root cause: A data sync inconsistency left a phantom pending "
            "transaction record that was invisible in the UI but blocked the "
            "date advance check.\n\n"
            "Resolution: Ran the Advance Property Date Fix Script "
            "(SCRIPT-MOCK-001) with DATABASE=HeritagePT, SITE_NAME=HPTMN01, "
            "DATE=2026-02-01. Customer confirmed date advanced successfully."
        ),
        "category": "Advance Property Date",
        "module": "Accounting / Date Advance",
        "tags": "date-advance,month-end,data-sync,backend-fix",
    },
]

SCRIPTS_MASTER_ENTRIES = [
    {
        "script_id": "SCRIPT-MOCK-001",
        "script_title": "Advance Property Date Fix Script",
        "script_purpose": (
            "Run this backend data-fix script to resolve property date advance "
            "failures caused by data sync inconsistencies after month-end close."
        ),
        "module": "Accounting / Date Advance",
        "category": "Advance Property Date",
        "source": "Questions",
    },
    {
        "script_id": "SCRIPT-MOCK-002",
        "script_title": "Reset Certification Status Script",
        "script_purpose": (
            "Run this backend data-fix script to reset a stuck certification "
            "status caused by a timeout in the compliance sync job."
        ),
        "module": "Compliance / Certifications",
        "category": "Certifications",
        "source": "Questions",
    },
]

CONVERSATIONS_ENTRY = {
    "ticket_number": "CS-MOCK0001",
    "conversation_id": "CONV-MOCK-000001",
    "channel": "Chat",
    "customer_role": "Property Manager",
    "agent_name": "Alex",
    "product": "ExampleCo PropertySuite Affordable",
    "category": "Advance Property Date",
    "issue_summary": "Unable to advance property date after month-end close",
}

TICKETS_ENTRY = {
    "ticket_number": "CS-MOCK0001",
    "status": "Closed",
    "priority": "High",
    "tier": "3",
    "module": "Accounting / Date Advance",
    "case_type": "Incident",
    "subject": "Unable to advance property date after month-end close",
    "description": (
        "Customer at Heritage Point cannot advance property date. "
        "System shows 'Date advance blocked' despite all transactions posted."
    ),
    "resolution": (
        "Ran Advance Property Date Fix Script. Phantom pending transaction "
        "cleared. Customer confirmed date advanced to 2026-02-01."
    ),
    "root_cause": "Data sync inconsistency left phantom pending transaction record",
    "tags": "date-advance,month-end,backend-fix",
    "script_id": "SCRIPT-MOCK-001",
}


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------


def seed() -> None:
    """Insert mock data with real embeddings."""
    print("Connecting to Supabase...")
    sb = get_supabase_client()
    embedder = Embedder()

    # 1. Embed all corpus content in one batch
    texts = [entry["content"] for entry in CORPUS_ENTRIES]
    print(f"Generating embeddings for {len(texts)} entries (text-embedding-3-large)...")
    embeddings = embedder.embed_batch(texts)

    # 2. Insert retrieval_corpus
    print("Inserting retrieval_corpus entries...")
    for entry, emb in zip(CORPUS_ENTRIES, embeddings):
        row = {**entry, "embedding": emb}
        sb.table("retrieval_corpus").upsert(row).execute()
    print(f"  {len(CORPUS_ENTRIES)} retrieval_corpus rows upserted.")

    # 3. Insert scripts_master (enrichment)
    print("Inserting scripts_master entries...")
    for entry in SCRIPTS_MASTER_ENTRIES:
        sb.table("scripts_master").upsert(entry).execute()
    print(f"  {len(SCRIPTS_MASTER_ENTRIES)} scripts_master rows upserted.")

    # 4. Insert conversations (FK for tickets)
    print("Inserting conversations entry...")
    sb.table("conversations").upsert(CONVERSATIONS_ENTRY).execute()
    print("  1 conversations row upserted.")

    # 5. Insert tickets (enrichment for TICKET_RESOLUTION)
    print("Inserting tickets entry...")
    sb.table("tickets").upsert(TICKETS_ENTRY).execute()
    print("  1 tickets row upserted.")

    print("\nDone! Mock data seeded successfully.")
    print("Test with: GET /api/conversations/{id}/suggested-actions")


def clean() -> None:
    """Remove all mock data (anything with MOCK in the ID)."""
    print("Connecting to Supabase...")
    sb = get_supabase_client()

    # Delete in reverse FK order
    tables_and_filters = [
        ("tickets", "ticket_number", "CS-MOCK0001"),
        ("conversations", "ticket_number", "CS-MOCK0001"),
        ("scripts_master", "script_id", "SCRIPT-MOCK-001"),
        ("scripts_master", "script_id", "SCRIPT-MOCK-002"),
        ("retrieval_corpus", "source_id", "SCRIPT-MOCK-001"),
        ("retrieval_corpus", "source_id", "SCRIPT-MOCK-002"),
        ("retrieval_corpus", "source_id", "KB-MOCK-000001"),
        ("retrieval_corpus", "source_id", "KB-MOCK-000002"),
        ("retrieval_corpus", "source_id", "CS-MOCK0001"),
    ]

    for table, column, value in tables_and_filters:
        result = sb.table(table).delete().eq(column, value).execute()
        count = len(result.data) if result.data else 0
        print(f"  Deleted {count} row(s) from {table} where {column}={value}")

    print("\nDone! Mock data cleaned up.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed or clean mock data for RAG testing")
    parser.add_argument("--clean", action="store_true", help="Remove mock data instead of inserting")
    args = parser.parse_args()

    if args.clean:
        clean()
    else:
        seed()


if __name__ == "__main__":
    main()
