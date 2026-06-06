"use client";

import type { EChartsOption } from "echarts";
import { useEffect, useMemo, useState } from "react";
import { Chart } from "@/components/chart";
import { Confidence } from "@/components/confidence";
import { ErrorState, LoadingState } from "@/components/data-state";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { LocationPoint, LocationTrendPoint } from "@/lib/types";

export default function LocationsPage() {
  const [cities, setCities] = useState<LocationPoint[]>();
  const [states, setStates] = useState<LocationPoint[]>();
  const [trends, setTrends] = useState<LocationTrendPoint[]>();
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([
      api<LocationPoint[]>("/analytics/locations/city?limit=12"),
      api<LocationPoint[]>("/analytics/locations/state?limit=12"),
      api<LocationTrendPoint[]>("/analytics/location-trends?days=90"),
    ]).then(([c, s, t]) => { setCities(c); setStates(s); setTrends(t); }).catch((e) => setError(e.message));
  }, []);
  const option = useMemo<EChartsOption>(() => ({
    tooltip: { trigger: "axis" },
    grid: { left: 90, right: 20, top: 10, bottom: 25 },
    xAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#27272a" } } },
    yAxis: { type: "category", data: [...(cities || [])].reverse().map((x) => x.name), axisLabel: { color: "#a1a1aa" } },
    series: [{ type: "bar", data: [...(cities || [])].reverse().map((x) => x.visits), itemStyle: { color: "#22c55e", borderRadius: [0, 3, 3, 0] } }],
  }), [cities]);
  const trendOption = useMemo<EChartsOption>(() => {
    const periods = [...new Set((trends || []).map((x) => x.period))];
    const names = [...new Set((trends || []).map((x) => x.location))];
    return {
      tooltip: { trigger: "axis" },
      legend: { data: names, textStyle: { color: "#a1a1aa" } },
      grid: { left: 38, right: 16, top: 45, bottom: 35 },
      xAxis: { type: "category", data: periods, axisLabel: { color: "#71717a" } },
      yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#27272a" } } },
      series: names.map((name) => ({
        name, type: "line", smooth: true, showSymbol: false,
        data: periods.map((period) => trends?.find((x) => x.period === period && x.location === name)?.visits || 0),
      })),
    };
  }, [trends]);
  if (error) return <ErrorState message={error} />;
  if (!cities || !states || !trends) return <LoadingState />;
  return (
    <>
      <PageHeader title="Locations" description="Coarse GeoIP estimates. Confidence reflects source and historical consistency." />
      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2"><CardHeader><CardTitle>Geographic distribution</CardTitle></CardHeader><CardContent><Chart option={option} className="h-[420px]" /></CardContent></Card>
        <Card><CardHeader><CardTitle>Top states</CardTitle></CardHeader><CardContent className="space-y-4">
          {states.map((item, index) => <div key={item.name} className="flex items-center justify-between gap-3">
            <div className="min-w-0"><p className="truncate text-sm"><span className="mr-2 text-muted-foreground">{index + 1}</span>{item.name}</p><p className="text-xs text-muted-foreground">{item.unique_visitors} unique / {item.visits} visits</p></div>
            <Confidence value={item.average_confidence} />
          </div>)}
        </CardContent></Card>
      </div>
      <Card className="mt-5"><CardHeader><CardTitle>Location trends</CardTitle></CardHeader><CardContent><Chart option={trendOption} /></CardContent></Card>
    </>
  );
}
