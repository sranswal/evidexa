"""Integration test for Alembic 007_cross_document_consistency migration."""

import sqlite3
from pathlib import Path

from alembic.config import Config

from alembic import command


def test_alembic_007_migration_lifecycle(tmp_path: Path) -> None:
    """Verify clean upgrade to 007, schema creation, downgrade to 006, and re-upgrade."""
    db_file = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to head (007)
    command.upgrade(alembic_cfg, "head")

    # Verify tables and columns in sqlite
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "consistency_findings" in tables
    assert "consistency_reviews" in tables

    # Verify columns in consistency_findings
    cursor.execute("PRAGMA table_info(consistency_findings)")
    finding_cols = {row[1] for row in cursor.fetchall()}
    expected_finding_cols = {
        "id",
        "case_id",
        "analysis_run_id",
        "rule_id",
        "rule_version",
        "category",
        "title",
        "explanation",
        "severity",
        "outcome",
        "score",
        "score_semantics",
        "affected_document_ids",
        "compared_fields",
        "original_values",
        "normalized_values",
        "supporting_evidence_ids",
        "contradicting_evidence_ids",
        "locations_payload",
        "detection_method",
        "rule_parameters",
        "limitations",
        "status",
        "review_status",
        "is_human_reviewed",
        "comparisons_payload",
        "created_at",
        "updated_at",
    }
    assert expected_finding_cols.issubset(finding_cols)

    # Verify columns in consistency_reviews
    cursor.execute("PRAGMA table_info(consistency_reviews)")
    review_cols = {row[1] for row in cursor.fetchall()}
    expected_review_cols = {
        "id",
        "case_id",
        "finding_id",
        "decision",
        "reviewer_id",
        "reason",
        "reviewed_at",
        "previous_status",
        "new_status",
    }
    assert expected_review_cols.issubset(review_cols)

    conn.close()

    # 2. Downgrade to 006
    command.downgrade(alembic_cfg, "006_relationship_semantics")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables_downgraded = {row[0] for row in cursor.fetchall()}
    assert "consistency_findings" not in tables_downgraded
    assert "consistency_reviews" not in tables_downgraded
    conn.close()

    # 3. Re-upgrade to head
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables_reupgraded = {row[0] for row in cursor.fetchall()}
    assert "consistency_findings" in tables_reupgraded
    assert "consistency_reviews" in tables_reupgraded
    conn.close()
