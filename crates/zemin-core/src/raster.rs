//! Parallel Grid Raster Engine for ShakeMap generation.

use crate::gmpe::{
    calculate_ground_motion, EarthquakeSource, GmpeModel, GroundMotionIntensity, SiteCondition,
};
use crate::spatial::{BoundingBox, GeoCoord};
use rayon::prelude::*;
use serde::{Deserialize, Serialize};

/// Summary statistics of a generated ShakeMap
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShakeMapStats {
    pub max_pga_g: f64,
    pub max_pgv_cms: f64,
    pub max_mmi: f64,
    /// Estimated area (km^2) exceeding MMI VII (severe shaking / potential damage)
    pub area_mmi_gte_7_km2: f64,
    /// Total number of grid points computed
    pub total_points: usize,
}

/// A 2D ShakeMap raster grid
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShakeMapRaster {
    pub bbox: BoundingBox,
    pub nrows: usize,
    pub ncols: usize,
    /// Flat row-major array of PGA values (in g)
    pub pga: Vec<f32>,
    /// Flat row-major array of PGV values (in cm/s)
    pub pgv: Vec<f32>,
    /// Flat row-major array of MMI values (1.0 - 10.0)
    pub mmi: Vec<f32>,
    pub stats: ShakeMapStats,
}

impl ShakeMapRaster {
    /// Compute a parallel ShakeMap across the designated bounding box.
    pub fn compute(
        source: &EarthquakeSource,
        epicenter: &GeoCoord,
        bbox: &BoundingBox,
        nrows: usize,
        ncols: usize,
        default_vs30: f64,
        model: GmpeModel,
    ) -> Self {
        let total_points = nrows * ncols;
        let coords = bbox.generate_grid(nrows, ncols);

        // Approximate cell area in km^2
        let lat_dist = (bbox.max_lat - bbox.min_lat) * 111.0;
        let avg_lat = ((bbox.min_lat + bbox.max_lat) / 2.0).to_radians();
        let lon_dist = (bbox.max_lon - bbox.min_lon) * 111.0 * avg_lat.cos();
        let cell_area_km2 = if total_points > 0 {
            (lat_dist * lon_dist) / (total_points as f64)
        } else {
            0.0
        };

        let site = SiteCondition::new(default_vs30);

        // Parallel map over grid points using Rayon
        let results: Vec<GroundMotionIntensity> = coords
            .par_iter()
            .map(|coord| {
                let r_jb = epicenter.distance_haversine_km(coord);
                calculate_ground_motion(source, &site, r_jb, model)
            })
            .collect();

        let mut pga = Vec::with_capacity(total_points);
        let mut pgv = Vec::with_capacity(total_points);
        let mut mmi = Vec::with_capacity(total_points);

        let mut max_pga: f64 = 0.0;
        let mut max_pgv: f64 = 0.0;
        let mut max_mmi: f64 = 0.0;
        let mut points_mmi_gte_7 = 0;

        for res in results {
            pga.push(res.pga_g as f32);
            pgv.push(res.pgv_cms as f32);
            mmi.push(res.mmi as f32);

            if res.pga_g > max_pga {
                max_pga = res.pga_g;
            }
            if res.pgv_cms > max_pgv {
                max_pgv = res.pgv_cms;
            }
            if res.mmi > max_mmi {
                max_mmi = res.mmi;
            }
            if res.mmi >= 7.0 {
                points_mmi_gte_7 += 1;
            }
        }

        let area_mmi_gte_7_km2 = (points_mmi_gte_7 as f64) * cell_area_km2;

        Self {
            bbox: *bbox,
            nrows,
            ncols,
            pga,
            pgv,
            mmi,
            stats: ShakeMapStats {
                max_pga_g: max_pga,
                max_pgv_cms: max_pgv,
                max_mmi,
                area_mmi_gte_7_km2,
                total_points,
            },
        }
    }

    /// Exports MMI contour points above given threshold as GeoJSON FeatureCollection
    pub fn to_geojson_features(&self, min_mmi: f32) -> serde_json::Value {
        let mut features = Vec::new();
        let lat_step = (self.bbox.max_lat - self.bbox.min_lat) / (self.nrows.max(2) - 1) as f64;
        let lon_step = (self.bbox.max_lon - self.bbox.min_lon) / (self.ncols.max(2) - 1) as f64;

        for r in 0..self.nrows {
            let lat = self.bbox.min_lat + (r as f64) * lat_step;
            for c in 0..self.ncols {
                let idx = r * self.ncols + c;
                let mmi_val = self.mmi[idx];
                if mmi_val >= min_mmi {
                    let lon = self.bbox.min_lon + (c as f64) * lon_step;
                    let feature = serde_json::json!({
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat]
                        },
                        "properties": {
                            "mmi": mmi_val,
                            "pga_g": self.pga[idx],
                            "pgv_cms": self.pgv[idx]
                        }
                    });
                    features.push(feature);
                }
            }
        }

        serde_json::json!({
            "type": "FeatureCollection",
            "metadata": {
                "max_pga_g": self.stats.max_pga_g,
                "max_mmi": self.stats.max_mmi,
                "area_mmi_gte_7_km2": self.stats.area_mmi_gte_7_km2
            },
            "features": features
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::gmpe::FaultMechanism;

    #[test]
    fn test_shakemap_raster_computation() {
        let epicenter = GeoCoord::new(37.174, 37.085);
        let source = EarthquakeSource::new(7.8, 10.0, FaultMechanism::StrikeSlip);
        // Region encompassing SE Turkey (Hatay, Maraş, Antep, Adıyaman)
        let bbox = BoundingBox::new(35.5, 38.5, 35.5, 39.0);

        let raster = ShakeMapRaster::compute(
            &source,
            &epicenter,
            &bbox,
            50, // 50 rows
            50, // 50 cols = 2500 grid points
            360.0,
            GmpeModel::AkkarBommer2014,
        );

        assert_eq!(raster.pga.len(), 2500);
        assert_eq!(raster.stats.total_points, 2500);
        assert!(raster.stats.max_pga_g > 0.4);
        assert!(raster.stats.max_mmi >= 8.0);
        assert!(raster.stats.area_mmi_gte_7_km2 > 1000.0);

        // Test GeoJSON generation
        let geojson = raster.to_geojson_features(7.0);
        let features = geojson["features"].as_array().unwrap();
        assert!(!features.is_empty(), "Should have points with MMI >= 7.0");
    }
}
