"use client";

import { Clock, Database, HardDrive, Map, MemoryStick, ShieldCheck, Globe, RefreshCw } from "lucide-react";
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

  function getGeoIPBadge(status: string) {
    switch (status) {
      case "up_to_date":
        return <Badge className="bg-emerald-500/15 text-emerald-500 hover:bg-emerald-500/15 border border-emerald-500/30">Up to date</Badge>;
      case "update_available":
        return <Badge className="bg-amber-500/15 text-amber-500 hover:bg-amber-500/15 border border-amber-500/30">Update available</Badge>;
      case "updating":
        return <Badge className="bg-blue-500/15 text-blue-500 hover:bg-blue-500/15 border border-blue-500/30 animate-pulse">Updating...</Badge>;
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
        <StatCard label="Disk usage" value={`${health.disk_used_percent.toFixed(1)}%`} icon={HardDrive} />
        <StatCard label="Memory usage" value={`${health.memory_used_percent.toFixed(1)}%`} icon={MemoryStick} />
        <StatCard 
          label="Uptime" 
          value={`${Math.floor(health.uptime_seconds / 3600)}h ${Math.floor((health.uptime_seconds % 3600) / 60)}m`} 
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
            <div className="pt-2 border-t">
              <Button 
                variant="outline" 
                size="sm" 
                className="w-full flex items-center justify-center gap-2"
                onClick={handleTriggerGeoIPUpdate}
                disabled={isGeoIPUpdating}
              >
                <RefreshCw className={`size-3.5 ${isGeoIPUpdating ? "animate-spin" : ""}`} />
                {isGeoIPUpdating ? "Updating..." : "Trigger Auto-Update"}
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
