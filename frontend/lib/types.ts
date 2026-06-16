export type Summary = {
  total_visits: number;
  unique_visitors: number;
  returning_visitors: number;
  crawler_visits: number;
  top_country: string | null;
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
export type CrawlerPoint = { crawler_type: string; visits: number; last_seen: string | null };
export type Visitor = {
  id: number; anonymous_id: string; first_seen: string; last_seen: string;
  total_visits: number; current_city: string | null; current_state: string | null;
  current_country: string | null; confidence_score: number; country_confidence_score: number;
  state_confidence_score: number; city_confidence_score: number; current_asn: number | null;
  current_isp: string | null; current_network_type: string; current_location_source: string;
  classification: string; classification_confidence: number; classification_reason: string | null;
  current_country_confidence: string; current_state_confidence: string; current_city_confidence: string;
  current_location_confidence: string;
};
export type Visit = {
  id: number; anonymous_id: string; timestamp: string; city: string | null;
  state: string | null; country: string | null; confidence_score: number;
  country_confidence_score: number; state_confidence_score: number; city_confidence_score: number;
  location_source: string; location_source_detail: string | null;
  browser: string | null; os: string | null; device_type: string | null;
  network_type: string; asn: number | null; isp: string | null; network_organization: string | null;
  geolocation_accuracy_meters: number | null; is_anomalous: boolean; anomaly_reasons: string[] | null;
  tracking_status: string; tracking_failure_reason: string | null;
  classification: string; classification_confidence: number; classification_reason: string | null;
  country_confidence: string; state_confidence: string; city_confidence: string;
  location_confidence: string;
  cores: number | null;
  memory: number | null;
  gpu: string | null;
  rtt: number | null;
  downlink: number | null;
  save_data: boolean | null;
  has_private_ip: boolean | null;
  ping_jitter: number | null;
  screen_resolution: string | null;
  canvas_hash: string | null;
  webgl_hash: string | null;
};
export type Page<T> = {
  items: T[]; meta: { page: number; page_size: number; total: number };
};
export type Health = {
  status: "healthy" | "degraded"; database_status: string; database_size_bytes: number;
  disk_used_percent: number; memory_used_percent: number;
  memory_used_bytes: number; memory_total_bytes: number;
  disk_used_bytes: number; disk_total_bytes: number;
  geoip_city_status: string;
  geoip_asn_status: string;
  disable_maxmind_db: boolean;
  disable_latency_triangulation: boolean;
  last_backup_time: string | null; uptime_seconds: number;
  raw_retention_days: number; redirect_target_url: string; geoip_update_in_progress: boolean;
  geoip_last_error: string | null;
  telegram_bot_token: string | null;
  telegram_chat_id: string | null;
};

