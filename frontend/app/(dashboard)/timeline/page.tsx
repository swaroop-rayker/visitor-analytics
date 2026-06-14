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
  const [selected, setSelected] = useState<number[]>([]);
  const [isDeleting, setIsDeleting] = useState(false);
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [country, setCountry] = useState("");
  const [isp, setIsp] = useState("");
  const [asn, setAsn] = useState("");
  const [networkType, setNetworkType] = useState("");
  const [locationSource, setLocationSource] = useState("");
  const [classification, setClassification] = useState("");
  const [device, setDevice] = useState("");
  const [browser, setBrowser] = useState("");
  const [confidence, setConfidence] = useState("0");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const load = useCallback(() => {
    setSelected([]);
    const params = new URLSearchParams({ page: String(page), page_size: "50" });
    if (city) params.set("city", city);
    if (state) params.set("state", state);
    if (country) params.set("country", country);
    if (isp) params.set("isp", isp);
    if (asn) params.set("asn", asn);
    if (networkType) params.set("network_type", networkType);
    if (locationSource) params.set("location_source", locationSource);
    if (classification) params.set("classification", classification);
    if (device) params.set("device_type", device);
    if (browser) params.set("browser", browser);
    params.set("min_confidence", confidence);
    if (start) params.set("start_date", start);
    if (end) params.set("end_date", end);
    api<Page<Visit>>(`/analytics/visits?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, city, state, country, isp, asn, networkType, locationSource, classification, device, browser, confidence, start, end]);

  const toggleAll = () => {
    if (selected.length === data?.items.length) {
      setSelected([]);
    } else {
      setSelected(data?.items.map((item) => item.id) || []);
    }
  };

  const toggleOne = (id: number) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const deleteSelected = async () => {
    if (!selected.length) return;
    if (!confirm(`Are you sure you want to delete the ${selected.length} selected visit(s)?`)) return;
    setIsDeleting(true);
    try {
      await api<any>("/analytics/visits", {
        method: "DELETE",
        body: JSON.stringify({ ids: selected }),
      });
      setSelected([]);
      load();
    } catch (e: any) {
      alert(`Deletion failed: ${e.message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const deleteAll = async () => {
    if (!confirm("WARNING: Are you sure you want to delete ALL tracking data? This resets the dashboard and cannot be undone.")) return;
    setIsDeleting(true);
    try {
      await api<any>("/analytics/visits", {
        method: "DELETE",
        body: JSON.stringify({ all: true }),
      });
      setSelected([]);
      load();
    } catch (e: any) {
      alert(`Clear failed: ${e.message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  useEffect(() => { load(); }, [load]);
  return (
    <>
      <PageHeader title="Timeline" description="Chronological raw activity within the configured retention window." />
      <Card className="mb-5 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Input placeholder="City" value={city} onChange={(e) => setCity(e.target.value)} />
        <Input placeholder="State" value={state} onChange={(e) => setState(e.target.value)} />
        <Input placeholder="Country" value={country} onChange={(e) => setCountry(e.target.value)} />
        <Input placeholder="ISP / organization" value={isp} onChange={(e) => setIsp(e.target.value)} />
        <Input placeholder="ASN" value={asn} onChange={(e) => setAsn(e.target.value.replace(/\D/g, ""))} />
        <Select value={networkType} onChange={(e) => setNetworkType(e.target.value)}>
          <option value="">All networks</option><option>Residential Broadband</option><option>Mobile Carrier</option>
          <option>Corporate Network</option><option>Datacenter</option><option>Cloud Provider</option>
          <option>VPN</option><option>Proxy</option>
        </Select>
        <Select value={locationSource} onChange={(e) => setLocationSource(e.target.value)}>
          <option value="">All sources</option><option>IP/ASN Inference</option><option>Hybrid Inference</option>
          <option>Browser Geolocation API (user-consented)</option>
          <option>Browser Geolocation API (historical)</option>
          <option>Hybrid Inference (Historical)</option>
          <option>IP/ASN Inference (Historical)</option>
        </Select>
        <Select value={classification} onChange={(e) => setClassification(e.target.value)}>
          <option value="">All classifications</option>
          <option>Human</option>
          <option>Likely Human</option>
          <option>Unknown</option>
          <option>Likely Bot</option>
          <option>Known Bot</option>
          <option>Social Media Crawler</option>
          <option>Search Engine Crawler</option>
          <option>Security Scanner</option>
          <option>Monitoring Service</option>
        </Select>
        <Select value={device} onChange={(e) => setDevice(e.target.value)}><option value="">All devices</option><option>Mobile</option><option>Desktop</option><option>Tablet</option><option>Other</option></Select>
        <Input placeholder="Browser (exact)" value={browser} onChange={(e) => setBrowser(e.target.value)} />
        <Select value={confidence} onChange={(e) => setConfidence(e.target.value)}><option value="0">Any confidence</option><option value="50">50%+</option><option value="75">75%+</option><option value="90">90%+</option></Select>
        <Input type="date" aria-label="Start date" value={start} onChange={(e) => setStart(e.target.value)} />
        <Input type="date" aria-label="End date" value={end} onChange={(e) => setEnd(e.target.value)} />
        <Button onClick={() => { setPage(1); load(); }}>Apply filters</Button>
      </Card>
      {error ? <ErrorState message={error} /> : !data ? <LoadingState /> : !data.items.length ? <EmptyState /> : (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 px-1">
            <div className="text-sm text-muted-foreground">
              {selected.length > 0 ? (
                <span className="text-red-400 font-semibold">{selected.length} selected</span>
              ) : (
                "Select rows to perform actions"
              )}
            </div>
            <div className="flex gap-2">
              {selected.length > 0 && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="border border-red-900/50 bg-red-950/30 text-red-400 hover:bg-red-900/30 hover:text-red-200"
                  disabled={isDeleting}
                  onClick={deleteSelected}
                >
                  Delete Selected ({selected.length})
                </Button>
              )}
              <Button
                size="sm"
                variant="outline"
                className="border-red-900/30 text-red-400 hover:bg-red-950/20 hover:text-red-300"
                disabled={isDeleting}
                onClick={deleteAll}
              >
                Delete All Data
              </Button>
            </div>
          </div>
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b bg-muted/40 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="w-12 px-4 py-3">
                      <input
                        type="checkbox"
                        className="size-4 rounded border-gray-300 accent-primary"
                        checked={data.items.length > 0 && selected.length === data.items.length}
                        onChange={toggleAll}
                      />
                    </th>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3">Visitor</th>
                    <th className="px-4 py-3">Location</th>
                    <th className="px-4 py-3">Device</th>
                    <th className="px-4 py-3">Network</th>
                    <th className="px-4 py-3">Confidence</th>
                    <th className="px-4 py-3">Classification</th>
                    <th className="px-4 py-3">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {data.items.map((visit) => (
                    <tr key={visit.id} className="hover:bg-muted/20">
                      <td className="w-12 px-4 py-3">
                        <input
                          type="checkbox"
                          className="size-4 rounded border-gray-300 accent-primary"
                          checked={selected.includes(visit.id)}
                          onChange={() => toggleOne(visit.id)}
                        />
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">{formatDate(visit.timestamp)}</td>
                      <td className="px-4 py-3 font-mono text-xs">{visit.anonymous_id}</td>
                      <td className="px-4 py-3">
                        <p>{[visit.city, visit.state, visit.country].filter(Boolean).join(", ") || "Unknown"}</p>
                        {visit.city_confidence_score < 45 && <p className="text-xs text-amber-400">Approximate city estimate</p>}
                        {visit.location_source === "Browser Geolocation API (user-consented)" && <p className="text-xs text-green-400">User-consented precise location</p>}
                      </td>
                      <td className="px-4 py-3">
                        <p className="font-medium">{visit.device_type || "Unknown"}</p>
                        <p className="text-xs text-muted-foreground">{visit.browser} on {visit.os || "Unknown OS"}</p>
                        {visit.screen_resolution && <p className="text-xs text-muted-foreground/80">{visit.screen_resolution}</p>}
                        {(visit.cores !== null || visit.memory !== null || visit.gpu !== null) && (
                          <div className="mt-1.5 flex flex-col gap-0.5 text-xs text-muted-foreground/75 bg-muted/40 p-1.5 rounded border border-border max-w-[220px]">
                            {visit.cores !== null && <span>CPU: {visit.cores} Cores</span>}
                            {visit.memory !== null && <span>RAM: {visit.memory} GB</span>}
                            {visit.gpu !== null && <span className="truncate" title={visit.gpu || undefined}>GPU: {visit.gpu}</span>}
                          </div>
                        )}
                        {visit.is_anomalous && visit.anomaly_reasons && (
                          <div className="mt-2 flex flex-wrap gap-1 max-w-[220px]">
                            {visit.anomaly_reasons.map((reason) => {
                              let label = reason;
                              let isSpoof = false;
                              if (reason === "headless_software_gpu") { label = "Headless Browser"; isSpoof = true; }
                              else if (reason === "gpu_os_mismatch") { label = "Spoof: GPU Mismatch"; isSpoof = true; }
                              else if (reason === "ios_memory_leak") { label = "Spoof: iOS Emulator"; isSpoof = true; }
                              else if (reason === "suspicious_hardware_capacity") { label = "Spoof: Fake Specs"; isSpoof = true; }
                              else if (reason === "probable_vpn") { label = "VPN"; }
                              else if (reason === "hosting_provider") { label = "Datacenter/Cloud"; }
                              else if (reason === "rapid_country_change") { label = "Geo-jump (Country)"; }
                              else if (reason === "rapid_city_change") { label = "Geo-jump (City)"; }
                              else if (reason === "historical_location_inconsistency") { label = "Location Drift"; }
                              
                              return (
                                <Badge 
                                  key={reason}
                                  className={isSpoof 
                                    ? "bg-red-950/40 text-red-400 border-red-900/50 text-[10px] py-0.5 px-1.5" 
                                    : "bg-amber-950/40 text-amber-400 border-amber-900/50 text-[10px] py-0.5 px-1.5"
                                  }
                                >
                                  {label}
                                </Badge>
                              );
                            })}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <p className="font-medium">{visit.isp || visit.network_organization || "Unknown ISP"}</p>
                        <p className="text-xs text-muted-foreground">{visit.asn ? `AS${visit.asn}` : "ASN unknown"}</p>
                        <div className="mt-1 flex flex-wrap gap-1 items-center">
                          <Badge>{visit.network_type}</Badge>
                          {visit.has_private_ip && <Badge className="bg-green-950/40 text-green-400 border-green-900/50">Private IP</Badge>}
                          {visit.save_data && <Badge className="bg-amber-950/40 text-amber-400 border-amber-900/50">Data Saver</Badge>}
                          {visit.is_anomalous && (
                            <span title={visit.anomaly_reasons?.join(", ") || undefined}>
                              <AlertTriangle className="ml-1 inline size-4 text-amber-400 align-middle" />
                            </span>
                          )}
                        </div>
                        {(visit.rtt !== null || visit.downlink !== null || visit.ping_jitter !== null) && (
                          <div className="mt-1.5 flex flex-col gap-0.5 text-xs text-muted-foreground/75 bg-muted/40 p-1.5 rounded border border-border max-w-[220px]">
                            {visit.rtt !== null && <span>RTT: {visit.rtt} ms</span>}
                            {visit.downlink !== null && <span>Bandwidth: {visit.downlink} Mbps</span>}
                            {visit.ping_jitter !== null && <span>Jitter: {visit.ping_jitter} ms</span>}
                          </div>
                        )}
                      </td>
                      <td className="flex flex-col gap-1 px-4 py-3">
                        <Confidence value={visit.country_confidence_score} label="country" />
                        <Confidence value={visit.state_confidence_score} label="state" />
                        <Confidence value={visit.city_confidence_score} label="city" />
                      </td>
                      <td className="px-4 py-3">
                        <p>{visit.classification}</p>
                        <p className="text-xs text-muted-foreground">{Math.round(visit.classification_confidence * 100)}% conf</p>
                      </td>
                      <td className="px-4 py-3"><Badge>{visit.location_source}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t p-3 text-sm text-muted-foreground">
              <span>{data.meta.total} retained events</span>
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
        </>
      )}
    </>
  );
}
