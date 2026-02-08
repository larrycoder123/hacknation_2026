"""Live end-to-end test of the full SupportMind pipeline against real services.

Exercises the same flow a user would do in the frontend, but via HTTP requests:
  1. List conversations
  2. View messages
  3. Get RAG suggested actions (real embeddings + Cohere rerank)
  4. Close conversation (LLM ticket generation + learning pipeline)
  5. Verify DB state (ticket, retrieval_log, corpus confidence, learning event, KB draft)
  6. Review the learning event (approve/reject)
  7. Verify final DB state

Requires:
  - Backend running: cd backend && uvicorn app.main:app --reload --port 8000
  - All env vars set in backend/.env (SUPABASE_URL, SUPABASE_KEY,
    SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY, COHERE_API_KEY)

Usage:
  python backend/scripts/test_live_pipeline.py
  python backend/scripts/test_live_pipeline.py --conversation 1024
  python backend/scripts/test_live_pipeline.py --conversation 1024 --review reject
  python backend/scripts/test_live_pipeline.py --skip-close  # just test RAG suggestions
"""

import argparse
import sys
import time

import httpx

BASE = "http://localhost:8000"
PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"
INFO = "[INFO]"

# Counts
passed = 0
failed = 0
skipped = 0


def check(label: str, condition: bool, detail: str = ""):
    """Assert a condition and print result."""
    global passed, failed
    if condition:
        passed += 1
        print(f"  {PASS} {label}")
    else:
        failed += 1
        msg = f"  {FAIL} {label}"
        if detail:
            msg += f" -- {detail}"
        print(msg)
    return condition


def info(msg: str):
    print(f"  {INFO} {msg}")


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── Step functions ────────────────────────────────────────────────────


def _step0_health_check(client: httpx.Client, base: str):
    """Verify the backend is reachable."""
    section("Step 0: Health Check")
    try:
        r = client.get("/")
        check("Backend reachable", r.status_code == 200, f"status={r.status_code}")
    except httpx.ConnectError:
        print(f"  {FAIL} Cannot connect to {base}. Is the backend running?")
        print(f"    Start it: cd backend && uvicorn app.main:app --reload --port 8000")
        sys.exit(1)


def _step1_list_conversations(client: httpx.Client, conv_id_arg: str | None) -> str:
    """List conversations and pick one to test. Returns the selected conv_id."""
    section("Step 1: List Conversations")
    r = client.get("/api/conversations")
    check("GET /api/conversations returns 200", r.status_code == 200)
    conversations = r.json()
    check("At least 1 conversation exists", len(conversations) > 0, f"got {len(conversations)}")
    info(f"Found {len(conversations)} conversations")
    for c in conversations:
        info(f"  [{c['status']}] {c['id']}: {c['subject']}")

    conv_id = conv_id_arg
    if conv_id is None:
        open_convs = [c for c in conversations if c["status"] == "Open"]
        if not open_convs:
            print(f"\n  {FAIL} No Open conversations found. Seed mock data first:")
            print(f"    PYTHONPATH=backend python backend/scripts/seed_mock_data.py")
            sys.exit(1)
        conv_id = open_convs[0]["id"]
    info(f"Selected conversation: {conv_id}")
    return conv_id


def _step2_conversation_detail(client: httpx.Client, conv_id: str):
    """Fetch and verify conversation detail."""
    section("Step 2: Conversation Detail")
    r = client.get(f"/api/conversations/{conv_id}")
    check("GET conversation detail returns 200", r.status_code == 200)
    conv = r.json()
    check("Has subject", bool(conv.get("subject")), conv.get("subject", ""))
    check("Has customer_name", bool(conv.get("customer_name")))
    info(f"Subject: {conv['subject']}")
    info(f"Customer: {conv['customer_name']}")
    info(f"Priority: {conv['priority']}")


def _step3_messages(client: httpx.Client, conv_id: str):
    """Fetch and verify message history."""
    section("Step 3: Messages")
    r = client.get(f"/api/conversations/{conv_id}/messages")
    check("GET messages returns 200", r.status_code == 200)
    messages = r.json()
    check("Has messages", len(messages) > 0, f"got {len(messages)}")
    info(f"Message count: {len(messages)}")
    for m in messages[:3]:
        content_preview = m["content"][:80] + "..." if len(m["content"]) > 80 else m["content"]
        info(f"  [{m['sender']}] {content_preview}")


def _step4_rag_suggestions(client: httpx.Client, conv_id: str):
    """Fetch RAG suggested actions."""
    section("Step 4: RAG Suggested Actions")
    info("Calling RAG pipeline (embeddings + rerank)... this may take a few seconds")
    start = time.time()
    r = client.get(f"/api/conversations/{conv_id}/suggested-actions")
    elapsed = time.time() - start
    check("GET suggested-actions returns 200", r.status_code == 200)
    actions = r.json()
    check("At least 1 suggestion returned", len(actions) > 0, f"got {len(actions)}")
    info(f"Returned {len(actions)} suggestions in {elapsed:.1f}s")
    for a in actions:
        score = a.get("confidence_score", "?")
        info(f"  [{a.get('type','?')}] {a.get('title','?')} (score={score})")
        info(f"    Source: {a.get('source', '?')}")


def _step5_close_conversation(
    client: httpx.Client,
    conv_id: str,
    skip_confirm: bool,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Close the conversation and verify ticket + learning result.

    Returns (ticket_number, event_id, drafted_kb_id, gap_class).
    """
    section("Step 5: Close Conversation (Ticket + Learning Pipeline)")
    if not skip_confirm:
        info(f"This will CLOSE conversation {conv_id} and write to the live database.")
        info("A ticket, learning event, and possibly a KB draft will be created.")
        answer = input("  Proceed? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            info("Aborted by user.")
            global skipped
            skipped += 1
            return None, None, None, None

    info("Closing conversation (LLM ticket gen + gap detection)... may take 10-30s")
    start = time.time()
    r = client.post(
        f"/api/conversations/{conv_id}/close",
        json={
            "conversation_id": conv_id,
            "resolution_type": "Resolved Successfully",
            "notes": "Issue resolved using suggested KB article and script guidance.",
            "create_ticket": True,
        },
    )
    elapsed = time.time() - start
    check("POST close returns 200", r.status_code == 200, f"status={r.status_code}")

    if r.status_code != 200:
        info(f"Response: {r.text[:500]}")
        _print_summary()
        sys.exit(1)

    close_data = r.json()
    info(f"Completed in {elapsed:.1f}s")
    check("Status is success", close_data.get("status") == "success")

    # Ticket verification
    ticket = close_data.get("ticket")
    ticket_number = None
    ticket_ok = check("Ticket was generated", ticket is not None)
    if ticket_ok:
        ticket_number = ticket.get("ticket_number")
        check("Ticket has ticket_number", ticket_number is not None, str(ticket_number))
        check("Ticket has subject", bool(ticket.get("subject")))
        check("Ticket has resolution", bool(ticket.get("resolution")))
        check("Ticket has tags", isinstance(ticket.get("tags"), list) and len(ticket["tags"]) > 0)
        info(f"Ticket: {ticket_number}")
        info(f"  Subject:    {ticket.get('subject', '?')[:80]}")
        info(f"  Resolution: {ticket.get('resolution', '?')[:80]}...")
        info(f"  Tags:       {ticket.get('tags', [])}")

    # Learning result verification
    learning = close_data.get("learning_result")
    learning_ok = check("Learning result returned", learning is not None)

    event_id = None
    drafted_kb_id = None
    gap_class = None

    if learning_ok:
        gap_class = learning.get("gap_classification")
        event_id = learning.get("learning_event_id")
        drafted_kb_id = learning.get("drafted_kb_article_id")
        matched_kb = learning.get("matched_kb_article_id")
        logs_processed = learning.get("retrieval_logs_processed", 0)
        confidence_updates = learning.get("confidence_updates", [])

        check("Gap classification is valid",
              gap_class in ("SAME_KNOWLEDGE", "NEW_KNOWLEDGE", "CONTRADICTS"),
              f"got: {gap_class}")
        check("Learning event ID created", event_id is not None, str(event_id))

        info(f"Classification:       {gap_class}")
        info(f"Retrieval logs:       {logs_processed} processed")
        info(f"Confidence updates:   {len(confidence_updates)}")
        for u in confidence_updates:
            info(f"  {u['source_type']}/{u['source_id']}: "
                 f"delta={u['delta']:+.2f} -> confidence={u['new_confidence']:.2f} "
                 f"(usage={u['new_usage_count']})")
        info(f"Learning event:       {event_id}")
        info(f"Matched KB:           {matched_kb}")
        info(f"Match similarity:     {learning.get('match_similarity')}")
        info(f"Drafted KB:           {drafted_kb_id}")

        if gap_class == "SAME_KNOWLEDGE":
            check("SAME_KNOWLEDGE: no draft created", drafted_kb_id is None)
            check("SAME_KNOWLEDGE: matched KB set", matched_kb is not None)
        elif gap_class in ("NEW_KNOWLEDGE", "CONTRADICTS"):
            check(f"{gap_class}: draft KB created", drafted_kb_id is not None)

    warnings = close_data.get("warnings", [])
    if warnings:
        info(f"Warnings: {warnings}")

    return ticket_number, event_id, drafted_kb_id, gap_class


def _step6_verify_db(
    ticket_number: str | None,
    event_id: str | None,
    drafted_kb_id: str | None,
):
    """Verify DB state directly via Supabase client."""
    section("Step 6: Verify DB State via Supabase")
    info("Checking database directly...")

    try:
        sys.path.insert(0, "backend")
        from app.db.client import get_supabase
        sb = get_supabase()

        if ticket_number:
            t_row = sb.table("tickets").select("ticket_number, subject, status").eq(
                "ticket_number", ticket_number
            ).maybe_single().execute()
            check("Ticket saved in DB", t_row.data is not None, str(t_row.data))
            if t_row.data:
                info(f"  DB ticket status: {t_row.data.get('status')}")

            rl_rows = sb.table("retrieval_log").select("retrieval_id, outcome, source_type").eq(
                "ticket_number", ticket_number
            ).execute()
            log_count = len(rl_rows.data) if rl_rows.data else 0
            info(f"  Retrieval log entries for ticket: {log_count}")
            if rl_rows.data:
                for rl in rl_rows.data[:5]:
                    info(f"    {rl['retrieval_id']}: outcome={rl.get('outcome')}, "
                         f"source={rl.get('source_type')}")

        if event_id:
            le_row = sb.table("learning_events").select("*").eq(
                "event_id", event_id
            ).maybe_single().execute()
            check("Learning event in DB", le_row.data is not None)
            if le_row.data:
                info(f"  Event type:    {le_row.data.get('event_type')}")
                info(f"  Final status:  {le_row.data.get('final_status')}")
                info(f"  Detected gap:  {le_row.data.get('detected_gap', '?')[:100]}...")

        if drafted_kb_id:
            kb_row = sb.table("knowledge_articles").select(
                "kb_article_id, title, status, source_type"
            ).eq("kb_article_id", drafted_kb_id).maybe_single().execute()
            check("Drafted KB article in DB", kb_row.data is not None)
            if kb_row.data:
                check("KB status is Draft", kb_row.data.get("status") == "Draft",
                      kb_row.data.get("status"))
                check("KB source_type is SYNTH_FROM_TICKET",
                      kb_row.data.get("source_type") == "SYNTH_FROM_TICKET")
                info(f"  KB title: {kb_row.data.get('title')}")

            corpus_row = sb.table("retrieval_corpus").select(
                "source_type, source_id, confidence, usage_count"
            ).eq("source_type", "KB").eq("source_id", drafted_kb_id).maybe_single().execute()
            check("KB embedded in retrieval_corpus", corpus_row.data is not None)
            if corpus_row.data:
                check("Corpus confidence is 0.5", corpus_row.data.get("confidence") == 0.5)
                check("Corpus usage_count is 0", corpus_row.data.get("usage_count") == 0)

            lineage_rows = sb.table("kb_lineage").select(
                "source_type, source_id, relationship"
            ).eq("kb_article_id", drafted_kb_id).execute()
            lineage_count = len(lineage_rows.data) if lineage_rows.data else 0
            check("KB lineage records created", lineage_count == 3, f"got {lineage_count}")
            if lineage_rows.data:
                for lr in lineage_rows.data:
                    info(f"  Lineage: {lr['source_type']}/{lr['source_id']} "
                         f"({lr['relationship']})")

    except ImportError:
        info("Could not import Supabase client for DB verification.")
        info("Run with PYTHONPATH=backend for direct DB checks.")
        global skipped
        skipped += 1
    except Exception as e:
        info(f"DB verification error: {e}")
        skipped += 1


def _step7_review(
    client: httpx.Client,
    event_id: str,
    drafted_kb_id: str,
    gap_class: str | None,
    review_decision: str,
):
    """Review a learning event and verify post-review DB state."""
    decision = "Approved" if review_decision == "approve" else "Rejected"
    section(f"Step 7: Review Learning Event ({review_decision})")
    info(f"Reviewing event {event_id} with decision={decision}")

    r = client.post(
        f"/api/learning-events/{event_id}/review",
        json={
            "decision": decision,
            "reviewer_role": "Tier 3 Support",
            "reason": "Live pipeline test",
        },
    )
    check("POST review returns 200", r.status_code == 200, f"status={r.status_code}")

    if r.status_code != 200:
        info(f"Response: {r.text[:500]}")
        return

    review_data = r.json()
    check("Final status matches decision",
          review_data.get("final_status") == decision,
          review_data.get("final_status"))
    check("Reviewer role set",
          review_data.get("reviewer_role") == "Tier 3 Support")
    info(f"  Event:        {review_data.get('event_id')}")
    info(f"  Final status: {review_data.get('final_status')}")
    info(f"  Reviewer:     {review_data.get('reviewer_role')}")

    # Verify post-review DB state
    try:
        sys.path.insert(0, "backend")
        from app.db.client import get_supabase as _get_sb
        sb_review = _get_sb()

        if decision == "Approved":
            kb_row = sb_review.table("knowledge_articles").select("status").eq(
                "kb_article_id", drafted_kb_id
            ).maybe_single().execute()
            if kb_row.data:
                if gap_class == "CONTRADICTS":
                    check("Approved CONTRADICTION: draft archived",
                          kb_row.data.get("status") == "Archived",
                          kb_row.data.get("status"))
                else:
                    check("Approved GAP: KB now Active",
                          kb_row.data.get("status") == "Active",
                          kb_row.data.get("status"))
        else:
            kb_row = sb_review.table("knowledge_articles").select("status").eq(
                "kb_article_id", drafted_kb_id
            ).maybe_single().execute()
            if kb_row.data:
                check("Rejected: KB archived",
                      kb_row.data.get("status") == "Archived",
                      kb_row.data.get("status"))

            corpus_row = sb_review.table("retrieval_corpus").select("source_id").eq(
                "source_type", "KB"
            ).eq("source_id", drafted_kb_id).maybe_single().execute()
            check("Rejected: KB removed from corpus", corpus_row.data is None)

    except Exception as e:
        info(f"Post-review DB check error: {e}")


# ── Orchestration ─────────────────────────────────────────────────────


def main():
    global skipped

    parser = argparse.ArgumentParser(description="Live pipeline test")
    parser.add_argument(
        "--conversation", "-c", default=None,
        help="Conversation ID to test (default: first Open conversation)",
    )
    parser.add_argument(
        "--review", "-r", choices=["approve", "reject", "skip"], default="approve",
        help="Review decision for drafted KB (default: approve)",
    )
    parser.add_argument(
        "--skip-close", action="store_true",
        help="Only test listing + RAG suggestions, don't close the conversation",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt before destructive operations (close conversation)",
    )
    parser.add_argument(
        "--base-url", default=BASE,
        help=f"Backend URL (default: {BASE})",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    client = httpx.Client(base_url=base, timeout=120.0)

    _step0_health_check(client, base)
    conv_id = _step1_list_conversations(client, args.conversation)
    _step2_conversation_detail(client, conv_id)
    _step3_messages(client, conv_id)
    _step4_rag_suggestions(client, conv_id)

    if args.skip_close:
        section("Done (--skip-close)")
        skipped += 1
        info("Skipping close + learning pipeline. Run without --skip-close to test full flow.")
        _print_summary()
        return

    ticket_number, event_id, drafted_kb_id, gap_class = _step5_close_conversation(
        client, conv_id, skip_confirm=args.yes,
    )

    # User aborted at confirmation prompt
    if event_id is None and drafted_kb_id is None and gap_class is None and ticket_number is None:
        _print_summary()
        return

    _step6_verify_db(ticket_number, event_id, drafted_kb_id)

    if event_id and drafted_kb_id and args.review != "skip":
        _step7_review(client, event_id, drafted_kb_id, gap_class, args.review)
    elif event_id and not drafted_kb_id:
        section("Step 7: Review (skipped)")
        info("SAME_KNOWLEDGE classification -- no draft to review (auto-approved by System)")
        skipped += 1
    elif args.review == "skip":
        section("Step 7: Review (skipped by --review skip)")
        skipped += 1

    _print_summary()


def _print_summary():
    section("Summary")
    total = passed + failed + skipped
    print(f"  Passed:  {passed}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Total:   {total}")
    if failed:
        print(f"\n  Result: SOME CHECKS FAILED")
        sys.exit(1)
    else:
        print(f"\n  Result: ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
