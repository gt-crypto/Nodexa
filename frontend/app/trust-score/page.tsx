import React from "react";
import { MerchantTrustScorePanel } from "../../components/MerchantTrustScorePanel";

export const metadata = {
  title: "Merchant Trust Score | Nodexa",
  description: "Dynamic operational merchant risk assessment and determinant factor scoring.",
};

export default function TrustScorePage() {
  return (
    <div className="space-y-6">
      <div className="pb-2">
        <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
          Merchant Trust Score
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Operational trust and financial impact analytics for nodal accounts
        </p>
      </div>

      <MerchantTrustScorePanel />
    </div>
  );
}
