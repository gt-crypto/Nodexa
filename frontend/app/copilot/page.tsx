import React from "react";
import { AskSentinelPanel } from "../../components/AskSentinelPanel";

export const metadata = {
  title: "Ask Sentinel Copilot | Nodal Sentinel",
  description: "Grounded AI Operational Copilot for nodal account inquiries and causal explanations.",
};

export default function CopilotPage() {
  return (
    <div className="space-y-6">
      <AskSentinelPanel />
    </div>
  );
}
