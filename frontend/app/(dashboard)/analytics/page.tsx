"use client";

import type { EChartsOption } from "echarts";
import { useEffect, useMemo, useState } from "react";
import { Chart } from "@/components/chart";
import { ErrorState, LoadingState } from "@/components/data-state";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { FrequencyPoint, RetentionPoint, TrendPoint } from "@/lib/types";

export default function AnalyticsPage() {
  const [period, setPeriod] = useState("weekly");
  const [trends, setTrends] = useState<TrendPoint[]>();
  const [retention, setRetention] = useState<RetentionPoint[]>();
  const [frequency, setFrequency] = useState<FrequencyPoint[]>();
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([
      api<TrendPoint[]>(`/analytics/trends?period=${period}&days=365`),
      api<RetentionPoint[]>("/analytics/retention"),
      api<FrequencyPoint[]>("/analytics/frequency"),
    ]).then(([t, r, f]) => { setTrends(t); setRetention(r); setFrequency(f); }).catch((e) => setError(e.message));
  }, [period]);
  const activity = useMemo<EChartsOption>(() => ({
    tooltip: { trigger: "axis" },
    legend: { data: ["Visits", "Unique"], textStyle: { color: "#a1a1aa" } },
    grid: { left: 38, right: 16, top: 40, bottom: 45 },
    xAxis: { type: "category", data: trends?.map((x) => x.period), axisLabel: { color: "#71717a", rotate: 35 } },
    yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#27272a" } } },
    series: [
      { name: "Visits", type: "bar", data: trends?.map((x) => x.visits), itemStyle: { color: "#22c55e" } },
      { name: "Unique", type: "line", data: trends?.map((x) => x.unique_visitors), lineStyle: { color: "#60a5fa" } },
    ],
  }), [trends]);
  const retentionOption = useMemo<EChartsOption>(() => ({
    tooltip: { trigger: "axis", formatter: "{b}: {c}%" },
    grid: { left: 38, right: 16, top: 15, bottom: 45 },
    xAxis: { type: "category", data: retention?.map((x) => x.cohort), axisLabel: { color: "#71717a", rotate: 35 } },
    yAxis: { type: "value", max: 100, axisLabel: { formatter: "{value}%" }, splitLine: { lineStyle: { color: "#27272a" } } },
    series: [{ type: "line", smooth: true, data: retention?.map((x) => x.retention_rate), lineStyle: { color: "#a78bfa" }, areaStyle: { color: "rgba(167,139,250,.08)" } }],
  }), [retention]);
  const frequencyOption = useMemo<EChartsOption>(() => ({
    tooltip: { trigger: "item" },
    grid: { left: 38, right: 16, top: 15, bottom: 30 },
    xAxis: { type: "category", data: frequency?.map((x) => `${x.bucket} visits`), axisLabel: { color: "#a1a1aa" } },
    yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#27272a" } } },
    series: [{ type: "bar", data: frequency?.map((x) => x.visitors), itemStyle: { color: "#f59e0b", borderRadius: [4, 4, 0, 0] } }],
  }), [frequency]);
  if (error) return <ErrorState message={error} />;
  if (!trends || !retention || !frequency) return <LoadingState />;
  return (
    <>
      <PageHeader title="Analytics" description="Activity, visitor frequency, and repeat-visit retention." actions={
        <Select value={period} onChange={(e) => setPeriod(e.target.value)}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></Select>
      } />
      <div className="grid gap-5 xl:grid-cols-2">
        <Card><CardHeader><CardTitle>Activity</CardTitle></CardHeader><CardContent><Chart option={activity} /></CardContent></Card>
        <Card><CardHeader><CardTitle>Visitor retention by cohort</CardTitle><p className="text-xs text-muted-foreground">Share of each weekly cohort that returned at least once.</p></CardHeader><CardContent><Chart option={retentionOption} /></CardContent></Card>
        <Card><CardHeader><CardTitle>Visitor frequency</CardTitle><p className="text-xs text-muted-foreground">Anonymous visitors grouped by lifetime visit count.</p></CardHeader><CardContent><Chart option={frequencyOption} /></CardContent></Card>
      </div>
    </>
  );
}
