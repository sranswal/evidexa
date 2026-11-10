"""Integration test for Alembic 008_evidence_dossier migration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic.config import Config

from alembic import command


def test_alembic_008_migration_lifecycle(tmp_path: Path) -> None:
    """Verify clean upgrade to 008, schema updates, downgrade to 007, and re-upgrade."""
    db_file = tmp_path / "test_migration_008.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to head (008)
    command.upgrade(alembic_cfg, "head")

    # Verify tables and columns in sqlite
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "aggregated_finding_reviews" in tables
    assert "investigation_dossiers" in tables

    # Verify columns in investigation_dossiers
    cursor.execute("PRAGMA table_info(investigation_dossiers)")
    dossier_cols = {row[1] for row in cursor.fetchall()}
    expected_dossier_cols = {
        "id",
        "case_id",
        "title",
        "scope_and_purpose",
        "version",
        "status",
        "executive_summary",
        "document_summaries",
        "finding_ids",
        "evidence_ids",
        "review_decisions",
        "limitations",
        "unresolved_questions",
        "sections",
        "content_hash",
        "dossier_payload",
        "created_at",
        "created_by",
        "finalized_at",
    }
    assert expected_dossier_cols.issubset(dossier_cols)

    # Verify columns in aggregated_finding_reviews
    cursor.execute("PRAGMA table_info(aggregated_finding_reviews)")
    review_cols = {row[1] for row in cursor.fetchall()}
    expected_review_cols = {
        "id",
        "case_id",
        "finding_id",
        "action",
        "reviewer_id",
        "comment",
        "reviewed_at",
        "previous_status",
        "new_status",
    }
    assert expected_review_cols.issubset(review_cols)

    conn.close()

    # 2. Downgrade to 007
    command.downgrade(alembic_cfg, "007_cross_document_consistency")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables_downgraded = {row[0] for row in cursor.fetchall()}
    assert "aggregated_finding_reviews" not in tables_downgraded
    conn.close()

    # 3. Re-upgrade to head
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables_reupgraded = {row[0] for row in cursor.fetchall()}
    assert "aggregated_finding_reviews" in tables_reupgraded
    conn.close()
