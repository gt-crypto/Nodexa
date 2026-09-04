import React from "react";
import { EscalationWebhookPanel } from "../../components/EscalationWebhookPanel";

export const metadata = {
  title: "Escalation Webhooks | Nodexa",
  description: "Secure, HMAC-authenticated escalation notifications and finance ops routing.",
};

export default function EscalationsPage() {
  return (
    <div className="space-y-6">
      <EscalationWebhookPanel />
    </div>
  );
}
