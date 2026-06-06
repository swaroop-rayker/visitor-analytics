"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LoadingState } from "@/components/data-state";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    api<{ authenticated: boolean }>("/auth/session")
      .then(() => setReady(true))
      .catch(() => router.replace(`/login?next=${encodeURIComponent(pathname)}`));
  }, [pathname, router]);
  return ready ? children : <LoadingState />;
}

