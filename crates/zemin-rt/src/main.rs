//! ZeminRisk Real-Time Event Processing Service.
//!
//! Listens to live seismic event streams (AFAD/EMSC) or replays historical disaster
//! scenarios (e.g. 2023 Kahramanmaraş M7.8 & M7.6), immediately generating
//! calibrated ShakeMaps, estimated impact metrics, and affected spatial perimeters.

use chrono::Utc;
use log::info;
use serde::{Deserialize, Serialize};
use std::time::Instant;
use zemin_core::{
    BoundingBox, EarthquakeSource, FaultMechanism, FaultRupture, GeoCoord, GmpeModel,
    ShakeMapRaster,
};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SeismicEvent {
    pub id: String,
    pub event_time: String,
    pub magnitude: f64,
    pub depth_km: f64,
    pub lat: f64,
    pub lon: f64,
    pub location_name: String,
    pub strike_slip: bool,
}

impl SeismicEvent {
    pub fn kahramanmaras_2023() -> Self {
        Self {
            id: "TURKEY_20230206_M78".to_string(),
            event_time: "2023-02-06T01:17:34Z".to_string(),
            magnitude: 7.8,
            depth_km: 10.0,
            lat: 37.174,
            lon: 37.085,
            location_name: "Pazarcık, Kahramanmaraş, Türkiye".to_string(),
            strike_slip: true,
        }
    }

    pub fn elbistan_2023() -> Self {
        Self {
            id: "TURKEY_20230206_M76".to_string(),
            event_time: "2023-02-06T10:24:49Z".to_string(),
            magnitude: 7.6,
            depth_km: 7.0,
            lat: 38.089,
            lon: 37.239,
            location_name: "Ekinözü / Elbistan, Kahramanmaraş, Türkiye".to_string(),
            strike_slip: true,
        }
    }
}

/// ShakeMap calculation runner
pub fn process_event(event: &SeismicEvent, grid_size: usize) -> (ShakeMapRaster, u128) {
    info!(
        "Processing seismic event {}: M{:.1} at ({:.3}, {:.3}) - {}",
        event.id, event.magnitude, event.lat, event.lon, event.location_name
    );

    let start = Instant::now();

    // Define impact perimeter (~200km radius around epicenter)
    let delta = 2.5; // degrees approx 275 km
    let bbox = BoundingBox::new(
        event.lat - delta,
        event.lat + delta,
        event.lon - delta,
        event.lon + delta,
    );

    let mech = if event.strike_slip {
        FaultMechanism::StrikeSlip
    } else {
        FaultMechanism::Normal
    };

    let source = EarthquakeSource::new(event.magnitude, event.depth_km, mech);

    let raster = if event.magnitude >= 7.0 && event.id.contains("M78") {
        let rupture = FaultRupture::east_anatolian_fault_2023();
        ShakeMapRaster::compute_with_rupture(
            &source,
            &rupture,
            &bbox,
            grid_size,
            grid_size,
            360.0,
            GmpeModel::AkkarBommer2014,
        )
    } else {
        let epicenter = GeoCoord::new(event.lat, event.lon);
        ShakeMapRaster::compute(
            &source,
            &epicenter,
            &bbox,
            grid_size,
            grid_size,
            360.0,
            GmpeModel::AkkarBommer2014,
        )
    };

    let duration_micros = start.elapsed().as_micros();
    (raster, duration_micros)
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    info!("=== ZeminRisk Real-Time Engine (zemin-rt) ===");
    info!("Timestamp: {}", Utc::now());

    let event = SeismicEvent::kahramanmaras_2023();
    let grid_dim = 100; // 100x100 = 10,000 grid points
    let (raster, elapsed_us) = process_event(&event, grid_dim);

    info!(
        "Computed 10,000 grid points in {:.2} ms ({:.1} pts/ms)",
        elapsed_us as f64 / 1000.0,
        10000.0 / (elapsed_us as f64 / 1000.0)
    );
    info!(
        "Peak Ground Acceleration (PGA): {:.3} g",
        raster.stats.max_pga_g
    );
    info!(
        "Peak Ground Velocity (PGV): {:.1} cm/s",
        raster.stats.max_pgv_cms
    );
    info!("Max Instrumental MMI: {:.2}", raster.stats.max_mmi);
    info!(
        "Estimated severe impact area (MMI >= VII): {:.1} km^2",
        raster.stats.area_mmi_gte_7_km2
    );

    Ok(())
}
