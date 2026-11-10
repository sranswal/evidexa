import { describe, expect, it } from 'vitest';
import { isSensitiveField, maskSensitiveValue } from '../utils/masking';

describe('Sensitive Value Masking', () => {
  it('identifies sensitive field keys and data types', () => {
    expect(isSensitiveField('account_number')).toBe(true);
    expect(isSensitiveField('bank_account_number')).toBe(true);
    expect(isSensitiveField('pan_number')).toBe(true);
    expect(isSensitiveField('tax_id')).toBe(true);
    expect(isSensitiveField('custom_field', 'TAX_ID')).toBe(true);
    expect(isSensitiveField('custom_field', 'ACCOUNT_NUMBER')).toBe(true);

    expect(isSensitiveField('invoice_total')).toBe(false);
    expect(isSensitiveField('vendor_name')).toBe(false);
    expect(isSensitiveField('issue_date')).toBe(false);
  });

  it('masks values preserving last 4 characters', () => {
    expect(maskSensitiveValue('123456789012')).toBe('•••••••• 9012');
    expect(maskSensitiveValue('ABCDE1234F')).toBe('•••••• 234F');
    expect(maskSensitiveValue('1234')).toBe('••••');
    expect(maskSensitiveValue(null)).toBe('-');
    expect(maskSensitiveValue(undefined)).toBe('-');
  });
});

