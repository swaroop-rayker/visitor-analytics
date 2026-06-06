"use client";

import { Clock, Database, HardDrive, Map, MemoryStick, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "@/components/data-state";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Health } from "@/lib/types";
import { formatBytes, formatDate } from "@/lib/utils";

export default function SystemPage() {
  const [health, setHealth] = useState<Health>();
  const [error, setError] = useState("");
  useEffect(() => { api<Health>("/system/health").then(setHealth).catch((e) => setError(e.message)); }, []);
  if (error) return <ErrorState message={error} />;
  if (!health) return <LoadingState />;
  return (
    <>
      <PageHeader title="System Health" description="Operational status for the single-VM deployment." actions={<Badge className={health.status === "healthy" ? "text-green-400" : "text-amber-400"}>{health.status}</Badge>} />
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Database size" value={formatBytes(health.database_size_bytes)} icon={Database} hint={health.database_status} />
        <StatCard label="Disk usage" value={`${health.disk_used_percent.toFixed(1)}%`} icon={HardDrive} />
        <StatCard label="Memory usage" value={`${health.memory_used_percent.toFixed(1)}%`} icon={MemoryStick} />
        <StatCard label="Uptime" value={`${Math.floor(health.uptime_seconds / 3600)}h`} icon={Clock} />
      </section>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card><CardHeader><CardTitle className="flex items-center gap-2"><Map className="size-4" />GeoIP databases</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><div className="flex justify-between"><span className="text-muted-foreground">GeoLite2 City</span><Badge>{health.geoip_city_status}</Badge></div><div className="flex justify-between"><span className="text-muted-foreground">GeoLite2 ASN</span><Badge>{health.geoip_asn_status}</Badge></div></CardContent></Card>
        <Card><CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="size-4" />Data lifecycle</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><div className="flex justify-between"><span className="text-muted-foreground">Raw event retention</span><span>{health.raw_retention_days} days</span></div><div className="flex justify-between"><span className="text-muted-foreground">Last backup</span><span>{health.last_backup_time ? formatDate(health.last_backup_time) : "No backup found"}</span></div></CardContent></Card>
      </div>
    </>
  );
}

