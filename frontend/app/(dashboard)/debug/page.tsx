"use client";

import { AlertCircle, Bug, CheckCircle2, HelpCircle, RefreshCw, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Confidence } from "@/components/confidence";
import { EmptyState, ErrorState, LoadingState } from "@/components/data-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Page, Visit } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export default function DebugPage() {
  const [data, setData] = useState<Page<Visit>>();
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(() => {
    setError("");
    setRefreshing(true);
    api<Page<Visit>>(`/analytics/debug?page=${page}&page_size=50`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setRefreshing(false));
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  function getStatusBadge(status: string) {
    switch (status) {
      case "persisted":
        return <Badge className="border-green-900 bg-green-950/40 text-green-400">persisted</Badge>;
      case "received":
        return <Badge className="border-blue-900 bg-blue-950/40 text-blue-400">received</Badge>;
      case "classified":
        return <Badge className="border-indigo-900 bg-indigo-950/40 text-indigo-400">classified</Badge>;
      case "geolocated":
        return <Badge className="border-purple-900 bg-purple-950/40 text-purple-400">geolocated</Badge>;
      case "failed":
        return <Badge className="border-red-900 bg-red-950/40 text-red-400">failed</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  }

  return (
    <>
      <PageHeader
        title="Admin Debug Logs"
        description="Comprehensive observability and reliability tracing for every tracking request received."
        actions={
          <Button size="sm" variant="outline" onClick={load} disabled={refreshing}>
            <RefreshCw className={`mr-2 size-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      {error ? (
        <ErrorState message={error} />
      ) : !data ? (
        <LoadingState />
      ) : !data.items.length ? (
        <EmptyState />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/40 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Status / DB</th>
                  <th className="px-4 py-3">Fingerprint</th>
                  <th className="px-4 py-3">Classification</th>
                  <th className="px-4 py-3">Location Estimate</th>
                  <th className="px-4 py-3">Geo Confidence</th>
                  <th className="px-4 py-3">Network</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.items.map((visit) => (
                  <tr key={visit.id} className="hover:bg-muted/20">
                    <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">
                      {formatDate(visit.timestamp)}
                    </td>
                    <td className="space-y-1.5 px-4 py-3">
                      <div>{getStatusBadge(visit.tracking_status)}</div>
                      <div className="flex items-center gap-1 text-xs">
                        {visit.tracking_status === "failed" ? (
                          <>
                            <XCircle className="size-3 text-red-400" />
                            <span className="text-red-400 font-medium truncate max-w-[150px]" title={visit.tracking_failure_reason || ""}>
                              {visit.tracking_failure_reason || "Write Failed"}
                            </span>
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="size-3 text-green-400" />
                            <span className="text-green-400 font-medium">Recorded</span>
                          </>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs" title="Truncated visitor fingerprint.">
                      {visit.anonymous_id}
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-semibold">{visit.classification}</p>
                      <p className="text-xs text-muted-foreground">
                        {Math.round(visit.classification_confidence * 100)}% conf
                      </p>
                      {visit.classification_reason && (
                        <p className="mt-1 text-xs text-muted-foreground/80 italic max-w-[200px]" title={visit.classification_reason || undefined}>
                          {visit.classification_reason}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium">
                        {[visit.city, visit.state, visit.country].filter(Boolean).join(", ") || "Unknown"}
                      </p>
                      <div className="mt-1">
                        <Badge className="text-xs">
                          {visit.location_source}
                        </Badge>
                      </div>
                      {visit.location_source_detail && (
                        <p className="mt-1 text-xxs text-muted-foreground/75 truncate max-w-[200px]" title={visit.location_source_detail || undefined}>
                          {visit.location_source_detail}
                        </p>
                      )}
                    </td>
                    <td className="flex flex-col gap-1 px-4 py-3">
                      <Confidence value={visit.country_confidence_score} label="country" />
                      <Confidence value={visit.state_confidence_score} label="state" />
                      <Confidence value={visit.city_confidence_score} label="city" />
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium">{visit.isp || visit.network_organization || "Unknown ISP"}</p>
                      <p className="text-xs text-muted-foreground">
                        {visit.asn ? `AS${visit.asn}` : "ASN unknown"} / {visit.network_type}
                      </p>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t p-3 text-sm text-muted-foreground">
            <span>{data.meta.total} attempt events</span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage((x) => x - 1)}>
                Previous
              </Button>
              <Button size="sm" variant="outline" disabled={page * data.meta.page_size >= data.meta.total} onClick={() => setPage((x) => x + 1)}>
                Next
              </Button>
            </div>
          </div>
        </Card>
      )}
    </>
  );
}
