"""Invoice extraction schema definition (Version 1.0.0)."""

from document_intelligence.domain.enums import DocumentClass, FieldDataType
from document_intelligence.domain.models.extraction import (
    ExtractionSchema,
    FieldDefinition,
)

INVOICE_SCHEMA_V1 = ExtractionSchema(
    schema_id="invoice_v1",
    document_class=DocumentClass.INVOICE,
    version="1.0.0",
    description="Standard commercial and tax invoice structured field extraction schema.",
    fields=[
        FieldDefinition(
            field_key="invoice_number",
            label="Invoice Number",
            data_type=FieldDataType.STRING,
            is_required=True,
            description="Unique invoice reference identifier.",
            validation_rules=["alphanumeric_identifier"],
        ),
        FieldDefinition(
            field_key="invoice_date",
            label="Invoice Date",
            data_type=FieldDataType.DATE,
            is_required=True,
            description="Issue date of the invoice (normalized to ISO 8601 YYYY-MM-DD).",
            validation_rules=["iso_date"],
        ),
        FieldDefinition(
            field_key="due_date",
            label="Due Date",
            data_type=FieldDataType.DATE,
            is_required=False,
            description="Payment due date (normalized to ISO 8601 YYYY-MM-DD).",
            validation_rules=["iso_date"],
        ),
        FieldDefinition(
            field_key="supplier_name",
            label="Supplier / Vendor Name",
            data_type=FieldDataType.STRING,
            is_required=True,
            description="Legal or commercial name of the issuing vendor.",
            validation_rules=["non_empty_string"],
        ),
        FieldDefinition(
            field_key="supplier_tax_id",
            label="Supplier Tax ID",
            data_type=FieldDataType.STRING,
            is_required=False,
            description="Tax identifier of vendor (e.g. GSTIN, VAT, TIN, EIN).",
            validation_rules=["tax_identifier"],
        ),
        FieldDefinition(
            field_key="buyer_name",
            label="Buyer / Client Name",
            data_type=FieldDataType.STRING,
            is_required=False,
            description="Name of the customer, client, or billed entity.",
            validation_rules=["non_empty_string"],
        ),
        FieldDefinition(
            field_key="buyer_tax_id",
            label="Buyer Tax ID",
            data_type=FieldDataType.STRING,
            is_required=False,
            description="Tax identifier of buyer (e.g. GSTIN, VAT).",
            validation_rules=["tax_identifier"],
        ),
        FieldDefinition(
            field_key="subtotal",
            label="Subtotal Amount",
            data_type=FieldDataType.DECIMAL,
            is_required=False,
            description="Taxable net subtotal amount before taxes and shipping.",
            validation_rules=["decimal_amount"],
        ),
        FieldDefinition(
            field_key="tax_amount",
            label="Tax Amount",
            data_type=FieldDataType.DECIMAL,
            is_required=False,
            description="Total aggregated tax amount (GST, VAT, Sales Tax).",
            validation_rules=["decimal_amount"],
        ),
        FieldDefinition(
            field_key="total_amount",
            label="Total Amount Due",
            data_type=FieldDataType.DECIMAL,
            is_required=True,
            description="Final payable gross total amount.",
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
    ],
)
