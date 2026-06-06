# Database schema

```mermaid
erDiagram
    VISITORS ||--o{ VISIT_LOGS : has
    VISITORS ||--o{ DAILY_STAT_VISITORS : counted_in
    AGGREGATED_DAILY_STATS ||--o{ DAILY_STAT_VISITORS : includes

    VISITORS {
      int id PK
      string visitor_hash UK
      datetime first_seen
      datetime last_seen
      int total_visits
      string current_city
      string current_state
      string current_country
      int confidence_score
    }
    VISIT_LOGS {
      int id PK
      int visitor_id FK
      datetime timestamp
      string city
      string state
      string country
      int confidence_score
      string browser
      string os
      string device_type
      string network_type
      int asn
      string network_organization
      bool is_anomalous
      json anomaly_reasons
    }
    AGGREGATED_DAILY_STATS {
      int id PK
      date date
      string city
      string state
      int visit_count
      int unique_visitors
    }
    DAILY_STAT_VISITORS {
      int daily_stat_id PK,FK
      int visitor_id PK,FK
    }
    AUDIT_LOGS {
      int id PK
      datetime timestamp
      string action
      string actor
      string outcome
      json details
    }
```

Alembic owns schema changes. The backend runs `alembic upgrade head` before
starting. Important query paths are indexed by visitor hash, visitor last-seen,
event timestamp, visitor/timestamp, aggregate date, and audit timestamp.

