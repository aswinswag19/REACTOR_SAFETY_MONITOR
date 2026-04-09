-- ============================================================
--  Supabase Database Schema
--  AR Nuclear Reactor Safety Monitor
--  Run this in: Supabase Dashboard → SQL Editor
-- ============================================================

-- ─── SENSOR READINGS TABLE ────────────────────────────────
CREATE TABLE IF NOT EXISTS readings (
  id              BIGSERIAL PRIMARY KEY,
  timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  temperature     REAL,
  humidity        REAL,
  gas_raw         INTEGER,
  gas_detected    BOOLEAN,
  uv_raw          INTEGER,
  uv_index        REAL,
  coolant_level   REAL,
  distance_cm     REAL,
  status          TEXT CHECK (status IN ('SAFE', 'WARNING', 'CRITICAL'))
);

-- Index for time-series queries
CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp DESC);

-- ─── ALERTS TABLE ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
  id            BIGSERIAL PRIMARY KEY,
  timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status        TEXT CHECK (status IN ('WARNING', 'CRITICAL')),
  reasons       TEXT,       -- JSON array as text
  temperature   REAL,
  gas_detected  BOOLEAN,
  uv_raw        INTEGER,
  coolant_level REAL
);

CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp DESC);

-- ─── ROW LEVEL SECURITY (Optional: enable for production) ─
-- ALTER TABLE readings ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE alerts   ENABLE ROW LEVEL SECURITY;

-- ─── REALTIME (Enable for live updates) ───────────────────
-- In Supabase Dashboard → Database → Replication
-- Enable replication on 'readings' and 'alerts' tables

-- ─── SAMPLE TEST DATA ─────────────────────────────────────
INSERT INTO readings (temperature, humidity, gas_raw, gas_detected, uv_raw, uv_index, coolant_level, distance_cm, status)
VALUES
  (32.5, 45.2,  150, false, 200, 2.15, 85.0, 25.0, 'SAFE'),
  (45.1, 48.0,  180, false, 310, 3.33, 78.5, 27.3, 'SAFE'),
  (52.3, 51.3,  420, true,  450, 4.84, 65.2, 31.2, 'WARNING'),
  (61.0, 55.0,  650, true,  600, 6.45, 45.0, 38.5, 'WARNING'),
  (73.5, 58.1,  800, true,  750, 8.06, 12.0, 62.0, 'CRITICAL'),
  (35.0, 43.0,  120, false, 180, 1.94, 90.0, 22.0, 'SAFE');

-- ─── USEFUL QUERIES ───────────────────────────────────────

-- Get last 20 readings
-- SELECT * FROM readings ORDER BY timestamp DESC LIMIT 20;

-- Get all critical events
-- SELECT * FROM alerts WHERE status = 'CRITICAL' ORDER BY timestamp DESC;

-- Average temperature today
-- SELECT AVG(temperature) FROM readings WHERE timestamp > NOW() - INTERVAL '24 hours';

-- Count readings by status
-- SELECT status, COUNT(*) FROM readings GROUP BY status;

-- ─── USERS TABLE (for login/signup) ──────────────────────
CREATE TABLE IF NOT EXISTS users (
  id             BIGSERIAL PRIMARY KEY,
  email          TEXT UNIQUE NOT NULL,
  name           TEXT NOT NULL,
  password_hash  TEXT NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Remove uv_raw / uv_index columns from readings if upgrading:
-- ALTER TABLE readings DROP COLUMN IF EXISTS uv_raw;
-- ALTER TABLE readings DROP COLUMN IF EXISTS uv_index;
