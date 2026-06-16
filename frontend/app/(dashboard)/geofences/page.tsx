"use client";

import { useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import {
  Plus,
  Trash2,
  Save,
  Layers,
  Settings,
  Compass,
  AlertCircle,
  CheckCircle,
  Eye,
  EyeOff,
  Navigation,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface Geofence {
  id: number;
  name: string;
  type: string;
  center_latitude: number | null;
  center_longitude: number | null;
  radius_meters: number | null;
  coordinates: number[][] | null;
  is_active: boolean;
}

export default function GeofencesPage() {
  const [geofences, setGeofences] = useState<Geofence[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Telegram Config state
  const [botToken, setBotToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [saveTelegramStatus, setSaveTelegramStatus] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [telegramMessage, setTelegramMessage] = useState("");

  // Create Geofence Form state
  const [name, setName] = useState("");
  const [type, setType] = useState<"circle" | "polygon">("circle");
  const [radius, setRadius] = useState(500); // meters
  const [circleCenter, setCircleCenter] = useState<{ lat: number; lng: number } | null>(null);
  const [polygonVertices, setPolygonVertices] = useState<{ lat: number; lng: number }[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const [createMessage, setCreateMessage] = useState("");

  // Leaflet Map References
  const mapInstance = useRef<any>(null);
  const tempDrawLayer = useRef<any>(null);
  const geofencesGroup = useRef<any>(null);

  // Load initial settings and geofences
  useEffect(() => {
    Promise.all([
      api<any>("/system/health"),
      api<Geofence[]>("/system/geofences"),
    ])
      .then(([health, gfList]) => {
        setBotToken(health.telegram_bot_token || "");
        setChatId(health.telegram_chat_id || "");
        setGeofences(gfList);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load page data.");
        setLoading(false);
      });
  }, []);

  // Initialize Leaflet Map
  useEffect(() => {
    if (loading || error) return;

    // Load Leaflet resources dynamically from CDN
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(link);

    const script = document.createElement("script");
    script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.onload = () => {
      initMap();
    };
    document.head.appendChild(script);

    return () => {
      document.head.removeChild(link);
      document.head.removeChild(script);
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, [loading, error]);

  // Redraw geofences when list changes
  useEffect(() => {
    if (!mapInstance.current || !geofencesGroup.current) return;
    drawExistingGeofences();
  }, [geofences]);

  // Redraw current drawing when shape status changes
  useEffect(() => {
    if (!mapInstance.current) return;
    updateTemporaryDrawing();
  }, [type, circleCenter, polygonVertices, radius]);

  const initMap = () => {
    const L = (window as any).L;
    if (!L || mapInstance.current) return;

    // Center map around New Delhi/India default or first geofence
    let defaultCenter: [number, number] = [20.5937, 78.9629];
    let defaultZoom = 5;

    if (geofences.length > 0) {
      const first = geofences[0];
      if (
        first.type === "circle" &&
        first.center_latitude !== null &&
        first.center_longitude !== null
      ) {
        defaultCenter = [first.center_latitude, first.center_longitude];
        defaultZoom = 13;
      } else if (
        first.type === "polygon" &&
        first.coordinates &&
        first.coordinates.length > 0
      ) {
        const firstPoint = first.coordinates[0];
        if (firstPoint && firstPoint.length >= 2) {
          defaultCenter = [firstPoint[0], firstPoint[1]];
          defaultZoom = 13;
        }
      }
    }

    const map = L.map("geofence-map", {
      zoomControl: true,
      scrollWheelZoom: true,
    }).setView(defaultCenter, defaultZoom);

    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: "abcd",
      maxZoom: 20,
    }).addTo(map);

    mapInstance.current = map;
    geofencesGroup.current = L.featureGroup().addTo(map);
    tempDrawLayer.current = L.featureGroup().addTo(map);

    // Click handler to register shapes
    map.on("click", (e: any) => {
      const { lat, lng } = e.latlng;
      if (type === "circle") {
        setCircleCenter({ lat, lng });
      } else {
        setPolygonVertices((prev) => [...prev, { lat, lng }]);
      }
    });

    drawExistingGeofences();
  };

  const drawExistingGeofences = () => {
    const L = (window as any).L;
    if (!L || !mapInstance.current || !geofencesGroup.current) return;

    geofencesGroup.current.clearLayers();

    geofences.forEach((gf) => {
      if (!gf.is_active) return;

      const color = gf.type === "circle" ? "#10b981" : "#6366f1"; // Green for circles, Purple for polygons

      if (
        gf.type === "circle" &&
        gf.center_latitude !== null &&
        gf.center_longitude !== null &&
        gf.radius_meters !== null
      ) {
        const circle = L.circle([gf.center_latitude, gf.center_longitude], {
          radius: gf.radius_meters,
          color: color,
          fillColor: color,
          fillOpacity: 0.15,
          weight: 2,
        });
        circle.bindPopup(`<b>${gf.name}</b><br/>Type: Circle<br/>Radius: ${gf.radius_meters}m`);
        geofencesGroup.current.addLayer(circle);
      } else if (gf.type === "polygon" && gf.coordinates) {
        const polygon = L.polygon(gf.coordinates as [number, number][], {
          color: color,
          fillColor: color,
          fillOpacity: 0.15,
          weight: 2,
        });
        polygon.bindPopup(`<b>${gf.name}</b><br/>Type: Polygon`);
        geofencesGroup.current.addLayer(polygon);
      }
    });
  };

  const updateTemporaryDrawing = () => {
    const L = (window as any).L;
    if (!L || !tempDrawLayer.current) return;

    tempDrawLayer.current.clearLayers();

    // Pulse marker divIcon
    const pulseMarkerIcon = L.divIcon({
      className: "custom-pulse-marker",
      html: `<div class="relative flex items-center justify-center"><div class="absolute inline-flex h-4 w-4 rounded-full bg-emerald-400 opacity-75 animate-ping"></div><div class="relative rounded-full h-3.5 w-3.5 bg-emerald-500 border-2 border-white shadow"></div></div>`,
      iconSize: [16, 16],
      iconAnchor: [8, 8],
    });

    const blueMarkerIcon = L.divIcon({
      className: "custom-pulse-marker-blue",
      html: `<div class="relative flex items-center justify-center"><div class="absolute inline-flex h-4 w-4 rounded-full bg-indigo-400 opacity-75 animate-ping"></div><div class="relative rounded-full h-3.5 w-3.5 bg-indigo-500 border-2 border-white shadow"></div></div>`,
      iconSize: [16, 16],
      iconAnchor: [8, 8],
    });

    if (type === "circle" && circleCenter) {
      // Draw center marker
      L.marker([circleCenter.lat, circleCenter.lng], { icon: pulseMarkerIcon }).addTo(tempDrawLayer.current);
      // Draw circle overlay
      L.circle([circleCenter.lat, circleCenter.lng], {
        radius: radius,
        color: "#10b981",
        fillColor: "#10b981",
        fillOpacity: 0.1,
        weight: 1.5,
        dashArray: "4, 4",
      }).addTo(tempDrawLayer.current);
    } else if (type === "polygon" && polygonVertices.length > 0) {
      // Draw markers for all vertices
      polygonVertices.forEach((v) => {
        L.marker([v.lat, v.lng], { icon: blueMarkerIcon }).addTo(tempDrawLayer.current);
      });

      if (polygonVertices.length >= 2) {
        const coords = polygonVertices.map((v) => [v.lat, v.lng] as [number, number]);
        if (polygonVertices.length >= 3) {
          L.polygon(coords, {
            color: "#6366f1",
            fillColor: "#6366f1",
            fillOpacity: 0.1,
            weight: 1.5,
            dashArray: "4, 4",
          }).addTo(tempDrawLayer.current);
        } else {
          // Draw simple polyline for 2 points
          L.polyline(coords, {
            color: "#6366f1",
            weight: 1.5,
            dashArray: "4, 4",
          }).addTo(tempDrawLayer.current);
        }
      }
    }
  };

  const clearDrawing = () => {
    setCircleCenter(null);
    setPolygonVertices([]);
  };

  const handleSaveTelegramConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveTelegramStatus("saving");
    setTelegramMessage("");

    try {
      const res = await api<{ success: boolean; telegram_bot_token: string; telegram_chat_id: string; env_updated: boolean }>("/system/config/telegram", {
        method: "POST",
        body: JSON.stringify({
          telegram_bot_token: botToken,
          telegram_chat_id: chatId,
        }),
      });

      if (res.success) {
        setSaveTelegramStatus("success");
        setTelegramMessage(
          res.env_updated
            ? "✅ Credentials updated and saved to disk!"
            : "⚠️ Applied in-memory, but failed to write to .env. Will reset on restart."
        );
        setTimeout(() => setTelegramMessage(""), 5000);
      } else {
        setSaveTelegramStatus("error");
        setTelegramMessage("❌ Failed to update settings.");
      }
    } catch (err: any) {
      setSaveTelegramStatus("error");
      setTelegramMessage(err.message || "❌ Error saving Telegram configurations.");
    }
  };

  const handleCreateGeofence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    if (type === "circle" && !circleCenter) {
      setCreateMessage("❌ Please click on the map to define the circle center.");
      return;
    }
    if (type === "polygon" && polygonVertices.length < 3) {
      setCreateMessage("❌ Polygons require at least 3 vertices. Click on the map to place points.");
      return;
    }

    setIsCreating(true);
    setCreateMessage("");

    const payload = {
      name,
      type,
      center_latitude: type === "circle" ? circleCenter?.lat : null,
      center_longitude: type === "circle" ? circleCenter?.lng : null,
      radius_meters: type === "circle" ? radius : null,
      coordinates: type === "polygon" ? polygonVertices.map((v) => [v.lat, v.lng]) : null,
    };

    try {
      const gf = await api<Geofence>("/system/geofences", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setGeofences((prev) => [gf, ...prev]);
      setName("");
      clearDrawing();
      setCreateMessage("✅ Boundary created successfully!");
      setTimeout(() => setCreateMessage(""), 4000);
    } catch (err: any) {
      setCreateMessage(err.message || "❌ Failed to create geofence.");
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteGeofence = async (id: number) => {
    try {
      await api(`/system/geofences/${id}`, { method: "DELETE" });
      setGeofences((prev) => prev.filter((gf) => gf.id !== id));
    } catch (err: any) {
      alert(err.message || "Failed to delete geofence.");
    }
  };

  const handleToggleGeofence = async (id: number) => {
    try {
      const res = await api<{ success: boolean; is_active: boolean }>(`/system/geofences/${id}/toggle`, {
        method: "POST",
      });
      setGeofences((prev) =>
        prev.map((gf) => (gf.id === id ? { ...gf, is_active: res.is_active } : gf))
      );
    } catch (err: any) {
      alert(err.message || "Failed to toggle geofence.");
    }
  };

  if (loading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent mx-auto" />
          <p className="mt-4 text-muted-foreground text-sm">Loading geofencing systems...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title="Geofences & Alerts"
        description="Set circular or polygon coordinates. Visitors who enter these areas will trigger special notifications."
      />

      {error && (
        <Card className="mb-6 border-rose-500/30 bg-rose-500/10">
          <CardContent className="flex items-center gap-3 pt-6 text-rose-500">
            <AlertCircle className="size-5" />
            <p className="text-sm font-medium">{error}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Columns - Map & List */}
        <div className="space-y-6 lg:col-span-2">
          {/* Leaflet Map Card */}
          <Card className="overflow-hidden">
            <CardHeader className="pb-3 border-b bg-card/50">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <Compass className="size-4 text-emerald-500" />
                    Interactive Boundary Map
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">
                    {type === "circle"
                      ? "Click on the map to define the center point of your circle boundary."
                      : "Click multiple points on the map to add vertices and form a polygon boundary."}
                  </p>
                </div>
                {(circleCenter || polygonVertices.length > 0) && (
                  <Button variant="outline" size="sm" onClick={clearDrawing} className="text-xs h-8">
                    Clear Drawing
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-0 relative bg-zinc-950">
              <div id="geofence-map" className="h-[460px] w-full z-0" />
            </CardContent>
          </Card>

          {/* Active Geofences List */}
          <Card>
            <CardHeader className="pb-3 border-b bg-card/50">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Layers className="size-4 text-indigo-500" />
                Active Geofence Boundaries ({geofences.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              {geofences.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-sm text-muted-foreground">No geofences created yet. Draw one on the map above.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {geofences.map((gf) => {
                    const color = gf.type === "circle" ? "text-emerald-500 border-emerald-500/30 bg-emerald-500/10" : "text-indigo-500 border-indigo-500/30 bg-indigo-500/10";
                    return (
                      <div
                        key={gf.id}
                        className="flex items-center justify-between p-4 border rounded-xl bg-card/30 backdrop-blur-sm gap-4 transition-all hover:bg-card/50"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm truncate">{gf.name}</span>
                            <Badge className={`text-[10px] uppercase font-semibold border ${color}`}>
                              {gf.type}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground mt-1 truncate">
                            {gf.type === "circle"
                              ? `Center: ${gf.center_latitude !== null ? gf.center_latitude.toFixed(4) : "N/A"}, ${gf.center_longitude !== null ? gf.center_longitude.toFixed(4) : "N/A"} | Radius: ${gf.radius_meters}m`
                              : `${gf.coordinates ? gf.coordinates.length : 0} Vertices: ${gf.coordinates ? gf.coordinates.slice(0, 2).map((c) => c.map((v) => v.toFixed(3)).join(", ")).join(" -> ") : ""}...`}
                          </p>
                        </div>

                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 text-xs"
                            onClick={() => handleToggleGeofence(gf.id)}
                          >
                            {gf.is_active ? (
                              <span className="text-emerald-500 flex items-center gap-1 font-medium">● Active</span>
                            ) : (
                              <span className="text-muted-foreground flex items-center gap-1">○ Inactive</span>
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-muted-foreground hover:text-rose-500 size-8"
                            onClick={() => handleDeleteGeofence(gf.id)}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column - Forms */}
        <div className="space-y-6">
          {/* Telegram Settings */}
          <Card>
            <CardHeader className="pb-3 border-b bg-card/50">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Settings className="size-4 text-emerald-500" />
                Telegram Notifications
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                Configure your Telegram Bot API credentials to receive alerts on new visits.
              </p>
            </CardHeader>
            <CardContent className="pt-6">
              <form onSubmit={handleSaveTelegramConfig} className="space-y-4">
                <div className="space-y-1.5">
                  <label htmlFor="bot-token" className="text-xs font-medium block">Telegram Bot Token</label>
                  <div className="relative">
                    <Input
                      id="bot-token"
                      type={showToken ? "text" : "password"}
                      value={botToken}
                      onChange={(e) => setBotToken(e.target.value)}
                      placeholder="1234567890:ABCDefGhI..."
                      className="pr-10 text-xs h-9 bg-background/50 border-input"
                    />
                    <button
                      type="button"
                      onClick={() => setShowToken(!showToken)}
                      className="absolute right-3 top-2.5 text-muted-foreground hover:text-foreground"
                    >
                      {showToken ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="chat-id" className="text-xs font-medium block">Telegram Chat ID</label>
                  <Input
                    id="chat-id"
                    value={chatId}
                    onChange={(e) => setChatId(e.target.value)}
                    placeholder="-100123456789"
                    className="text-xs h-9 bg-background/50 border-input"
                  />
                </div>

                <Button
                  type="submit"
                  disabled={saveTelegramStatus === "saving"}
                  className="w-full text-xs font-medium h-9"
                >
                  <Save className="size-3.5 mr-2" />
                  {saveTelegramStatus === "saving" ? "Saving..." : "Save Telegram Settings"}
                </Button>

                {telegramMessage && (
                  <div
                    className={`p-3 rounded-lg border text-xs flex items-center gap-2 ${
                      saveTelegramStatus === "success"
                        ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                        : "bg-rose-500/10 border-rose-500/20 text-rose-400"
                    }`}
                  >
                    {saveTelegramStatus === "success" ? (
                      <CheckCircle className="size-4 shrink-0" />
                    ) : (
                      <AlertCircle className="size-4 shrink-0" />
                    )}
                    <p className="leading-normal">{telegramMessage}</p>
                  </div>
                )}
              </form>
            </CardContent>
          </Card>

          {/* Add Geofence */}
          <Card>
            <CardHeader className="pb-3 border-b bg-card/50">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Plus className="size-4 text-indigo-500" />
                Add Boundary Geofence
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                Fill details and draw or click on the map to define the boundary.
              </p>
            </CardHeader>
            <CardContent className="pt-6">
              <form onSubmit={handleCreateGeofence} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium block">Boundary Shape Type</label>
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      type="button"
                      variant={type === "circle" ? "default" : "outline"}
                      onClick={() => {
                        setType("circle");
                        clearDrawing();
                      }}
                      className="text-xs h-9 font-medium"
                    >
                      Circle
                    </Button>
                    <Button
                      type="button"
                      variant={type === "polygon" ? "default" : "outline"}
                      onClick={() => {
                        setType("polygon");
                        clearDrawing();
                      }}
                      className="text-xs h-9 font-medium"
                    >
                      Polygon
                    </Button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="gf-name" className="text-xs font-medium block">Boundary Name</label>
                  <Input
                    id="gf-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Office, Home Circle"
                    className="text-xs h-9 bg-background/50 border-input"
                    required
                  />
                </div>

                {type === "circle" && (
                  <div className="space-y-1.5">
                    <label htmlFor="gf-radius" className="text-xs font-medium block">Circle Radius (Meters)</label>
                    <Input
                      id="gf-radius"
                      type="number"
                      value={radius}
                      onChange={(e) => setRadius(Math.max(1, parseInt(e.target.value) || 0))}
                      placeholder="500"
                      className="text-xs h-9 bg-background/50 border-input"
                      required
                    />
                  </div>
                )}

                {/* Coordinate Previews */}
                <div className="p-3.5 border rounded-xl bg-muted/30 text-[11px] font-mono leading-relaxed space-y-1 text-muted-foreground">
                  <div className="flex items-center gap-1.5 text-foreground font-semibold font-sans mb-1 text-xs">
                    <Navigation className="size-3 text-indigo-500" />
                    Boundary Coordinates
                  </div>
                  {type === "circle" ? (
                    circleCenter ? (
                      <div>
                        Lat: {circleCenter.lat.toFixed(6)}<br />
                        Lng: {circleCenter.lng.toFixed(6)}
                      </div>
                    ) : (
                      <span className="italic text-muted-foreground/60">Click on the map to define the circle center.</span>
                    )
                  ) : polygonVertices.length > 0 ? (
                    <div>
                      {polygonVertices.map((v, idx) => (
                        <div key={idx}>
                          P{idx + 1}: {v.lat.toFixed(5)}, {v.lng.toFixed(5)}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span className="italic text-muted-foreground/60">Click points on the map to build your polygon.</span>
                  )}
                </div>

                <Button
                  type="submit"
                  disabled={isCreating}
                  className="w-full text-xs font-medium h-9 bg-indigo-600 hover:bg-indigo-700 text-white"
                >
                  <Plus className="size-3.5 mr-2" />
                  {isCreating ? "Creating..." : "Create Boundary Geofence"}
                </Button>

                {createMessage && (
                  <div
                    className={`p-3 rounded-lg border text-xs flex items-center gap-2 ${
                      createMessage.startsWith("✅")
                        ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                        : "bg-rose-500/10 border-rose-500/20 text-rose-400"
                    }`}
                  >
                    <p className="leading-normal">{createMessage}</p>
                  </div>
                )}
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
