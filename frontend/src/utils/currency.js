// Exchange rates relative to USD (updated April 2026)
const RATES = {
  USD: 1,
  INR: 83.5,
};

const SYMBOLS = {
  USD: '$',
  INR: '₹',
};

const LOCALES = {
  USD: 'en-US',
  INR: 'en-IN',
};

/**
 * Format a USD-denominated amount into the user's preferred currency.
 * All amounts stored in the DB are in USD.
 *
 * @param {number|null|undefined} usdAmount
 * @param {'USD'|'INR'} currency
 * @returns {string}
 */
export function formatCurrency(usdAmount, currency = 'USD') {
  if (usdAmount == null) return '—';
  const code = RATES[currency] ? currency : 'USD';
  const converted = Number(usdAmount) * RATES[code];
  const locale = LOCALES[code];
  const symbol = SYMBOLS[code];

  // Use compact notation for large INR values to keep UI readable
  if (code === 'INR' && converted >= 1_00_000) {
    if (converted >= 1_00_00_000) {
      return `${symbol}${(converted / 1_00_00_000).toFixed(2)} Cr`;
    }
    if (converted >= 1_00_000) {
      return `${symbol}${(converted / 1_00_000).toFixed(2)} L`;
    }
  }

  return `${symbol}${converted.toLocaleString(locale, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

export const CURRENCY_OPTIONS = [
  { value: 'USD', label: 'USD — US Dollar ($)' },
  { value: 'INR', label: 'INR — Indian Rupee (₹)' },
];
