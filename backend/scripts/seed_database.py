#!/usr/bin/env python3
"""
Seed the Supabase database from SupportMind__Final_Data.xlsx.

Parses the Excel file, upserts all data in FK-dependency order via supabase-py,
then batch-embeds retrieval_corpus rows that have NULL embeddings.

Usage:
    cd backend
    PYTHONPATH=. python3 scripts/seed_database.py
    PYTHONPATH=. python3 scripts/seed_database.py --skip-embeddings
    PYTHONPATH=. python3 scripts/seed_database.py --embeddings-only
    PYTHONPATH=. python3 scripts/seed_database.py --yes              # skip confirmation
"""

import argparse
import os
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Excel XLSX parser (stdlib only)
# ---------------------------------------------------------------------------

EXCEL_EPOCH = datetime(1899, 12, 30)


def excel_serial_to_timestamp(serial_str):
    """Convert an Excel serial-date float string to ISO 8601 UTC string."""
    if not serial_str:
        return None
    try:
        serial = float(serial_str)
    except (ValueError, TypeError):
        return None
    dt = EXCEL_EPOCH + timedelta(days=serial)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


class XlsxReader:
    """Stdlib-only XLSX reader. Use as a context manager."""

    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        try:
            self._shared_strings = self._parse_shared_strings()
            self._sheet_paths = self._parse_sheet_paths()
        except Exception:
            self.z.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _parse_shared_strings(self):
        try:
            ss_xml = self.z.read("xl/sharedStrings.xml")
        except KeyError:
            return []
        root = ET.fromstring(ss_xml)
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        strings = []
        for si in root.findall("s:si", ns):
            texts = si.findall(".//s:t", ns)
            strings.append("".join(t.text or "" for t in texts))
        return strings

    def _parse_sheet_paths(self):
        wb_xml = self.z.read("xl/workbook.xml")
        wb_root = ET.fromstring(wb_xml)
        ns_wb = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        rels_xml = self.z.read("xl/_rels/workbook.xml.rels")
        rels_root = ET.fromstring(rels_xml)
        rid_to_path = {}
        for rel in rels_root:
            rid_to_path[rel.attrib["Id"]] = "xl/" + rel.attrib["Target"]
        result = {}
        ns_r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        for s in wb_root.findall(".//s:sheet", ns_wb):
            name = s.attrib["name"]
            rid = s.attrib[f"{{{ns_r}}}id"]
            result[name] = rid_to_path.get(rid, "")
        return result

    @staticmethod
    def _col_to_idx(col_str):
        r = 0
        for c in col_str:
            r = r * 26 + (ord(c) - ord("A") + 1)
        return r - 1

    def read_sheet(self, sheet_name):
        """Return (headers: list[str], rows: list[dict])."""
        path = self._sheet_paths.get(sheet_name)
        if not path:
            raise KeyError(f"Sheet '{sheet_name}' not found")
        xml_data = self.z.read(path)
        root = ET.fromstring(xml_data)
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        raw_rows = []
        for row_el in root.findall(".//s:sheetData/s:row", ns):
            cells = {}
            for c in row_el.findall("s:c", ns):
                ref = c.attrib["r"]
                col_str = re.match(r"([A-Z]+)", ref).group(1)
                col_idx = self._col_to_idx(col_str)
                val_el = c.find("s:v", ns)
                if val_el is not None and val_el.text is not None:
                    if c.attrib.get("t") == "s":
                        val = self._shared_strings[int(val_el.text)]
                    else:
                        val = val_el.text
                else:
                    val = None
                cells[col_idx] = val
            raw_rows.append(cells)

        if not raw_rows:
            return [], []

        header_cells = raw_rows[0]
        max_col = max(header_cells.keys()) + 1 if header_cells else 0
        headers = [header_cells.get(i, f"col_{i}") or f"col_{i}" for i in range(max_col)]

        data = []
        for raw in raw_rows[1:]:
            row = {}
            for i, h in enumerate(headers):
                row[h] = raw.get(i)
            data.append(row)
        return headers, data

    def close(self):
        self.z.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_val(val):
    """Return None for empty/whitespace-only strings, otherwise stripped string."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def batch_upsert(supabase, table, rows, on_conflict, batch_size=200):
    """Upsert rows in batches. Returns total upserted count."""
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            supabase.table(table).upsert(batch, on_conflict=on_conflict).execute()
        except Exception as exc:
            batch_num = i // batch_size + 1
            print(
                f"\n  ERROR upserting {table} batch {batch_num} "
                f"(rows {i}-{i + len(batch) - 1}): {exc}",
                file=sys.stderr,
            )
            raise
        total += len(batch)
    return total


def validate_columns(headers, required, sheet_name):
    """Abort early if required columns are missing from a sheet."""
    missing = set(required) - set(headers)
    if missing:
        raise ValueError(
            f"Sheet '{sheet_name}' is missing required columns: {sorted(missing)}"
        )


# ---------------------------------------------------------------------------
# Per-table seed functions
# ---------------------------------------------------------------------------

def _seed_categories(supabase, reader, ticket_rows):
    print("  [1/11] categories")
    categories = set()
    for sheet in ("Scripts_Master", "Conversations", "Questions", "Knowledge_Articles"):
        _, rows = reader.read_sheet(sheet)
        for row in rows:
            cat = row.get("Category")
            if cat and cat.strip():
                categories.add(cat.strip())
    for row in ticket_rows:
        cat = row.get("Category")
        if cat and cat.strip():
            categories.add(cat.strip())

    records = [{"name": c} for c in sorted(categories)]
    n = batch_upsert(supabase, "categories", records, "name")
    print(f"         {n} rows")


def _seed_placeholder_dictionary(supabase, reader):
    print("  [2/11] placeholder_dictionary")
    headers, pd_rows = reader.read_sheet("Placeholder_Dictionary")
    validate_columns(headers, ["Placeholder"], "Placeholder_Dictionary")
    seen = set()
    records = []
    for row in pd_rows:
        ph = clean_val(row.get("Placeholder"))
        if not ph or ph in seen:
            continue
        seen.add(ph)
        records.append({
            "placeholder": ph,
            "meaning": clean_val(row.get("Meaning")),
            "example": clean_val(row.get("Example")),
        })
    n = batch_upsert(supabase, "placeholder_dictionary", records, "placeholder")
    print(f"         {n} rows")
    return seen  # needed for script_placeholders FK filter


def _seed_scripts_master(supabase, sm_rows):
    print("  [3/11] scripts_master")
    records = []
    script_inputs_map = {}
    for row in sm_rows:
        sid = clean_val(row.get("Script_ID"))
        if not sid:
            continue
        records.append({
            "script_id": sid,
            "script_title": clean_val(row.get("Script_Title")),
            "script_purpose": clean_val(row.get("Script_Purpose")),
            "module": clean_val(row.get("Module")),
            "category": clean_val(row.get("Category")),
            "source": clean_val(row.get("Source")),
            "script_text_sanitized": clean_val(row.get("Script_Text_Sanitized")),
        })
        inputs = row.get("Script_Inputs")
        if inputs:
            placeholders = [p.strip() for p in inputs.split(",") if p.strip()]
            script_inputs_map[sid] = placeholders
    n = batch_upsert(supabase, "scripts_master", records, "script_id")
    print(f"         {n} rows")
    return script_inputs_map


def _seed_script_placeholders(supabase, script_inputs_map, known_placeholders):
    print("  [4/11] script_placeholders")
    records = []
    for sid, phs in script_inputs_map.items():
        for ph in phs:
            if ph in known_placeholders:
                records.append({"script_id": sid, "placeholder": ph})
    n = batch_upsert(supabase, "script_placeholders", records, "script_id,placeholder")
    print(f"         {n} rows")


def _seed_knowledge_articles(supabase, ka_rows):
    print("  [5/11] knowledge_articles")
    records = []
    for row in ka_rows:
        kb_id = clean_val(row.get("KB_Article_ID"))
        if not kb_id:
            continue
        records.append({
            "kb_article_id": kb_id,
            "title": clean_val(row.get("Title")),
            "body": clean_val(row.get("Body")),
            "tags": clean_val(row.get("Tags")),
            "module": clean_val(row.get("Module")),
            "category": clean_val(row.get("Category")),
            "created_at": excel_serial_to_timestamp(row.get("Created_At")),
            "updated_at": excel_serial_to_timestamp(row.get("Updated_At")),
            "status": clean_val(row.get("Status")),
            "source_type": clean_val(row.get("Source_Type")),
        })
    n = batch_upsert(supabase, "knowledge_articles", records, "kb_article_id", batch_size=100)
    print(f"         {n} rows")


def _seed_conversations(supabase, reader):
    print("  [6/11] conversations")
    headers, conv_rows = reader.read_sheet("Conversations")
    validate_columns(headers, ["Ticket_Number"], "Conversations")
    records = []
    for row in conv_rows:
        tn = clean_val(row.get("Ticket_Number"))
        if not tn:
            continue
        records.append({
            "ticket_number": tn,
            "conversation_id": clean_val(row.get("Conversation_ID")),
            "channel": clean_val(row.get("Channel")),
            "conversation_start": excel_serial_to_timestamp(row.get("Conversation_Start")),
            "conversation_end": excel_serial_to_timestamp(row.get("Conversation_End")),
            "customer_role": clean_val(row.get("Customer_Role")),
            "agent_name": clean_val(row.get("Agent_Name")),
            "product": clean_val(row.get("Product")),
            "category": clean_val(row.get("Category")),
            "issue_summary": clean_val(row.get("Issue_Summary")),
            "transcript": clean_val(row.get("Transcript")),
            "sentiment": clean_val(row.get("Sentiment")),
            "generation_source_record": clean_val(row.get("Generation_Source_Record")),
        })
    n = batch_upsert(supabase, "conversations", records, "ticket_number", batch_size=50)
    print(f"         {n} rows")


def _seed_tickets(supabase, ticket_rows):
    print("  [7/11] tickets")
    records = []
    for row in ticket_rows:
        tn = clean_val(row.get("Ticket_Number"))
        if not tn:
            continue
        tier_raw = row.get("Tier")
        tier_val = None
        if tier_raw:
            try:
                tier_val = str(int(float(tier_raw)))
            except (ValueError, TypeError):
                tier_val = clean_val(tier_raw)
        records.append({
            "ticket_number": tn,
            "created_at": excel_serial_to_timestamp(row.get("Created_At")),
            "closed_at": excel_serial_to_timestamp(row.get("Closed_At")),
            "status": clean_val(row.get("Status")),
            "priority": clean_val(row.get("Priority")),
            "tier": tier_val,
            "module": clean_val(row.get("Module")),
            "case_type": clean_val(row.get("Case_Type")),
            "subject": clean_val(row.get("Subject")),
            "description": clean_val(row.get("Description")),
            "resolution": clean_val(row.get("Resolution")),
            "root_cause": clean_val(row.get("Root_Cause")),
            "tags": clean_val(row.get("Tags")),
            "kb_article_id": clean_val(row.get("KB_Article_ID")),
            "script_id": clean_val(row.get("Script_ID")),
            "generated_kb_article_id": clean_val(row.get("Generated_KB_Article_ID")),
        })
    n = batch_upsert(supabase, "tickets", records, "ticket_number", batch_size=50)
    print(f"         {n} rows")


def _seed_kb_lineage(supabase, reader):
    print("  [8/11] kb_lineage")
    headers, kbl_rows = reader.read_sheet("KB_Lineage")
    validate_columns(headers, ["KB_Article_ID", "Source_Type", "Source_ID"], "KB_Lineage")
    records = []
    for row in kbl_rows:
        kb_id = clean_val(row.get("KB_Article_ID"))
        if not kb_id:
            continue
        records.append({
            "kb_article_id": kb_id,
            "source_type": clean_val(row.get("Source_Type")),
            "source_id": clean_val(row.get("Source_ID")),
            "relationship": clean_val(row.get("Relationship")),
            "evidence_snippet": clean_val(row.get("Evidence_Snippet")),
            "event_timestamp": excel_serial_to_timestamp(row.get("Event_Timestamp")),
        })
    n = batch_upsert(supabase, "kb_lineage", records, "kb_article_id,source_type,source_id")
    print(f"         {n} rows")


def _seed_learning_events(supabase, reader):
    print("  [9/11] learning_events")
    headers, le_rows = reader.read_sheet("Learning_Events")
    validate_columns(headers, ["Event_ID"], "Learning_Events")
    records = []
    for row in le_rows:
        eid = clean_val(row.get("Event_ID"))
        if not eid:
            continue
        event_type = clean_val(row.get("Event_Type"))
        if not event_type and row.get("Proposed_KB_Article_ID"):
            event_type = "GAP"
        records.append({
            "event_id": eid,
            "trigger_ticket_number": clean_val(row.get("Trigger_Ticket_Number")),
            "detected_gap": clean_val(row.get("Detected_Gap")),
            "event_type": event_type,
            "proposed_kb_article_id": clean_val(row.get("Proposed_KB_Article_ID")),
            "flagged_kb_article_id": clean_val(row.get("Flagged_KB_Article_ID")),
            "draft_summary": clean_val(row.get("Draft_Summary")),
            "final_status": clean_val(row.get("Final_Status")),
            "reviewer_role": clean_val(row.get("Reviewer_Role")),
            "event_timestamp": excel_serial_to_timestamp(row.get("Event_Timestamp")),
        })
    n = batch_upsert(supabase, "learning_events", records, "event_id")
    print(f"         {n} rows")


def _seed_questions(supabase, reader):
    print("  [10/11] questions")
    headers, q_rows = reader.read_sheet("Questions")
    validate_columns(headers, ["Question_ID"], "Questions")
    records = []
    for row in q_rows:
        qid = clean_val(row.get("Question_ID"))
        if not qid:
            continue
        records.append({
            "question_id": qid,
            "source": clean_val(row.get("Source")),
            "product": clean_val(row.get("Product")),
            "category": clean_val(row.get("Category")),
            "module": clean_val(row.get("Module")),
            "difficulty": clean_val(row.get("Difficulty")),
            "question_text": clean_val(row.get("Question_Text")),
            "answer_type": clean_val(row.get("Answer_Type")),
            "target_id": clean_val(row.get("Target_ID")),
            "target_title": clean_val(row.get("Target_Title")),
            "generation_source_record": clean_val(row.get("Generation_Source_Record")),
        })
    n = batch_upsert(supabase, "questions", records, "question_id", batch_size=100)
    print(f"         {n} rows")


def _seed_retrieval_corpus(supabase, sm_rows, ka_rows, ticket_rows):
    print("  [11/11] retrieval_corpus")
    records = []

    for row in sm_rows:
        sid = clean_val(row.get("Script_ID"))
        if not sid:
            continue
        purpose = row.get("Script_Purpose") or ""
        script_text = row.get("Script_Text_Sanitized") or ""
        content = (purpose + "\n\n" + script_text).strip()
        records.append({
            "source_type": "SCRIPT",
            "source_id": sid,
            "title": clean_val(row.get("Script_Title")),
            "content": content or None,
            "category": clean_val(row.get("Category")),
            "module": clean_val(row.get("Module")),
            "tags": "",
            "confidence": 1.0,
            "usage_count": 0,
        })

    for row in ka_rows:
        kb_id = clean_val(row.get("KB_Article_ID"))
        if not kb_id:
            continue
        records.append({
            "source_type": "KB",
            "source_id": kb_id,
            "title": clean_val(row.get("Title")),
            "content": clean_val(row.get("Body")),
            "category": clean_val(row.get("Category")),
            "module": clean_val(row.get("Module")),
            "tags": clean_val(row.get("Tags")) or "",
            "confidence": 1.0,
            "usage_count": 0,
        })

    for row in ticket_rows:
        tn = clean_val(row.get("Ticket_Number"))
        resolution = clean_val(row.get("Resolution"))
        if not tn or not resolution:
            continue
        desc = row.get("Description") or ""
        root_cause = row.get("Root_Cause") or ""
        content = "\n\n".join(part for part in [desc, root_cause, resolution] if part)
        records.append({
            "source_type": "TICKET_RESOLUTION",
            "source_id": tn,
            "title": clean_val(row.get("Subject")),
            "content": content or None,
            "category": clean_val(row.get("Category")),
            "module": clean_val(row.get("Module")),
            "tags": clean_val(row.get("Tags")) or "",
            "confidence": 1.0,
            "usage_count": 0,
        })

    n = batch_upsert(supabase, "retrieval_corpus", records, "source_type,source_id", batch_size=50)
    print(f"         {n} rows")


# ---------------------------------------------------------------------------
# Data loading orchestrator
# ---------------------------------------------------------------------------

def load_data(supabase, xlsx_path):
    """Parse Excel and upsert all data in FK-dependency order."""
    print(f"Reading {xlsx_path} ...")

    with XlsxReader(xlsx_path) as reader:
        # Pre-read sheets needed by multiple steps
        sm_headers, sm_rows = reader.read_sheet("Scripts_Master")
        validate_columns(sm_headers, ["Script_ID"], "Scripts_Master")

        ka_headers, ka_rows = reader.read_sheet("Knowledge_Articles")
        validate_columns(ka_headers, ["KB_Article_ID"], "Knowledge_Articles")

        tk_headers, ticket_rows = reader.read_sheet("Tickets")
        validate_columns(tk_headers, ["Ticket_Number"], "Tickets")

        _seed_categories(supabase, reader, ticket_rows)
        known_placeholders = _seed_placeholder_dictionary(supabase, reader)
        script_inputs_map = _seed_scripts_master(supabase, sm_rows)
        _seed_script_placeholders(supabase, script_inputs_map, known_placeholders)
        _seed_knowledge_articles(supabase, ka_rows)
        _seed_conversations(supabase, reader)
        _seed_tickets(supabase, ticket_rows)
        _seed_kb_lineage(supabase, reader)
        _seed_learning_events(supabase, reader)
        _seed_questions(supabase, reader)
        _seed_retrieval_corpus(supabase, sm_rows, ka_rows, ticket_rows)

    print("\nData loading complete!")


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


def _embed_batch_with_retry(embedder, texts):
    """Call embedder.embed_batch for a single batch, with exponential backoff."""
    for attempt in range(MAX_RETRIES):
        try:
            return embedder.embed_batch(texts, batch_size=len(texts))
        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            print(f"\n    Retry {attempt + 1}/{MAX_RETRIES} after error: {exc}")
            print(f"    Waiting {delay:.0f}s...", flush=True)
            time.sleep(delay)


def generate_embeddings(supabase):
    """Fetch retrieval_corpus rows with NULL embeddings and batch-embed them."""
    from app.rag.core.embedder import Embedder

    print("\nFetching retrieval_corpus rows with NULL embeddings...")

    # Paginate through all rows with NULL embeddings
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        resp = (
            supabase.table("retrieval_corpus")
            .select("source_type,source_id,title,content")
            .is_("embedding", "null")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        page = resp.data
        if not page:
            break
        all_rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    if not all_rows:
        print("No rows need embedding. Done!")
        return

    print(f"Found {len(all_rows)} rows to embed.")

    # Build texts: title + content
    texts = []
    for row in all_rows:
        title = row.get("title") or ""
        content = row.get("content") or ""
        text = (title + "\n\n" + content).strip()
        texts.append(text if text else "empty")

    # Embed in batches, writing to DB after each batch for crash resilience
    embedder = Embedder()
    batch_size = 100
    total_batches = (len(texts) + batch_size - 1) // batch_size
    print(f"Embedding {len(texts)} texts in {total_batches} batches of {batch_size}...")

    t0 = time.time()
    total_written = 0
    for i in range(0, len(texts), batch_size):
        batch_num = i // batch_size + 1
        batch_texts = texts[i : i + batch_size]
        batch_rows = all_rows[i : i + batch_size]
        print(f"  Batch {batch_num}/{total_batches} ({len(batch_texts)} texts)...", end=" ", flush=True)
        bt = time.time()

        embeddings = _embed_batch_with_retry(embedder, batch_texts)

        # Write this batch's embeddings to DB immediately via upsert
        upsert_records = []
        for row, emb in zip(batch_rows, embeddings):
            if emb is None:
                continue
            upsert_records.append({
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "embedding": emb,
            })
        if upsert_records:
            try:
                supabase.table("retrieval_corpus").upsert(
                    upsert_records, on_conflict="source_type,source_id"
                ).execute()
            except Exception as exc:
                print(f"\n    ERROR writing batch {batch_num} to DB: {exc}", file=sys.stderr)
                raise

        total_written += len(upsert_records)
        print(f"{time.time() - bt:.1f}s")

    elapsed = time.time() - t0
    print(f"\nEmbedding complete: {total_written} rows in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed Supabase database from Excel")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Load data only, skip embedding generation",
    )
    mode.add_argument(
        "--embeddings-only",
        action="store_true",
        help="Skip data loading, only generate embeddings for NULL rows",
    )
    parser.add_argument(
        "--xlsx",
        default="SupportMind__Final_Data.xlsx",
        help="Path to Excel file (default: SupportMind__Final_Data.xlsx)",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    # Import supabase client (requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in .env)
    from app.rag.core.supabase_client import get_supabase_client
    from app.rag.core.config import settings

    supabase = get_supabase_client()

    # Safety confirmation
    if not args.yes:
        url = settings.supabase_url
        action = "data + embeddings"
        if args.skip_embeddings:
            action = "data only"
        elif args.embeddings_only:
            action = "embeddings only"
        print(f"Target:  {url}")
        print(f"Action:  {action}")
        answer = input("Proceed? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    print("Connected to Supabase.\n")

    if not args.embeddings_only:
        xlsx_path = args.xlsx
        if not os.path.exists(xlsx_path):
            print(f"ERROR: Excel file not found: {xlsx_path}", file=sys.stderr)
            sys.exit(1)
        load_data(supabase, xlsx_path)

    if not args.skip_embeddings:
        generate_embeddings(supabase)

    print("\nAll done!")


if __name__ == "__main__":
    main()
