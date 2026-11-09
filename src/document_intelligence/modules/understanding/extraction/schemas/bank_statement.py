"""Bank statement extraction schema definition (Version 1.0.0)."""

from document_intelligence.domain.enums import DocumentClass, FieldDataType
from document_intelligence.domain.models.extraction import (
    ExtractionSchema,
    FieldDefinition,
)

BANK_STATEMENT_SCHEMA_V1 = ExtractionSchema(
    schema_id="bank_statement_v1",
    document_class=DocumentClass.BANK_STATEMENT,
    version="1.0.0",
    description="Financial bank account statement header and summary extraction schema.",
    fields=[
        FieldDefinition(
            field_key="account_holder",
            label="Account Holder Name",
            data_type=FieldDataType.STRING,
            is_required=True,
            description="Primary named individual or corporate account owner.",
            validation_rules=["non_empty_string"],
        ),
        FieldDefinition(
            field_key="bank_name",
            label="Bank / Financial Institution",
            data_type=FieldDataType.STRING,
            is_required=True,
            description="Issuing financial institution or bank entity name.",
            validation_rules=["non_empty_string"],
        ),
        FieldDefinition(
            field_key="account_number_masked",
            label="Masked Account Number",
            data_type=FieldDataType.MASKED_STRING,
            is_required=True,
            description="Sanitized and masked account number (e.g. '****1234'). Full number is never exposed.",
            validation_rules=["masked_account_format"],
        ),
        FieldDefinition(
            field_key="statement_period_start",
            label="Statement Period Start",
            data_type=FieldDataType.DATE,
            is_required=False,
            description="Start date of billing/reporting cycle (ISO 8601 YYYY-MM-DD).",
            validation_rules=["iso_date"],
        ),
        FieldDefinition(
            field_key="statement_period_end",
            label="Statement Period End",
            data_type=FieldDataType.DATE,
            is_required=False,
            description="Closing date of billing/reporting cycle (ISO 8601 YYYY-MM-DD).",
            validation_rules=["iso_date"],
        ),
        FieldDefinition(
            field_key="opening_balance",
            label="Opening Balance",
            data_type=FieldDataType.DECIMAL,
            is_required=False,
            description="Account balance at start of statement cycle.",
            validation_rules=["decimal_amount"],
        ),
        FieldDefinition(
            field_key="closing_balance",
            label="Closing Balance",
            data_type=FieldDataType.DECIMAL,
            is_required=True,
            description="Final available ledger balance at close of cycle.",
            validation_rules=["decimal_amount"],
        ),
        FieldDefinition(
            field_key="currency",
            label="Currency Code",
            data_type=FieldDataType.CURRENCY,
            is_required=False,
            description="Normalized ISO currency code (USD, EUR, GBP, INR, etc.).",
            validation_rules=["iso_currency_code"],
        ),
    ],
)
