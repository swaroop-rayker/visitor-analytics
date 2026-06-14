"use client";

import {
  Activity, BarChart3, Clock3, HeartPulse, LogOut, MapPinned, Users, Bug,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const navigation = [
  { href: "/", label: "Overview", icon: Activity },
  { href: "/visitors", label: "Visitors", icon: Users },
  { href: "/locations", label: "Locations", icon: MapPinned },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/timeline", label: "Timeline", icon: Clock3 },
  { href: "/system", label: "System Health", icon: HeartPulse },
  { href: "/debug", label: "Debug Logs", icon: Bug },
];

function Navigation({ mobile = false }: { mobile?: boolean }) {
  const pathname = usePathname();
  return (
    <nav className={cn(mobile ? "flex min-w-max gap-1" : "space-y-1")}>
      {navigation.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          className={cn(
            "focus-ring flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground",
            pathname === href && "bg-muted text-foreground",
          )}
        >
          <Icon className="size-4" /><span>{label}</span>
        </Link>
      ))}
    </nav>
  );
}

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  async function logout() {
    await api("/auth/logout", { method: "POST" });
    router.replace("/login");
  }
  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-60 border-r bg-card/40 p-4 lg:flex lg:flex-col">
        <div className="mb-7 flex items-center gap-3 px-2">
          <div className="grid size-8 place-items-center rounded-lg bg-primary font-bold text-primary-foreground">V</div>
          <div><p className="text-sm font-semibold">Visitor Analytics</p><p className="text-xs text-muted-foreground">Private workspace</p></div>
        </div>
        <Navigation />
        <Button variant="ghost" className="mt-auto justify-start text-muted-foreground" onClick={logout}>
          <LogOut className="mr-3 size-4" />Sign out
        </Button>
      </aside>
      <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur lg:hidden">
        <div className="flex h-14 items-center justify-between px-4">
          <span className="font-semibold">Visitor Analytics</span>
          <Button variant="ghost" size="icon" aria-label="Sign out" onClick={logout}><LogOut className="size-4" /></Button>
        </div>
        <div className="overflow-x-auto px-2 pb-2"><Navigation mobile /></div>
      </header>
      <main className="lg:pl-60">
        <div className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8">{children}</div>
      </main>
    </div>
  );
}

