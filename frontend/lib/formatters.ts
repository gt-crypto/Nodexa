/**
 * Financial Formatting Utility for Nodal Sentinel
 *
 * Enforces integer minor-unit (paise) convention for financial precision.
 * Distinguishes between:
 * - Valid numeric value: formatted INR currency (e.g. ₹12,500.00)
 * - Actual zero (0): ₹0.00 (when zero is semantically meaningful)
 * - null / undefined / NaN / Infinity: "N/A" (metric has not yet been measured or is unavailable)
 *
 * Prevents technical implementation values ("null", "undefined", "NaN")
 * from ever leaking into user-facing financial interfaces.
 */
export function formatPaiseOrUnavailable(
  paise: number | null | undefined,
  unavailableLabel: string = "N/A"
): string {
  if (paise === null || paise === undefined) {
    return unavailableLabel;
  }
  if (typeof paise !== "number" || isNaN(paise) || !isFinite(paise)) {
    return unavailableLabel;
  }
  const rupees = paise / 100.0;
  return `₹${rupees.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
