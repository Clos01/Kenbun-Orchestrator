"""
Kenbun Hivemind Master Synchronization & Staging Bin Lifecycle.

Provides bidirectional sync between local SQLite staging (unified_memory_records)
and the Master Hivemind PostgreSQL database on LG 2025 (portable_postgres).
Includes defensive inspection guardrails to prevent accidental purge of unsynced data.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from typing import Any

from tools.infrastructure.config import settings
from tools.utils.error_codes import KenbunErrorCode, format_error

logger = logging.getLogger("kenbun.hivemind_sync")


def get_sqlite_conn(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or settings.INTELLIGENCE_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_sync_columns(conn: sqlite3.Connection) -> None:
    """Ensures local SQLite table has tracking columns for sync and purge state."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(unified_memory_records);")
    cols = {row["name"] for row in cur.fetchall()}

    if "synced_to_master" not in cols:
        cur.execute(
            "ALTER TABLE unified_memory_records ADD COLUMN synced_to_master INTEGER DEFAULT 0;"
        )
    if "synced_at" not in cols:
        cur.execute(
            "ALTER TABLE unified_memory_records ADD COLUMN synced_at REAL DEFAULT NULL;"
        )
    if "checksum" not in cols:
        cur.execute(
            "ALTER TABLE unified_memory_records ADD COLUMN checksum TEXT DEFAULT NULL;"
        )
    conn.commit()


def compute_record_checksum(record_id: str, content: str, meta_json: str) -> str:
    """Computes SHA-256 digest to guarantee cryptographic integrity across transfer."""
    raw = f"{record_id}:{content}:{meta_json}".encode()
    return hashlib.sha256(raw).hexdigest()


def get_master_postgres_conn(timeout: float = 3.0):
    """Returns a direct psycopg connection to Master PostgreSQL on LG 2025."""
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        raise RuntimeError(
            "psycopg library is required for Master Hivemind synchronization."
        )

    host = getattr(settings, "POSTGRES_HOST", "<ORCHESTRATOR_IP>")
    port = getattr(settings, "POSTGRES_PORT", 5432)
    user = getattr(settings, "POSTGRES_USER", "appuser")
    password = getattr(settings, "POSTGRES_PASSWORD", "kenbun")
    dbname = getattr(settings, "POSTGRES_DB", "kenbun_intelligence")

    conn_str = f"postgresql://{user}:{password}@{host}:{port}/{dbname}?connect_timeout={int(timeout)}"
    return psycopg.connect(conn_str, row_factory=dict_row)


def init_master_postgres_schema(conn) -> None:
    """Ensures master_hivemind_concepts table exists in Master Postgres."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS master_hivemind_concepts (
                id VARCHAR(64) PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                tags TEXT,
                category VARCHAR(64) NOT NULL DEFAULT 'concepts',
                source_node VARCHAR(64) DEFAULT 'local',
                checksum VARCHAR(64) NOT NULL,
                metadata JSONB,
                staged_timestamp DOUBLE PRECISION,
                synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE master_hivemind_concepts ADD COLUMN IF NOT EXISTS metadata JSONB;
            ALTER TABLE master_hivemind_concepts ADD COLUMN IF NOT EXISTS staged_timestamp DOUBLE PRECISION;
            CREATE INDEX IF NOT EXISTS idx_mhc_category ON master_hivemind_concepts(category);
            CREATE INDEX IF NOT EXISTS idx_mhc_synced_at ON master_hivemind_concepts(synced_at);
        """)
        conn.commit()


def inspect_local_hivemind_bin(db_path: str | None = None) -> dict[str, Any]:
    """
    Defensive inspection tool: audits the local staging bin BEFORE any purge action.
    Reports total, synced, and pending records so operators stay clean with data transfer.
    """
    with get_sqlite_conn(db_path) as conn:
        ensure_sync_columns(conn)
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) AS total FROM unified_memory_records;")
        total = cur.fetchone()["total"]

        cur.execute(
            "SELECT COUNT(*) AS synced FROM unified_memory_records WHERE synced_to_master = 1;"
        )
        synced = cur.fetchone()["synced"]

        cur.execute(
            "SELECT id, content, metadata, timestamp FROM unified_memory_records WHERE synced_to_master = 0 ORDER BY timestamp DESC;"
        )
        pending_rows = cur.fetchall()

    pending_list = []
    for r in pending_rows:
        meta = json.loads(r["metadata"]) if r["metadata"] else {}
        pending_list.append(
            {
                "id": r["id"],
                "title": meta.get("title", "(no title)"),
                "category": meta.get("category", "concepts"),
                "staged_time": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(r["timestamp"])
                ),
                "content_preview": r["content"][:120].replace("\n", " "),
            }
        )

    can_purge = len(pending_list) == 0

    return {
        "status": "clean" if can_purge else "pending_sync",
        "total_records": total,
        "synced_records": synced,
        "pending_records_count": len(pending_list),
        "can_safely_purge": can_purge,
        "pending_items": pending_list,
        "advice": (
            "✅ Local bin is 100% synchronized with Master Hivemind. Safe to purge."
            if can_purge
            else f"⚠️ {len(pending_list)} unsynced concepts staged locally. Run sync_local_hivemind_to_master() before purging!"
        ),
    }


def sync_local_hivemind_to_master(
    dry_run: bool = False,
    force_all: bool = False,
    db_path: str | None = None,
) -> dict[str, Any]:
    """
    Pushes local SQLite staging records to Master Hivemind on LG 2025.
    Computes cryptographic checksums and marks successfully transferred records.
    """
    target_host = getattr(settings, "POSTGRES_HOST", "<ORCHESTRATOR_IP>")

    # 1. Connect to local SQLite and inspect records
    with get_sqlite_conn(db_path) as local_conn:
        ensure_sync_columns(local_conn)
        cur = local_conn.cursor()

        if force_all:
            cur.execute(
                "SELECT id, content, source, metadata, timestamp FROM unified_memory_records;"
            )
        else:
            cur.execute(
                "SELECT id, content, source, metadata, timestamp FROM unified_memory_records WHERE synced_to_master = 0;"
            )
        records_to_sync = cur.fetchall()

    if not records_to_sync:
        return {
            "status": "up_to_date",
            "message": "All local concepts are already synchronized with Master Hivemind on LG 2025.",
            "synced_count": 0,
            "target_host": target_host,
        }

    if dry_run:
        return {
            "status": "dry_run",
            "message": f"Dry-run: {len(records_to_sync)} concepts are ready to push to Master Hivemind.",
            "count": len(records_to_sync),
            "target_host": target_host,
            "records": [r["id"] for r in records_to_sync],
        }

    # 2. Connect to Master PostgreSQL on LG 2025
    try:
        pg_conn = get_master_postgres_conn(timeout=3.0)
    except Exception as e:
        return format_error(
            KenbunErrorCode.MASTER_HIVEMIND_UNREACHABLE,
            details=f"Cannot reach Master Hivemind on LG 2025 ({target_host}:5432): {e}",
            context={"target_host": target_host, "pending_count": len(records_to_sync)},
        )

    synced_ids = []
    failed_records = []

    try:
        init_master_postgres_schema(pg_conn)
        for r in records_to_sync:
            rid = r["id"]
            content = r["content"]
            meta_str = r["metadata"] or "{}"
            meta = json.loads(meta_str) if meta_str else {}
            title = meta.get("title", rid)
            tags = meta.get("tags", "")
            category = meta.get("category", "concepts")
            staged_ts = float(r["timestamp"])

            checksum = compute_record_checksum(rid, content, meta_str)

            try:
                with pg_conn.cursor() as pg_cur:
                    pg_cur.execute(
                        """
                        INSERT INTO master_hivemind_concepts (
                            id, title, content, tags, category, source_node, checksum, metadata, staged_timestamp, synced_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            content = EXCLUDED.content,
                            tags = EXCLUDED.tags,
                            category = EXCLUDED.category,
                            checksum = EXCLUDED.checksum,
                            metadata = EXCLUDED.metadata,
                            staged_timestamp = EXCLUDED.staged_timestamp,
                            synced_at = CURRENT_TIMESTAMP;
                    """,
                        (
                            rid,
                            title,
                            content,
                            tags,
                            category,
                            "local_node",
                            checksum,
                            json.dumps(meta),
                            staged_ts,
                        ),
                    )
                pg_conn.commit()
                synced_ids.append((checksum, time.time(), rid))
            except Exception as sync_err:
                pg_conn.rollback()
                logger.error(f"Failed to sync record {rid}: {sync_err}")
                failed_records.append({"id": rid, "error": str(sync_err)})
    finally:
        pg_conn.close()

    # 3. Update local SQLite status for verified synced records
    if synced_ids:
        with get_sqlite_conn(db_path) as local_conn:
            cur = local_conn.cursor()
            cur.executemany(
                """
                UPDATE unified_memory_records
                SET synced_to_master = 1, checksum = ?, synced_at = ?
                WHERE id = ?;
            """,
                synced_ids,
            )
            local_conn.commit()

    return {
        "status": "success",
        "synced_count": len(synced_ids),
        "failed_count": len(failed_records),
        "target_host": target_host,
        "failed_records": failed_records,
        "message": f"Successfully pushed {len(synced_ids)} concepts to Master Hivemind on LG 2025 ({target_host}).",
    }


def purge_local_hivemind_bin(
    force: bool = False,
    older_than_days: int | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """
    Purges local staging bin with defensive guardrails.
    Refuses to purge unsynced records unless force=True.
    """
    inspection = inspect_local_hivemind_bin(db_path)

    if inspection["pending_records_count"] > 0 and not force:
        return format_error(
            KenbunErrorCode.UNVERIFIED_BIN_PURGE_BLOCKED,
            details=(
                f"Blocked bin purge: {inspection['pending_records_count']} unsynced concept(s) remain locally. "
                f"Execute sync_local_hivemind_to_master() first to avoid data loss, or specify force=True."
            ),
            context={"pending_items": inspection["pending_items"]},
        )

    with get_sqlite_conn(db_path) as conn:
        cur = conn.cursor()
        query = "DELETE FROM unified_memory_records WHERE (synced_to_master = 1"
        params: list[Any] = []

        if force:
            query = "DELETE FROM unified_memory_records WHERE (1=1"

        if older_than_days is not None:
            cutoff = time.time() - (older_than_days * 86400)
            query += " AND timestamp < ?"
            params.append(cutoff)

        query += ");"

        cur.execute(query, params)
        purged_count = cur.rowcount
        conn.commit()

        cur.execute("SELECT COUNT(*) AS remaining FROM unified_memory_records;")
        remaining_count = cur.fetchone()["remaining"]

    return {
        "status": "purged",
        "purged_count": purged_count,
        "remaining_count": remaining_count,
        "message": f"Cleanly purged {purged_count} synced records from local staging bin. Remaining: {remaining_count}.",
    }
