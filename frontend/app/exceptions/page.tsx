import React from "react";
import { ExceptionManagementPanel } from "../../components/ExceptionManagementPanel";

export const metadata = {
  title: "Exception Management & Investigation | Nodexa",
  description: "Enterprise exception management console, investigation workspace, and verified closed audit confirmation.",
};

export default function ExceptionsPage() {
  return (
    <div className="space-y-6">
      <ExceptionManagementPanel />
    </div>
  );
}
