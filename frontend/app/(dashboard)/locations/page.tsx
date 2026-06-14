"use client";

import type { EChartsOption } from "echarts";
import { useEffect, useMemo, useState } from "react";
import { Chart } from "@/components/chart";
import { Confidence } from "@/components/confidence";
import { ErrorState, LoadingState } from "@/components/data-state";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { CrawlerPoint, LocationPoint, LocationTrendPoint } from "@/lib/types";

function RankList({ title, items }: { title: string; items: LocationPoint[] }) {
  return (
    <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent className="space-y-4">
      {items.map((item, index) => <div key={`${title}-${item.name}`} className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm"><span className="mr-2 text-muted-foreground">{index + 1}</span>{item.name}</p>
          <p className="text-xs text-muted-foreground">{item.unique_visitors} unique / {item.visits} visits</p>
        </div>
        <Confidence value={item.average_confidence} />
      </div>)}
    </CardContent></Card>
  );
}

export default function LocationsPage() {
  const [cities, setCities] = useState<LocationPoint[]>();
  const [states, setStates] = useState<LocationPoint[]>();
  const [countries, setCountries] = useState<LocationPoint[]>();
  const [isps, setIsps] = useState<LocationPoint[]>();
  const [asns, setAsns] = useState<LocationPoint[]>();
  const [networkTypes, setNetworkTypes] = useState<LocationPoint[]>();
  const [sources, setSources] = useState<LocationPoint[]>();
  const [classifications, setClassifications] = useState<LocationPoint[]>();
  const [crawlers, setCrawlers] = useState<CrawlerPoint[]>();
  const [trends, setTrends] = useState<LocationTrendPoint[]>();
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([
      api<LocationPoint[]>("/analytics/locations/country?limit=12"),
      api<LocationPoint[]>("/analytics/locations/city?limit=12"),
      api<LocationPoint[]>("/analytics/locations/state?limit=12"),
      api<LocationPoint[]>("/analytics/locations/isp?limit=8"),
      api<LocationPoint[]>("/analytics/locations/asn?limit=8"),
      api<LocationPoint[]>("/analytics/locations/network_type?limit=8"),
      api<LocationPoint[]>("/analytics/locations/location_source?limit=8"),
      api<LocationPoint[]>("/analytics/locations/classification?limit=8"),
      api<CrawlerPoint[]>("/analytics/crawlers?limit=8"),
      api<LocationTrendPoint[]>("/analytics/location-trends?group_by=state&days=90"),
    ]).then(([countryRows, cityRows, stateRows, ispRows, asnRows, networkRows, sourceRows, classificationRows, crawlerRows, trendRows]) => {
      setCountries(countryRows); setCities(cityRows); setStates(stateRows); setIsps(ispRows);
      setAsns(asnRows); setNetworkTypes(networkRows); setSources(sourceRows); setClassifications(classificationRows); setCrawlers(crawlerRows); setTrends(trendRows);
    }).catch((e) => setError(e.message));
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
  if (!cities || !states || !countries || !isps || !asns || !networkTypes || !sources || !classifications || !crawlers || !trends) return <LoadingState />;
  return (
    <>
      <PageHeader title="Locations" description="Coarse GeoIP estimates. Confidence reflects source and historical consistency." />
      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2"><CardHeader><CardTitle>Geographic distribution</CardTitle></CardHeader><CardContent><Chart option={option} className="h-[420px]" /></CardContent></Card>
        <RankList title="Top states" items={states} />
      </div>
      <Card className="mt-5"><CardHeader><CardTitle>Location trends</CardTitle></CardHeader><CardContent><Chart option={trendOption} /></CardContent></Card>
      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <RankList title="Top countries" items={countries} />
        <RankList title="Top cities" items={cities} />
        <RankList title="Top ISPs" items={isps} />
        <RankList title="Top ASNs" items={asns.map((item) => ({ ...item, name: item.name === "Unknown" ? item.name : `AS${item.name}` }))} />
        <RankList title="Network types" items={networkTypes} />
        <RankList title="Location sources" items={sources} />
        <RankList title="Classifications" items={classifications} />
        <Card><CardHeader><CardTitle>Crawler analytics</CardTitle></CardHeader><CardContent className="space-y-4">
          {crawlers.length === 0 ? <p className="text-sm text-muted-foreground">No crawler traffic recorded.</p> : crawlers.map((item, index) => (
            <div key={item.crawler_type} className="flex items-center justify-between gap-3">
              <p className="truncate text-sm"><span className="mr-2 text-muted-foreground">{index + 1}</span>{item.crawler_type}</p>
              <p className="text-xs text-muted-foreground">{item.visits} visits</p>
            </div>
          ))}
        </CardContent></Card>
      </div>
    </>
  );
}
