"""Integration tests for FastAPI endpoints."""

import io

from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health check status."""

    def test_root_health(self, client: TestClient) -> None:
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_v1_health(self, client: TestClient) -> None:
        res = client.get("/api/v1/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"


class TestCaseEndpoints:
    """Test case creation, retrieval, and listing."""

    def test_create_case_success(self, client: TestClient) -> None:
        payload = {
            "title": "Corporate Loan Verification",
            "description": "Suspected altered income statements",
            "created_by": "underwriter_42",
            "metadata": {"loan_id": "LN-9876"},
        }
        res = client.post("/api/v1/cases", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["title"] == payload["title"]
        assert data["status"] == "DRAFT"
        assert data["case_reference"].startswith("CASE-")
        assert "id" in data

    def test_create_case_invalid_payload(self, client: TestClient) -> None:
        # Empty title violates min_length=1
        res = client.post("/api/v1/cases", json={"title": ""})
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"

    def test_get_case_by_id(self, client: TestClient) -> None:
        create_res = client.post("/api/v1/cases", json={"title": "Single Case Test"})
        case_id = create_res.json()["id"]

        get_res = client.get(f"/api/v1/cases/{case_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == case_id

    def test_get_nonexistent_case(self, client: TestClient) -> None:
        res = client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "ENTITY_NOT_FOUND"

    def test_list_cases_pagination(self, client: TestClient) -> None:
        for i in range(3):
            client.post("/api/v1/cases", json={"title": f"Batch Case {i}"})

        res = client.get("/api/v1/cases?skip=0&limit=2")
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 3


class TestDocumentEndpoints:
    """Test document upload, validation, duplicate handling, and query."""

    def test_upload_pdf_success(self, client: TestClient) -> None:
        case_res = client.post("/api/v1/cases", json={"title": "Document Test Case"})
        case_id = case_res.json()["id"]

        synthetic_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        files = {"file": ("bank_statement.pdf", io.BytesIO(synthetic_pdf), "application/pdf")}

        res = client.post(f"/api/v1/cases/{case_id}/documents", files=files)
        assert res.status_code == 201
        doc = res.json()
        assert doc["original_filename"] == "bank_statement.pdf"
        assert doc["media_type"] == "application/pdf"
        assert len(doc["sha256"]) == 64
        assert doc["file_size_bytes"] == len(synthetic_pdf)

        # Verify get_document endpoint
        get_res = client.get(f"/api/v1/cases/{case_id}/documents/{doc['id']}")
        assert get_res.status_code == 200
        get_doc = get_res.json()
        assert get_doc["id"] == doc["id"]
        assert get_doc["sha256"] == doc["sha256"]

        # Verify download_document endpoint
        dl_res = client.get(f"/api/v1/cases/{case_id}/documents/{doc['id']}/download")
        assert dl_res.status_code == 200
        assert dl_res.content == synthetic_pdf
        assert "bank_statement.pdf" in dl_res.headers.get("content-disposition", "")

        # Verify artifact retrieval (missing artifact returns 404)
        art_res = client.get(
            f"/api/v1/cases/{case_id}/documents/{doc['id']}/artifacts/run-123/nonexistent.png"
        )
        assert art_res.status_code == 404

    def test_magic_byte_mismatch_rejected(self, client: TestClient) -> None:
        case_res = client.post("/api/v1/cases", json={"title": "Tampered Upload Case"})
        case_id = case_res.json()["id"]

        # Claiming PDF but uploading random bytes
        fake_pdf = b"NOT_A_PDF_HEADER_BYTES"
        files = {"file": ("malicious.pdf", io.BytesIO(fake_pdf), "application/pdf")}

        res = client.post(f"/api/v1/cases/{case_id}/documents", files=files)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "SECURITY_VIOLATION"
        assert "signature does not match" in res.json()["error"]["message"]

    def test_unsupported_file_extension_rejected(self, client: TestClient) -> None:
        case_res = client.post("/api/v1/cases", json={"title": "Extension Test Case"})
        case_id = case_res.json()["id"]

        files = {"file": ("executable.exe", io.BytesIO(b"MZ1234"), "application/octet-stream")}

        res = client.post(f"/api/v1/cases/{case_id}/documents", files=files)
        assert res.status_code == 400
        assert res.json()["error"]["code"] == "SECURITY_VIOLATION"

    def test_duplicate_document_not_silently_discarded(self, client: TestClient) -> None:
        case_res = client.post("/api/v1/cases", json={"title": "Duplicate Upload Case"})
        case_id = case_res.json()["id"]

        synthetic_pdf = b"%PDF-1.4\nDuplicate test bytes\n%%EOF"

        # First upload
        files1 = {"file": ("doc_first.pdf", io.BytesIO(synthetic_pdf), "application/pdf")}
        res1 = client.post(f"/api/v1/cases/{case_id}/documents", files=files1)
        assert res1.status_code == 201
        doc1_id = res1.json()["id"]

        # Second upload with identical bytes
        files2 = {"file": ("doc_second.pdf", io.BytesIO(synthetic_pdf), "application/pdf")}
        res2 = client.post(f"/api/v1/cases/{case_id}/documents", files=files2)
        assert res2.status_code == 201
        doc2 = res2.json()

        assert doc2["id"] != doc1_id
        assert doc2["sha256"] == res1.json()["sha256"]
        assert doc2["metadata"]["duplicate_of_document_id"] == doc1_id


class TestFindingsAndAuditEndpoints:
    """Test findings and audit endpoints."""

    def test_get_findings_empty_collection(self, client: TestClient) -> None:
        case_res = client.post("/api/v1/cases", json={"title": "Findings Case"})
        case_id = case_res.json()["id"]

        res = client.get(f"/api/v1/cases/{case_id}/findings")
        assert res.status_code == 200
        data = res.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_get_audit_events_and_verify_chain(self, client: TestClient) -> None:
        case_res = client.post("/api/v1/cases", json={"title": "Audit Case"})
        case_id = case_res.json()["id"]

        # Upload a document to trigger audit events
        synthetic_pdf = b"%PDF-1.4\nAudit test document\n%%EOF"
        files = {"file": ("evidence.pdf", io.BytesIO(synthetic_pdf), "application/pdf")}
        client.post(f"/api/v1/cases/{case_id}/documents", files=files)

        # List audit events
        events_res = client.get(f"/api/v1/cases/{case_id}/audit-events")
        assert events_res.status_code == 200
        events_data = events_res.json()
        assert events_data["total"] >= 3  # CASE_CREATED, DOCUMENT_INGESTED, FILE_HASH_REGISTERED

        # Verify cryptographic chain
        verify_res = client.get(f"/api/v1/cases/{case_id}/audit-events/verify")
        assert verify_res.status_code == 200
        verify_data = verify_res.json()
        assert verify_data["chain_valid"] is True
        assert verify_data["error_message"] is None
