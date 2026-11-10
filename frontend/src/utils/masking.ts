/**
 * Utility for masking sensitive identifiers in the UI.
 * Masks account numbers, tax IDs, PANs, and Aadhaar identifiers
 * while preserving the last 4 characters for verification.
 */

const SENSITIVE_FIELD_KEYS = new Set([
  'account_number',
  'account_number_masked',
  'bank_account_number',
  'pan_number',
  'tax_id',
  'aadhaar_number',
  'ssn',
  'credit_card_number',
  'identity_number',
  'iban',
]);

export function isSensitiveField(fieldKey: string, dataType?: string): boolean {
  const normalizedKey = fieldKey.toLowerCase().replace(/[^a-z0-9_]/g, '_');
  if (SENSITIVE_FIELD_KEYS.has(normalizedKey)) return true;
  if (
    dataType &&
    ['TAX_ID', 'ACCOUNT_NUMBER', 'IDENTITY', 'PAN', 'MASKED_STRING'].includes(
      dataType.toUpperCase()
    )
  ) {
    return true;
  }
  return false;
}

export function maskSensitiveValue(value: unknown): string {
  if (value === null || value === undefined) return '-';
  const str = String(value).trim();
  if (!str) return '-';

  // If length is 4 or less, mask completely
  if (str.length <= 4) {
    return '•'.repeat(str.length);
  }

  const visibleLength = 4;
  const maskedLength = Math.max(0, str.length - visibleLength);
  const visible = str.slice(-visibleLength);

  // Group masked dots in blocks of 4 for readability
  const dots = '•'.repeat(maskedLength);
  return `${dots} ${visible}`;
}

