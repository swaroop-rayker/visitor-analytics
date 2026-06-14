"use client";

import { Clock, Database, HardDrive, Map, MemoryStick, ShieldCheck, Globe, RefreshCw, Signal } from "lucide-react";
import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "@/components/data-state";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Health } from "@/lib/types";
import { formatBytes, formatDate } from "@/lib/utils";

export default function SystemPage() {
  const [health, setHealth] = useState<Health>();
  const [error, setError] = useState("");
  
  // Settings Update state
  const [redirectUrl, setRedirectUrl] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");
  const [saveMessage, setSaveMessage] = useState("");

  // GeoIP update state
  const [isUpdatingGeoIP, setIsUpdatingGeoIP] = useState(false);
  const [geoIPMessage, setGeoIPMessage] = useState("");
  const [isTogglingGeoIP, setIsTogglingGeoIP] = useState(false);

  // Latency toggle state
  const [isTogglingLatency, setIsTogglingLatency] = useState(false);
  const [latencyMessage, setLatencyMessage] = useState("");

  // Initial load
  useEffect(() => {
    api<Health>("/system/health")
      .then((data) => {
        setHealth(data);
        setRedirectUrl(data.redirect_target_url);
      })
      .catch((e) => setError(e.message));
  }, []);

  // Poll health endpoint every 4s while GeoIP update is in progress
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (health?.geoip_update_in_progress) {
      interval = setInterval(() => {
        api<Health>("/system/health")
          .then((data) => {
            setHealth(data);
            if (!data.geoip_update_in_progress) {
              setGeoIPMessage("");
            }
          })
          .catch(() => {});
      }, 4000);
    }
    return () => clearInterval(interval);
  }, [health?.geoip_update_in_progress]);

  async function handleSaveRedirect(e: React.FormEvent) {
    e.preventDefault();
    setIsSaving(true);
    setSaveStatus("idle");
    setSaveMessage("");
    
    try {
      const res = await api<{ success: boolean; redirect_target_url: string }>("/system/config/redirect", {
        method: "POST",
        body: JSON.stringify({ redirect_target_url: redirectUrl }),
      });
      if (res.success) {
        setSaveStatus("success");
        setSaveMessage("Redirect URL updated successfully in real-time!");
        if (health) {
          setHealth({ ...health, redirect_target_url: res.redirect_target_url });
        }
      } else {
        setSaveStatus("error");
        setSaveMessage("Failed to update redirect URL.");
      }
    } catch (e: any) {
      setSaveStatus("error");
      setSaveMessage(e.message || "Failed to update redirect URL.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleTriggerGeoIPUpdate() {
    setIsUpdatingGeoIP(true);
    setGeoIPMessage("");
    try {
      const res = await api<{ success: boolean; detail: string; has_license_key: boolean; initiated: boolean }>("/system/geoip/update", {
        method: "POST",
      });
      if (res.success) {
        setGeoIPMessage(res.detail);
        if (res.initiated && health) {
          setHealth({ ...health, geoip_update_in_progress: true, geoip_city_status: "updating", geoip_asn_status: "updating" });
        } else {
          setTimeout(() => setGeoIPMessage(""), 5000);
        }
      } else {
        setGeoIPMessage("Failed to trigger GeoIP update.");
      }
    } catch (e: any) {
      setGeoIPMessage(e.message || "Error triggering GeoIP update.");
    } finally {
      setIsUpdatingGeoIP(false);
    }
  }

  async function handleToggleGeoIP(disabled: boolean) {
    setIsTogglingGeoIP(true);
    setGeoIPMessage("");
    try {
      const res = await api<{ success: boolean; disabled: boolean; env_updated: boolean }>("/system/geoip/toggle", {
        method: "POST",
        body: JSON.stringify({ disabled }),
      });
      if (res.success) {
        // Fetch fresh health stats to update the whole screen
        const freshHealth = await api<Health>("/system/health");
        setHealth(freshHealth);
        
        if (!res.env_updated) {
          setGeoIPMessage("⚠️ Applied in-memory, but failed to write to .env file on disk. Changes will be lost on container restart.");
        } else {
          setGeoIPMessage(disabled ? "✅ Databases disabled and saved to disk." : "✅ Databases enabled and saved to disk.");
          setTimeout(() => setGeoIPMessage(""), 5000);
        }
      }
    } catch (e: any) {
      setGeoIPMessage(`❌ Error: ${e.message || "Failed to toggle databases."}`);
    } finally {
      setIsTogglingGeoIP(false);
    }
  }

  async function handleToggleLatency(disabled: boolean) {
    setIsTogglingLatency(true);
    setLatencyMessage("");
    try {
      const res = await api<{ success: boolean; disabled: boolean; env_updated: boolean }>("/system/latency/toggle", {
        method: "POST",
        body: JSON.stringify({ disabled }),
      });
      if (res.success) {
        // Fetch fresh health stats to update the whole screen
        const freshHealth = await api<Health>("/system/health");
        setHealth(freshHealth);
        
        if (!res.env_updated) {
          setLatencyMessage("⚠️ Applied in-memory, but failed to write to .env file on disk. Changes will be lost on container restart.");
        } else {
          setLatencyMessage(disabled ? "✅ Latency triangulation disabled and saved to disk." : "✅ Latency triangulation enabled and saved to disk.");
          setTimeout(() => setLatencyMessage(""), 5000);
        }
      }
    } catch (e: any) {
      setLatencyMessage(`❌ Error: ${e.message || "Failed to toggle latency triangulation."}`);
    } finally {
      setIsTogglingLatency(false);
    }
  }

  function getGeoIPBadge(status: string) {
    switch (status) {
      case "up_to_date":
        return <Badge className="bg-emerald-500/15 text-emerald-500 hover:bg-emerald-500/15 border border-emerald-500/30">Up to date</Badge>;
      case "update_available":
        return <Badge className="bg-amber-500/15 text-amber-500 hover:bg-amber-500/15 border border-amber-500/30">Update available</Badge>;
      case "updating":
        return <Badge className="bg-blue-500/15 text-blue-500 hover:bg-blue-500/15 border border-blue-500/30 animate-pulse">Updating...</Badge>;
      case "disabled":
        return <Badge className="bg-slate-500/15 text-slate-400 hover:bg-slate-500/15 border border-slate-500/30">Disabled</Badge>;
      case "missing":
      default:
        return <Badge className="bg-rose-500/15 text-rose-500 hover:bg-rose-500/15 border border-rose-500/30">Missing</Badge>;
    }
  }

  if (error) return <ErrorState message={error} />;
  if (!health) return <LoadingState />;

  const isGeoIPUpdating = isUpdatingGeoIP || health.geoip_update_in_progress;

  return (
    <>
      <PageHeader title="System Health" description="Operational status for the single-VM deployment." actions={<Badge className={health.status === "healthy" ? "text-green-400" : "text-amber-400"}>{health.status}</Badge>} />
      
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Database size" value={formatBytes(health.database_size_bytes)} icon={Database} hint={health.database_status} />
        <StatCard 
          label="Disk usage" 
          value={`${health.disk_used_percent.toFixed(1)}%`} 
          icon={HardDrive} 
          hint={`${formatBytes(health.disk_used_bytes)} / ${formatBytes(health.disk_total_bytes)}`}
        />
        <StatCard 
          label="Memory usage" 
          value={`${health.memory_used_percent.toFixed(1)}%`} 
          icon={MemoryStick} 
          hint={`${formatBytes(health.memory_used_bytes)} / ${formatBytes(health.memory_total_bytes)}`}
        />
        <StatCard 
          label="Uptime" 
          value={(() => {
            const d = Math.floor(health.uptime_seconds / 86400);
            const h = Math.floor((health.uptime_seconds % 86400) / 3600);
            const m = Math.floor((health.uptime_seconds % 3600) / 60);
            return d > 0 ? `${d}d ${h}h ${m}m` : `${h}h ${m}m`;
          })()} 
          icon={Clock} 
        />
      </section>

      <div className="mt-5 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {/* GeoIP Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Map className="size-4" />GeoIP Databases
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">GeoLite2 City</span>
              {getGeoIPBadge(health.geoip_city_status)}
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">GeoLite2 ASN</span>
              {getGeoIPBadge(health.geoip_asn_status)}
            </div>
            <div className="pt-2 border-t space-y-2">
              <Button 
                variant="outline" 
                size="sm" 
                className="w-full flex items-center justify-center gap-2"
                onClick={handleTriggerGeoIPUpdate}
                disabled={isGeoIPUpdating || health.disable_maxmind_db}
              >
                <RefreshCw className={`size-3.5 ${isGeoIPUpdating ? "animate-spin" : ""}`} />
                {isGeoIPUpdating ? "Updating..." : "Trigger Auto-Update"}
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                className={`w-full flex items-center justify-center gap-2 transition-colors ${
                  health.disable_maxmind_db 
                    ? "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 border-emerald-500/30" 
                    : "text-rose-400 hover:text-rose-300 hover:bg-rose-950/20 border-rose-900/30"
                }`}
                onClick={() => handleToggleGeoIP(!health.disable_maxmind_db)}
                disabled={isTogglingGeoIP}
              >
                {health.disable_maxmind_db ? "Enable Databases" : "Disable Databases"}
              </Button>

              {geoIPMessage && (
                <p className="mt-2 text-xs text-muted-foreground text-center text-wrap">
                  {geoIPMessage}
                </p>
              )}
              {health.geoip_last_error && (
                <p className="mt-2 text-xs text-rose-400 font-medium border border-rose-500/20 bg-rose-500/10 p-2 rounded text-center text-wrap">
                  Error: {health.geoip_last_error}
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Redirect Target URL Control Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="size-4" />Redirect Target URL
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            <form onSubmit={handleSaveRedirect} className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="redirect-url-input" className="text-xs text-muted-foreground block">
                  Target Destination for /go Tracking
                </label>
                <Input 
                  id="redirect-url-input"
                  type="url"
                  className="w-full"
                  value={redirectUrl}
                  onChange={(e) => setRedirectUrl(e.target.value)}
                  placeholder="https://example.com"
                  required
                />
              </div>
              <Button 
                type="submit" 
                size="sm" 
                className="w-full"
                disabled={isSaving}
              >
                {isSaving ? "Saving..." : "Save Target URL"}
              </Button>
              {saveMessage && (
                <p className={`text-xs mt-1 text-center font-medium ${saveStatus === "success" ? "text-green-500" : "text-red-500"}`}>
                  {saveMessage}
                </p>
              )}
            </form>
          </CardContent>
        </Card>

        {/* Latency Triangulation Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Signal className="size-4" />Latency Triangulation
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Status</span>
              {health.disable_latency_triangulation ? (
                <Badge className="bg-slate-500/15 text-slate-400 hover:bg-slate-500/15 border border-slate-500/30">Disabled</Badge>
              ) : (
                <Badge className="bg-emerald-500/15 text-emerald-500 hover:bg-emerald-500/15 border border-emerald-500/30">Enabled</Badge>
              )}
            </div>
            <div className="pt-2 border-t space-y-2">
              <Button
                variant="outline"
                size="sm"
                className={`w-full flex items-center justify-center gap-2 transition-colors ${
                  health.disable_latency_triangulation 
                    ? "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 border-emerald-500/30" 
                    : "text-rose-400 hover:text-rose-300 hover:bg-rose-950/20 border-rose-900/30"
                }`}
                onClick={() => handleToggleLatency(!health.disable_latency_triangulation)}
                disabled={isTogglingLatency}
              >
                {health.disable_latency_triangulation ? "Enable Triangulation" : "Disable Triangulation"}
              </Button>

              {latencyMessage && (
                <p className="mt-2 text-xs text-muted-foreground text-center text-wrap">
                  {latencyMessage}
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Data Lifecycle Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="size-4" />Data Lifecycle
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Raw event retention</span>
              <span>{health.raw_retention_days} days</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Last backup</span>
              <span>{health.last_backup_time ? formatDate(health.last_backup_time) : "No backup found"}</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
