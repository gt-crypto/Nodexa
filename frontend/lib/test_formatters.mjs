/**
 * Regression Test Suite for Financial Formatter (Finding #4)
 * Covers:
 * 1. Valid positive realized savings in paise -> formatted INR
 * 2. Zero realized savings -> ₹0.00
 * 3. Null / unavailable realized savings -> N/A
 * 4. Undefined / missing value -> N/A
 * 5. NaN / Infinity values -> N/A
 * 6. Custom unavailable label support
 */

import { formatPaiseOrUnavailable } from "./formatters.ts";
import assert from "node:assert";

function runTests() {
  console.log("=== RUNNING FINANCIAL FORMATTER REGRESSION TESTS ===");

  // 1. Valid values
  assert.strictEqual(
    formatPaiseOrUnavailable(1250000),
    "₹12,500.00",
    "1,250,000 paise should format to ₹12,500.00"
  );
  assert.strictEqual(
    formatPaiseOrUnavailable(50050),
    "₹500.50",
    "50,050 paise should format to ₹500.50"
  );
  console.log("[PASS] 1. Valid positive realized savings format correctly");

  // 2. Zero realized savings (semantically meaningful zero)
  assert.strictEqual(
    formatPaiseOrUnavailable(0),
    "₹0.00",
    "0 paise should format to ₹0.00"
  );
  console.log("[PASS] 2. Zero realized savings formats to ₹0.00");

  // 3. Null realized savings (unmeasured / unavailable)
  assert.strictEqual(
    formatPaiseOrUnavailable(null),
    "N/A",
    "null realized savings should format to 'N/A'"
  );
  assert.strictEqual(
    formatPaiseOrUnavailable(null, "Not yet measured"),
    "Not yet measured",
    "null with custom label should format to custom label"
  );
  console.log("[PASS] 3. Null realized savings formats to N/A without leaking 'null'");

  // 4. Undefined / missing value
  assert.strictEqual(
    formatPaiseOrUnavailable(undefined),
    "N/A",
    "undefined should format to 'N/A'"
  );
  console.log("[PASS] 4. Undefined / missing realized savings formats to N/A");

  // 5. NaN / Infinity values
  assert.strictEqual(
    formatPaiseOrUnavailable(NaN),
    "N/A",
    "NaN should format to 'N/A'"
  );
  assert.strictEqual(
    formatPaiseOrUnavailable(Infinity),
    "N/A",
    "Infinity should format to 'N/A'"
  );
  assert.strictEqual(
    formatPaiseOrUnavailable(-Infinity),
    "N/A",
    "-Infinity should format to 'N/A'"
  );
  console.log("[PASS] 5. NaN / Infinity values format to N/A without throwing");

  console.log("\nALL FINANCIAL FORMATTER REGRESSION TESTS PASSED!");
}

runTests();
