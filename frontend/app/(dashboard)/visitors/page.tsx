"use client";

import { useCallback, useEffect, useState } from "react";
import { Confidence } from "@/components/confidence";
import { EmptyState, ErrorState, LoadingState } from "@/components/data-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { Page, Visitor } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export default function VisitorsPage() {
  const [data, setData] = useState<Page<Visitor>>();
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [returning, setReturning] = useState("");
  const [confidence, setConfidence] = useState("0");
  const [sort, setSort] = useState("most_recent");
  const load = useCallback(() => {
    setError("");
    const params = new URLSearchParams({ page: String(page), city, state, min_confidence: confidence, sort });
    if (returning) params.set("returning", returning);
    api<Page<Visitor>>(`/analytics/visitors?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, city, state, returning, confidence, sort]);
  useEffect(() => { load(); }, [load]);
  function filter() { setPage(1); load(); }
  return (
    <>
      <PageHeader title="Visitors" description="Anonymous browser signatures. No account identities or IP addresses are stored." />
      <Card className="mb-5 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-6">
        <Input placeholder="City" value={city} onChange={(e) => setCity(e.target.value)} />
        <Input placeholder="State" value={state} onChange={(e) => setState(e.target.value)} />
        <Select value={returning} onChange={(e) => setReturning(e.target.value)}>
          <option value="">All visitors</option><option value="true">Returning</option><option value="false">First-time</option>
        </Select>
        <Select value={confidence} onChange={(e) => setConfidence(e.target.value)}>
          <option value="0">Any confidence</option><option value="50">50%+</option><option value="75">75%+</option><option value="90">90%+</option>
        </Select>
        <Select value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="most_recent">Most recent</option><option value="oldest">Oldest</option>
          <option value="most_visits">Most visits</option><option value="least_visits">Least visits</option>
          <option value="city">City</option><option value="state">State</option><option value="confidence">Confidence</option>
          <option value="first_seen">First seen</option><option value="last_seen">Last seen</option>
        </Select>
        <Button onClick={filter}>Apply filters</Button>
      </Card>
      {error ? <ErrorState message={error} /> : !data ? <LoadingState /> : data.items.length === 0 ? <EmptyState /> : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/40 text-xs uppercase text-muted-foreground"><tr>
                <th className="px-4 py-3">Visitor ID</th><th className="px-4 py-3">First seen</th>
                <th className="px-4 py-3">Last seen</th><th className="px-4 py-3">Visits</th>
                <th className="px-4 py-3">Current estimate</th><th className="px-4 py-3">Confidence</th>
              </tr></thead>
              <tbody className="divide-y">
                {data.items.map((visitor) => <tr key={visitor.id} className="hover:bg-muted/20">
                  <td className="px-4 py-3 font-mono text-xs">{visitor.anonymous_id}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">{formatDate(visitor.first_seen)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">{formatDate(visitor.last_seen)}</td>
                  <td className="px-4 py-3">{visitor.total_visits}</td>
                  <td className="px-4 py-3">{[visitor.current_city, visitor.current_state].filter(Boolean).join(", ") || "Unknown"}</td>
                  <td className="px-4 py-3"><Confidence value={visitor.confidence_score} /></td>
                </tr>)}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t p-3 text-sm text-muted-foreground">
            <span>{data.meta.total} visitors</span><div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage((x) => x - 1)}>Previous</Button>
              <Button size="sm" variant="outline" disabled={page * data.meta.page_size >= data.meta.total} onClick={() => setPage((x) => x + 1)}>Next</Button>
            </div>
          </div>
        </Card>
      )}
    </>
  );
}

