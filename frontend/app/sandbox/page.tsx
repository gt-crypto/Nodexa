import React from "react";
import SandboxPanel from "../../components/SandboxPanel";

export const metadata = {
  title: "Test New Dataset | Nodexa AI Finance Controller",
  description: "Test unseen operational CSV datasets in an isolated in-memory sandbox with zero production database mutation.",
};

export default function SandboxPage() {
  return (
    <div className="space-y-6">
      <div className="pb-1">
        <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
          Test New Dataset
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Evaluate custom operational CSV batches against Nodexa&apos;s deterministic financial controls in an isolated sandbox.
        </p>
      </div>

      <SandboxPanel />
    </div>
  );
}
