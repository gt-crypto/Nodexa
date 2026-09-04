import React from "react";
import { VerifierPanel } from "../../components/VerifierPanel";
import { VerificationPanel } from "../../components/VerificationPanel";

export const metadata = {
  title: "Adversarial Verifier & Safety | Nodexa",
  description: "Adversarial policy verification and deterministic post-remediation evidence trail.",
};

export default function VerifierPage() {
  return (
    <div className="space-y-10">
      {/* Adversarial Verifier Safety Layer */}
      <VerifierPanel />

      {/* Post-Remediation Verification Engine & Audit Trail */}
      <VerificationPanel />
    </div>
  );
}
