-- Storm Forecasts V2 Table - Proper schema for V49 Storm Predictor
-- Run this in Supabase SQL Editor (Dashboard > SQL Editor)

CREATE TABLE IF NOT EXISTS storm_forecasts_v2 (
    id TEXT PRIMARY KEY,
    metro TEXT NOT NULL,
    day INTEGER NOT NULL,
    risk_level TEXT NOT NULL,
    risk_rank INTEGER NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_storm_forecasts_v2_metro_day ON storm_forecasts_v2(metro, day);
CREATE INDEX IF NOT EXISTS idx_storm_forecasts_v2_day_risk ON storm_forecasts_v2(day, risk_rank);

-- Enable RLS (optional - for future multi-tenant)
-- ALTER TABLE storm_forecasts_v2 ENABLE ROW LEVEL SECURITY;