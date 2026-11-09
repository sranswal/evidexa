"""Entity normalization modules for deterministic cross-document entity resolution."""

from document_intelligence.modules.entity_resolution.normalizers.bank_account import (
    normalize_bank_account_reference,
)
from document_intelligence.modules.entity_resolution.normalizers.currency_amount import (
    normalize_currency_amount,
)
from document_intelligence.modules.entity_resolution.normalizers.invoice_reference import (
    normalize_invoice_reference,
)
from document_intelligence.modules.entity_resolution.normalizers.organization import (
    normalize_organization_name,
)
from document_intelligence.modules.entity_resolution.normalizers.person import (
    normalize_person_name,
)
from document_intelligence.modules.entity_resolution.normalizers.tax_identifier import (
    normalize_tax_identifier,
)

__all__ = [
    "normalize_organization_name",
    "normalize_person_name",
    "normalize_tax_identifier",
    "normalize_invoice_reference",
    "normalize_bank_account_reference",
    "normalize_currency_amount",
]
