/**
 * Financial and Numeric Formatting Utilities for Nodexa
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

/**
 * Formats a generic integer/number with thousands separators.
 * e.g. 20723223 -> "20,723,223"
 */
export function formatNumber(
  val: number | null | undefined,
  fallback: string = "—"
): string {
  if (val === null || val === undefined || typeof val !== "number" || isNaN(val) || !isFinite(val)) {
    return fallback;
  }
  return val.toLocaleString("en-US");
}

/**
 * Formats a signed number with explicit plus/minus and thousands separators.
 * e.g. -20723223 -> "-20,723,223", 5 -> "+5", 0 -> "0"
 */
export function formatSignedNumber(
  val: number | null | undefined,
  fallback: string = "—"
): string {
  if (val === null || val === undefined || typeof val !== "number" || isNaN(val) || !isFinite(val)) {
    return fallback;
  }
  const formatted = Math.abs(val).toLocaleString("en-US");
  if (val > 0) return `+${formatted}`;
  if (val < 0) return `-${formatted}`;
  return "0";
}

/**
 * Converts screaming snake-case enums to clean, human-readable sentence case.
 * e.g. "HIGH_RISK_INCIDENCE" -> "High-risk incidence"
 */
export function toSentenceCase(text: string | null | undefined): string {
  if (!text) return "";
  const cleaned = text.replace(/_/g, " ").trim().toLowerCase();
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}
