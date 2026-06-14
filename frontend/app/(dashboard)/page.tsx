"use client";

import type { EChartsOption } from "echarts";
import { Bot, Building2, Globe2, MapPin, Repeat2, Route, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Chart } from "@/components/chart";
import { ErrorState, LoadingState } from "@/components/data-state";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Summary, TrendPoint } from "@/lib/types";

export default function OverviewPage() {
  const [summary, setSummary] = useState<Summary>();
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api<Summary>("/analytics/summary"), api<TrendPoint[]>("/analytics/trends?days=30")])
      .then(([s, t]) => { setSummary(s); setTrends(t); }).catch((e) => setError(e.message));
  }, []);
  const option = useMemo<EChartsOption>(() => ({
    tooltip: { trigger: "axis" },
    legend: { data: ["Visits", "Unique visitors"], textStyle: { color: "#a1a1aa" } },
    grid: { left: 36, right: 16, top: 40, bottom: 28 },
    xAxis: { type: "category", data: trends.map((x) => x.period), axisLabel: { color: "#71717a" } },
    yAxis: { type: "value", minInterval: 1, axisLabel: { color: "#71717a" }, splitLine: { lineStyle: { color: "#27272a" } } },
    series: [
      { name: "Visits", type: "line", smooth: true, showSymbol: false, data: trends.map((x) => x.visits), lineStyle: { color: "#22c55e" }, areaStyle: { color: "rgba(34,197,94,.08)" } },
      { name: "Unique visitors", type: "line", smooth: true, showSymbol: false, data: trends.map((x) => x.unique_visitors), lineStyle: { color: "#60a5fa" } },
    ],
  }), [trends]);
  if (error) return <ErrorState message={error} />;
  if (!summary) return <LoadingState />;
  return (
    <>
      <PageHeader title="Overview" description="A concise view of traffic to your tracked link." />
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-7">
        <StatCard label="Total visits" value={summary.total_visits} icon={Route} />
        <StatCard label="Unique visitors" value={summary.unique_visitors} icon={Users} />
        <StatCard label="Returning" value={summary.returning_visitors} icon={Repeat2} />
        <StatCard label="Crawler visits" value={summary.crawler_visits} icon={Bot} />
        <StatCard label="Top country" value={summary.top_country || "Unknown"} icon={Globe2} />
        <StatCard label="Top city" value={summary.top_city || "Unknown"} icon={Building2} hint={`${summary.average_confidence}% avg confidence`} />
        <StatCard label="Top state" value={summary.top_state || "Unknown"} icon={MapPin} />
      </section>
      <Card className="mt-6"><CardHeader><CardTitle>Last 30 days</CardTitle></CardHeader><CardContent><Chart option={option} /></CardContent></Card>
    </>
  );
}
