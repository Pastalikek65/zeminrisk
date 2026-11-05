-- ZeminRisk Core PostGIS Initialization Schema
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_raster;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Schemas
CREATE SCHEMA IF NOT EXISTS seismic;
CREATE SCHEMA IF NOT EXISTS exposure;
CREATE SCHEMA IF NOT EXISTS network;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Fault lines table (MTA active faults)
CREATE TABLE IF NOT EXISTS seismic.active_faults (
    id SERIAL PRIMARY KEY,
    fault_code VARCHAR(64) NOT NULL,
    fault_name VARCHAR(255),
    slip_type VARCHAR(64),
    slip_rate_mm_yr DOUBLE PRECISION,
    geom GEOMETRY(MultiLineStringZ, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_active_faults_geom ON seismic.active_faults USING GIST (geom);

-- Seismic events (Live & Historical catalog)
CREATE TABLE IF NOT EXISTS seismic.events (
    id VARCHAR(64) PRIMARY KEY,
    provider VARCHAR(32) NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    magnitude DOUBLE PRECISION NOT NULL,
    mag_type VARCHAR(16) NOT NULL,
    depth_km DOUBLE PRECISION NOT NULL,
    location_desc TEXT,
    geom GEOMETRY(PointZ, 4326) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_seismic_events_geom ON seismic.events USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_seismic_events_time ON seismic.events (event_time DESC);

-- Building stock exposure with fragility taxonomy (GEM standard)
CREATE TABLE IF NOT EXISTS exposure.buildings (
    id BIGSERIAL PRIMARY KEY,
    h3_index VARCHAR(16),
    gem_taxonomy VARCHAR(64),
    stories INT,
    construction_year INT,
    replacement_cost_usd DOUBLE PRECISION,
    occupancy_night INT,
    occupancy_day INT,
    geom GEOMETRY(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_buildings_geom ON exposure.buildings USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_buildings_h3 ON exposure.buildings (h3_index);

-- Critical facilities (Hospitals, shelters, fire stations)
CREATE TABLE IF NOT EXISTS exposure.facilities (
    id SERIAL PRIMARY KEY,
    facility_type VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    bed_capacity INT DEFAULT 0,
    is_operational BOOLEAN DEFAULT TRUE,
    geom GEOMETRY(Point, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facilities_geom ON exposure.facilities USING GIST (geom);
