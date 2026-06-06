export type Summary = {
  total_visits: number;
  unique_visitors: number;
  returning_visitors: number;
  top_city: string | null;
  top_state: string | null;
  average_confidence: number;
};

export type TrendPoint = { period: string; visits: number; unique_visitors: number };
export type LocationPoint = {
  name: string; visits: number; unique_visitors: number; average_confidence: number;
};
export type RetentionPoint = {
  cohort: string; cohort_size: number; returned: number; retention_rate: number;
};
export type FrequencyPoint = { bucket: string; visitors: number };
export type LocationTrendPoint = { period: string; location: string; visits: number };
export type Visitor = {
  id: number; anonymous_id: string; first_seen: string; last_seen: string;
  total_visits: number; current_city: string | null; current_state: string | null;
  current_country: string | null; confidence_score: number;
};
export type Visit = {
  id: number; anonymous_id: string; timestamp: string; city: string | null;
  state: string | null; country: string | null; confidence_score: number;
  browser: string | null; os: string | null; device_type: string | null;
  network_type: string; is_anomalous: boolean; anomaly_reasons: string[] | null;
};
export type Page<T> = {
  items: T[]; meta: { page: number; page_size: number; total: number };
};
export type Health = {
  status: "healthy" | "degraded"; database_status: string; database_size_bytes: number;
  disk_used_percent: number; memory_used_percent: number; geoip_city_status: string;
  geoip_asn_status: string; last_backup_time: string | null; uptime_seconds: number;
  raw_retention_days: number;
};
