"""Receipt extraction schema definition (Version 1.0.0)."""

from document_intelligence.domain.enums import DocumentClass, FieldDataType
from document_intelligence.domain.models.extraction import (
    ExtractionSchema,
    FieldDefinition,
)

RECEIPT_SCHEMA_V1 = ExtractionSchema(
    schema_id="receipt_v1",
    document_class=DocumentClass.RECEIPT,
    version="1.0.0",
    description="Point-of-sale and retail payment receipt structured field extraction schema.",
    fields=[
        FieldDefinition(
            field_key="merchant_name",
            label="Merchant Name",
            data_type=FieldDataType.STRING,
            is_required=True,
            description="Trading name of the retail store or merchant.",
            validation_rules=["non_empty_string"],
        ),
        FieldDefinition(
            field_key="transaction_date",
            label="Transaction Date",
            data_type=FieldDataType.DATE,
            is_required=True,
            description="Date when transaction occurred (normalized to ISO 8601 YYYY-MM-DD).",
            validation_rules=["iso_date"],
        ),
        FieldDefinition(
            field_key="receipt_number",
            label="Receipt / Transaction Number",
            data_type=FieldDataType.STRING,
            is_required=False,
            description="POS slip, ticket, or transaction reference number.",
            validation_rules=["alphanumeric_identifier"],
        ),
        FieldDefinition(
            field_key="subtotal",
            label="Subtotal Amount",
            data_type=FieldDataType.DECIMAL,
            is_required=False,
            description="Net item subtotal prior to taxes.",
            validation_rules=["decimal_amount"],
        ),
        FieldDefinition(
            field_key="tax_amount",
            label="Tax Amount",
            data_type=FieldDataType.DECIMAL,
            is_required=False,
            description="Sales tax or VAT charged.",
            validation_rules=["decimal_amount"],
        ),
        FieldDefinition(
            field_key="total_amount",
            label="Total Amount Paid",
            data_type=FieldDataType.DECIMAL,
            is_required=True,
            description="Total charged or tendered amount.",
            validation_rules=["decimal_amount", "arithmetic_check"],
        ),
        FieldDefinition(
            field_key="currency",
            label="Currency Code",
            data_type=FieldDataType.CURRENCY,
            is_required=False,
            description="Normalized ISO currency code (USD, EUR, GBP, INR, etc.).",
            validation_rules=["iso_currency_code"],
        ),
        FieldDefinition(
            field_key="payment_method",
            label="Payment Method",
            data_type=FieldDataType.STRING,
            is_required=False,
            description="Payment tender type (CASH, VISA, MASTERCARD, DEBIT, CARD).",
            validation_rules=["payment_tender_type"],
        ),
    ],
)
