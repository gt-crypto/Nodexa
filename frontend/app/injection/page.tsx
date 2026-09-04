import React from "react";
import { LiveInjectionConsole } from "../../components/LiveInjectionConsole";

export const metadata = {
  title: "Live Digital-Twin Injection | Nodexa",
  description: "Live runtime synthetic anomaly injection for financial pipeline verification.",
};

export default function InjectionPage() {
  return (
    <div className="space-y-6">
      <LiveInjectionConsole />
    </div>
  );
}
