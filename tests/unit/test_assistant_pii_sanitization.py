"""Unit tests for sensitive data protection and PII minimization."""

from __future__ import annotations

from document_intelligence.modules.assistant.sanitization import (
    mask_sensitive_value,
    sanitize_data_structure,
    sanitize_text,
)


def test_mask_sensitive_value() -> None:
    assert mask_sensitive_value("123456789012") == "****9012"
    assert mask_sensitive_value("1234 5678 9012") == "****9012"
    assert mask_sensitive_value("123") == "****"
    assert mask_sensitive_value("1234") == "****1234"


def test_sanitize_standard_account_numbers() -> None:
    raw = "Wire transferred funds to account 98765432101234."
    sanitized = sanitize_text(raw)
    assert "98765432101234" not in sanitized
    assert "****1234" in sanitized


def test_sanitize_spaced_and_dashed_account_numbers() -> None:
    raw = "Beneficiary account is 1234-5678-9012-3456 or 9876 5432 1098."
    sanitized = sanitize_text(raw)
    assert "1234-5678-9012-3456" not in sanitized
    assert "9876 5432 1098" not in sanitized
    assert "****3456" in sanitized
    assert "****1098" in sanitized


def test_sanitize_tax_and_identity_identifiers() -> None:
    # Indian PAN: ABCDE1234F
    pan_text = "Vendor Tax ID is ABCDE1234F and customer SSN is 123-45-6789."
    sanitized = sanitize_text(pan_text)
    assert "ABCDE1234F" not in sanitized
    assert "123-45-6789" not in sanitized
    assert "****234F" in sanitized or "****" in sanitized
    assert "****6789" in sanitized


def test_sanitize_ein_and_aadhaar() -> None:
    text = "Company EIN is 12-3456789 and Aadhaar 2345 6789 0123."
    sanitized = sanitize_text(text)
    assert "12-3456789" not in sanitized
    assert "2345 6789 0123" not in sanitized
    assert "****6789" in sanitized
    assert "****0123" in sanitized


def test_sanitize_nested_data_structure() -> None:
    data = {
        "case_id": "case-1",
        "documents": [
            {
                "filename": "invoice.pdf",
                "extracted_fields": {
                    "account": "Account 998877665544",
                    "vendor_pan": "XYZPA9999K",
                },
            }
        ],
        "conversation_context": [{"role": "user", "content": "Please check account 112233445566."}],
    }

    sanitized = sanitize_data_structure(data)

    assert "998877665544" not in str(sanitized)
    assert "XYZPA9999K" not in str(sanitized)
    assert "112233445566" not in str(sanitized)
    assert "****5544" in str(sanitized)
    assert "****5566" in str(sanitized)


def test_sanitize_ocr_split_and_spaced_identifiers() -> None:
    """Verifies OCR-split and irregular spaced account numbers are masked."""
    raw_ocr = "Account Number: 1 2 3 4 5 6 7 8 9 0 1 2 detected on check slip."
    sanitized = sanitize_text(raw_ocr)
    assert "1 2 3 4 5 6 7 8 9 0 1 2" not in sanitized
    assert "****" in sanitized

    spaced_pan = "PAN sequence observed as ABCDE 5678 K on application form."
    sanitized_pan = sanitize_text(spaced_pan)
    assert "ABCDE 5678 K" not in sanitized_pan
    assert "****" in sanitized_pan


def test_sanitize_multiple_identifiers_in_single_string() -> None:
    """Verifies multiple disparate identifiers in one string are all masked."""
    mixed = (
        "Client SSN 987-65-4321 deposited $500 from Account 1122334455667788 "
        "to IBAN GB29XABC10203012345678 with PAN AAAAA1111A."
    )
    sanitized = sanitize_text(mixed)
    assert "987-65-4321" not in sanitized
    assert "1122334455667788" not in sanitized
    assert "GB29XABC10203012345678" not in sanitized
    assert "AAAAA1111A" not in sanitized
    assert "$500" in sanitized  # Legitimate amount must be preserved


def test_pii_false_positive_preservation_of_evidence_identifiers() -> None:
    """Verifies legitimate evidence identifiers (invoice numbers, transaction IDs, dates) are NOT destroyed."""
    evidence_text = (
        "Invoice INV-2026-0042 was issued on 2026-11-10 for total $15,000.00. "
        "Referenced against PO-12345678 and transaction TXN-98765432 on 15/04/2026. "
        "Case file CASE-20261110-042 references DOC-87654321."
    )
    sanitized = sanitize_text(evidence_text)

    # Legitimate identifiers must remain intact
    assert "INV-2026-0042" in sanitized
    assert "2026-11-10" in sanitized
    assert "15/04/2026" in sanitized
    assert "PO-12345678" in sanitized
    assert "TXN-98765432" in sanitized
    assert "CASE-20261110-042" in sanitized
    assert "DOC-87654321" in sanitized
    assert "$15,000.00" in sanitized
