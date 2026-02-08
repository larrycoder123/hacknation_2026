"""Database verification script for SupportMind RAG.

Checks:
1. All 13 tables exist
2. All 3 RPC functions exist (match_corpus, increment_corpus_usage, update_corpus_confidence)
3. learning_events has event_type and flagged_kb_article_id columns
4. retrieval_log has conversation_id column and ticket_number is nullable
5. retrieval_corpus has mock data (MOCK entries)
6. match_corpus RPC works end-to-end with real embedding
"""

import sys
import json
import traceback

sys.path.insert(0, "backend")

from app.rag.core.supabase_client import get_supabase_client
from app.rag.core.embedder import Embedder


def print_result(check_name: str, passed: bool, detail: str = "") -> bool:
    status = "PASS" if passed else "FAIL"
    msg = f"[{status}] {check_name}"
    if detail:
        msg += f" -- {detail}"
    print(msg)
    return passed


def main() -> None:
    print("=" * 70)
    print("SupportMind Database Verification")
    print("=" * 70)
    print()

    results: list[bool] = []

    # ----------------------------------------------------------------
    # Connect
    # ----------------------------------------------------------------
    try:
        client = get_supabase_client()
        print("[INFO] Supabase client created successfully.")
    except Exception as e:
        print(f"[FATAL] Cannot create Supabase client: {e}")
        sys.exit(1)

    # ----------------------------------------------------------------
    # CHECK 1: All 13 tables exist
    # ----------------------------------------------------------------
    print()
    print("-" * 70)
    print("CHECK 1: All 13 tables exist")
    print("-" * 70)

    expected_tables = [
        "categories",
        "placeholder_dictionary",
        "config",
        "scripts_master",
        "knowledge_articles",
        "conversations",
        "script_placeholders",
        "tickets",
        "kb_lineage",
        "learning_events",
        "questions",
        "retrieval_corpus",
        "retrieval_log",
    ]

    for table_name in expected_tables:
        try:
            # Select a single row to verify the table exists
            resp = client.table(table_name).select("*").limit(1).execute()
            passed = True
            row_info = f"{len(resp.data)} row(s) returned in sample"
            results.append(print_result(f"Table '{table_name}' exists", passed, row_info))
        except Exception as e:
            err_str = str(e)
            results.append(print_result(f"Table '{table_name}' exists", False, err_str[:120]))

    # ----------------------------------------------------------------
    # CHECK 2: All 3 RPC functions exist
    # ----------------------------------------------------------------
    print()
    print("-" * 70)
    print("CHECK 2: All 3 RPC functions exist")
    print("-" * 70)

    # 2a: match_corpus -- needs a real embedding vector to call
    # We'll test it properly in check 6; here just verify it doesn't 404
    try:
        # Create a zero vector of correct dimension (3072) just to test the function exists
        zero_vec = [0.0] * 3072
        resp = client.rpc(
            "match_corpus",
            {
                "query_embedding": zero_vec,
                "p_top_k": 1,
                "p_similarity_threshold": 0.0,
            },
        ).execute()
        passed = True
        detail = f"returned {len(resp.data)} row(s) with zero vector"
        results.append(print_result("RPC 'match_corpus' exists", passed, detail))
    except Exception as e:
        results.append(print_result("RPC 'match_corpus' exists", False, str(e)[:150]))

    # 2b: increment_corpus_usage
    try:
        # Call with a nonexistent source -- should succeed (update 0 rows, no error)
        resp = client.rpc(
            "increment_corpus_usage",
            {
                "p_source_type": "__TEST_NONEXISTENT__",
                "p_source_id": "__TEST_NONEXISTENT__",
            },
        ).execute()
        results.append(print_result("RPC 'increment_corpus_usage' exists", True, "called successfully (no-op)"))
    except Exception as e:
        results.append(print_result("RPC 'increment_corpus_usage' exists", False, str(e)[:150]))

    # 2c: update_corpus_confidence
    try:
        # This function raises an exception if the row doesn't exist,
        # so we expect it to fail with a specific message. That still proves the function exists.
        resp = client.rpc(
            "update_corpus_confidence",
            {
                "p_source_type": "__TEST_NONEXISTENT__",
                "p_source_id": "__TEST_NONEXISTENT__",
                "p_delta": 0.0,
                "p_increment_usage": False,
            },
        ).execute()
        # If it somehow succeeds, that's fine too
        results.append(print_result("RPC 'update_corpus_confidence' exists", True, "called successfully"))
    except Exception as e:
        err_str = str(e)
        # The function exists but raises because no matching row -- that's expected
        if "retrieval_corpus row not found" in err_str:
            results.append(print_result(
                "RPC 'update_corpus_confidence' exists", True,
                "function exists (raised expected 'row not found' for test input)"
            ))
        else:
            results.append(print_result("RPC 'update_corpus_confidence' exists", False, err_str[:150]))

    # ----------------------------------------------------------------
    # CHECK 3: learning_events has event_type and flagged_kb_article_id columns
    # ----------------------------------------------------------------
    print()
    print("-" * 70)
    print("CHECK 3: learning_events has event_type and flagged_kb_article_id columns")
    print("-" * 70)

    for col_name in ["event_type", "flagged_kb_article_id"]:
        try:
            # Try to select just this column -- if it doesn't exist, Supabase returns an error
            resp = client.table("learning_events").select(col_name).limit(1).execute()
            results.append(print_result(
                f"Column 'learning_events.{col_name}' exists", True,
                f"sample value: {resp.data[0][col_name] if resp.data else '(no rows)'}"
            ))
        except Exception as e:
            err_str = str(e)
            results.append(print_result(f"Column 'learning_events.{col_name}' exists", False, err_str[:150]))

    # ----------------------------------------------------------------
    # CHECK 4: retrieval_log has conversation_id column and ticket_number is nullable
    # ----------------------------------------------------------------
    print()
    print("-" * 70)
    print("CHECK 4: retrieval_log has conversation_id column; ticket_number is nullable")
    print("-" * 70)

    # 4a: conversation_id column exists
    try:
        resp = client.table("retrieval_log").select("conversation_id").limit(1).execute()
        results.append(print_result(
            "Column 'retrieval_log.conversation_id' exists", True,
            f"sample value: {resp.data[0]['conversation_id'] if resp.data else '(no rows)'}"
        ))
    except Exception as e:
        results.append(print_result("Column 'retrieval_log.conversation_id' exists", False, str(e)[:150]))

    # 4b: ticket_number is nullable -- try inserting a row with null ticket_number
    # We use a test retrieval_id that we'll clean up afterward
    test_retrieval_id = "__VERIFY_NULLABLE_TEST__"
    try:
        # Clean up first in case a previous run left it
        client.table("retrieval_log").delete().eq("retrieval_id", test_retrieval_id).execute()

        # Insert with ticket_number = None
        resp = client.table("retrieval_log").insert({
            "retrieval_id": test_retrieval_id,
            "ticket_number": None,
            "attempt_number": 1,
            "query_text": "test nullable ticket_number",
        }).execute()

        if resp.data and len(resp.data) > 0:
            results.append(print_result(
                "Column 'retrieval_log.ticket_number' is nullable", True,
                "successfully inserted row with ticket_number=NULL"
            ))
        else:
            results.append(print_result(
                "Column 'retrieval_log.ticket_number' is nullable", False,
                "insert returned no data"
            ))

        # Clean up
        client.table("retrieval_log").delete().eq("retrieval_id", test_retrieval_id).execute()
    except Exception as e:
        err_str = str(e)
        if "not-null" in err_str.lower() or "violates not-null" in err_str.lower() or "null value" in err_str.lower():
            results.append(print_result(
                "Column 'retrieval_log.ticket_number' is nullable", False,
                "NOT NULL constraint still in place"
            ))
        else:
            results.append(print_result(
                "Column 'retrieval_log.ticket_number' is nullable", False,
                err_str[:150]
            ))
        # Clean up attempt
        try:
            client.table("retrieval_log").delete().eq("retrieval_id", test_retrieval_id).execute()
        except Exception:
            pass

    # ----------------------------------------------------------------
    # CHECK 5: retrieval_corpus has mock data (MOCK entries)
    # ----------------------------------------------------------------
    print()
    print("-" * 70)
    print("CHECK 5: retrieval_corpus has MOCK entries")
    print("-" * 70)

    try:
        resp = (
            client.table("retrieval_corpus")
            .select("source_type, source_id, title")
            .like("source_id", "%MOCK%")
            .execute()
        )
        mock_count = len(resp.data)
        if mock_count > 0:
            results.append(print_result(
                "retrieval_corpus has MOCK entries", True,
                f"found {mock_count} MOCK row(s)"
            ))
            # Show a few examples
            for row in resp.data[:5]:
                print(f"       -> {row['source_type']} | {row['source_id']} | {row.get('title', '')[:60]}")
        else:
            results.append(print_result(
                "retrieval_corpus has MOCK entries", False,
                "no rows with source_id LIKE 'MOCK%' found"
            ))
    except Exception as e:
        results.append(print_result("retrieval_corpus has MOCK entries", False, str(e)[:150]))

    # ----------------------------------------------------------------
    # CHECK 6: match_corpus RPC works end-to-end with real embedding
    # ----------------------------------------------------------------
    print()
    print("-" * 70)
    print("CHECK 6: match_corpus RPC works with real embedding")
    print("-" * 70)

    try:
        embedder = Embedder()
        print("[INFO] Embedding query: 'property date advance'...")
        query_embedding = embedder.embed("property date advance")
        print(f"[INFO] Got embedding vector of dimension {len(query_embedding)}")

        resp = client.rpc(
            "match_corpus",
            {
                "query_embedding": query_embedding,
                "p_top_k": 5,
                "p_similarity_threshold": 0.0,
            },
        ).execute()

        result_count = len(resp.data)
        if result_count > 0:
            results.append(print_result(
                "match_corpus returns results with real embedding", True,
                f"got {result_count} result(s)"
            ))
            print()
            print("  Top results:")
            for i, row in enumerate(resp.data[:5], 1):
                sim = row.get("similarity", 0)
                title = (row.get("title") or "(no title)")[:70]
                src = row.get("source_type", "?")
                sid = row.get("source_id", "?")
                print(f"    {i}. [{src}] {sid} (sim={sim:.4f}) {title}")
        else:
            results.append(print_result(
                "match_corpus returns results with real embedding", False,
                "RPC returned 0 results"
            ))
    except Exception as e:
        traceback.print_exc()
        results.append(print_result(
            "match_corpus returns results with real embedding", False,
            str(e)[:200]
        ))

    # ----------------------------------------------------------------
    # SUMMARY
    # ----------------------------------------------------------------
    print()
    print("=" * 70)
    total = len(results)
    passed = sum(results)
    failed = total - passed
    print(f"SUMMARY: {passed}/{total} checks passed, {failed} failed")
    if failed == 0:
        print("All checks passed!")
    else:
        print(f"WARNING: {failed} check(s) failed. Review output above.")
    print("=" * 70)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
