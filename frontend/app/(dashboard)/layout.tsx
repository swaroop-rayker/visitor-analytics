import { AuthGate } from "@/components/auth-gate";
import { DashboardShell } from "@/components/dashboard-shell";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <AuthGate><DashboardShell>{children}</DashboardShell></AuthGate>;
}

