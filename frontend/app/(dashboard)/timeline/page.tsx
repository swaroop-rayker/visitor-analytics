"use client";

import { AlertTriangle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Confidence } from "@/components/confidence";
import { EmptyState, ErrorState, LoadingState } from "@/components/data-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { Page, Visit } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export default function TimelinePage() {
  const [data, setData] = useState<Page<Visit>>();
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [device, setDevice] = useState("");
  const [browser, setBrowser] = useState("");
  const [confidence, setConfidence] = useState("0");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const load = useCallback(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "50" });
    if (city) params.set("city", city);
    if (state) params.set("state", state);
    if (device) params.set("device_type", device);
    if (browser) params.set("browser", browser);
    params.set("min_confidence", confidence);
    if (start) params.set("start_date", start);
    if (end) params.set("end_date", end);
    api<Page<Visit>>(`/analytics/visits?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, city, state, device, browser, confidence, start, end]);
  useEffect(() => { load(); }, [load]);
  return (
    <>
      <PageHeader title="Timeline" description="Chronological raw activity within the configured retention window." />
      <Card className="mb-5 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Input placeholder="City" value={city} onChange={(e) => setCity(e.target.value)} />
        <Input placeholder="State" value={state} onChange={(e) => setState(e.target.value)} />
        <Select value={device} onChange={(e) => setDevice(e.target.value)}><option value="">All devices</option><option>Mobile</option><option>Desktop</option><option>Tablet</option><option>Other</option></Select>
        <Input placeholder="Browser (exact)" value={browser} onChange={(e) => setBrowser(e.target.value)} />
        <Select value={confidence} onChange={(e) => setConfidence(e.target.value)}><option value="0">Any confidence</option><option value="50">50%+</option><option value="75">75%+</option><option value="90">90%+</option></Select>
        <Input type="date" aria-label="Start date" value={start} onChange={(e) => setStart(e.target.value)} />
        <Input type="date" aria-label="End date" value={end} onChange={(e) => setEnd(e.target.value)} />
        <Button onClick={() => { setPage(1); load(); }}>Apply filters</Button>
      </Card>
      {error ? <ErrorState message={error} /> : !data ? <LoadingState /> : !data.items.length ? <EmptyState /> : (
        <Card className="overflow-hidden"><div className="overflow-x-auto"><table className="w-full text-left text-sm">
          <thead className="border-b bg-muted/40 text-xs uppercase text-muted-foreground"><tr><th className="px-4 py-3">Timestamp</th><th className="px-4 py-3">Visitor</th><th className="px-4 py-3">Location estimate</th><th className="px-4 py-3">Device</th><th className="px-4 py-3">Network</th><th className="px-4 py-3">Confidence</th></tr></thead>
          <tbody className="divide-y">{data.items.map((visit) => <tr key={visit.id} className="hover:bg-muted/20">
            <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">{formatDate(visit.timestamp)}</td><td className="px-4 py-3 font-mono text-xs">{visit.anonymous_id}</td>
            <td className="px-4 py-3">{[visit.city, visit.state].filter(Boolean).join(", ") || "Unknown"}</td><td className="px-4 py-3"><p>{visit.device_type || "Unknown"}</p><p className="text-xs text-muted-foreground">{visit.browser}</p></td>
            <td className="px-4 py-3"><Badge>{visit.network_type}</Badge>{visit.is_anomalous && <span title={visit.anomaly_reasons?.join(", ")}><AlertTriangle className="ml-2 inline size-4 text-amber-400" /></span>}</td>
            <td className="px-4 py-3"><Confidence value={visit.confidence_score} /></td>
          </tr>)}</tbody>
        </table></div><div className="flex items-center justify-between border-t p-3 text-sm text-muted-foreground"><span>{data.meta.total} retained events</span><div className="flex gap-2"><Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage((x) => x - 1)}>Previous</Button><Button size="sm" variant="outline" disabled={page * data.meta.page_size >= data.meta.total} onClick={() => setPage((x) => x + 1)}>Next</Button></div></div></Card>
      )}
    </>
  );
}
