//! Spatial geometries and geodetic distance computations.

use serde::{Deserialize, Serialize};

/// Earth radius in kilometers (WGS-84 mean radius)
pub const EARTH_RADIUS_KM: f64 = 6371.0088;

/// Geographic coordinate in decimal degrees.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct GeoCoord {
    pub lat: f64,
    pub lon: f64,
}

impl GeoCoord {
    #[inline]
    pub const fn new(lat: f64, lon: f64) -> Self {
        Self { lat, lon }
    }

    /// Calculate great-circle distance to another coordinate using the Haversine formula.
    /// Returns distance in kilometers.
    #[inline]
    pub fn distance_haversine_km(&self, other: &GeoCoord) -> f64 {
        let lat1_rad = self.lat.to_radians();
        let lat2_rad = other.lat.to_radians();
        let dlat = (other.lat - self.lat).to_radians();
        let dlon = (other.lon - self.lon).to_radians();

        let a = (dlat / 2.0).sin().powi(2)
            + lat1_rad.cos() * lat2_rad.cos() * (dlon / 2.0).sin().powi(2);
        let c = 2.0 * a.sqrt().atan2((1.0 - a).sqrt());

        EARTH_RADIUS_KM * c
    }

    /// Computes hypocentral distance (R_hypo) in kilometers given source depth (km).
    #[inline]
    pub fn hypocentral_distance_km(&self, other: &GeoCoord, depth_km: f64) -> f64 {
        let repi = self.distance_haversine_km(other);
        (repi.powi(2) + depth_km.powi(2)).sqrt()
    }
}

/// Bounding box defined by min/max latitudes and longitudes.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct BoundingBox {
    pub min_lat: f64,
    pub max_lat: f64,
    pub min_lon: f64,
    pub max_lon: f64,
}

impl BoundingBox {
    pub fn new(min_lat: f64, max_lat: f64, min_lon: f64, max_lon: f64) -> Self {
        assert!(min_lat <= max_lat, "min_lat must be <= max_lat");
        assert!(min_lon <= max_lon, "min_lon must be <= max_lon");
        Self {
            min_lat,
            max_lat,
            min_lon,
            max_lon,
        }
    }

    /// Generate an equirectangular grid of points inside this bounding box.
    pub fn generate_grid(&self, nrows: usize, ncols: usize) -> Vec<GeoCoord> {
        let mut grid = Vec::with_capacity(nrows * ncols);
        let lat_step = if nrows > 1 {
            (self.max_lat - self.min_lat) / (nrows - 1) as f64
        } else {
            0.0
        };
        let lon_step = if ncols > 1 {
            (self.max_lon - self.min_lon) / (ncols - 1) as f64
        } else {
            0.0
        };

        for r in 0..nrows {
            let lat = self.min_lat + (r as f64) * lat_step;
            for c in 0..ncols {
                let lon = self.min_lon + (c as f64) * lon_step;
                grid.push(GeoCoord::new(lat, lon));
            }
        }
        grid
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use approx::assert_relative_eq;

    #[test]
    fn test_distance_kahramanmaras_to_antakya() {
        // Epicenter 2023 Kahramanmaraş M7.8 (approx 37.174, 37.085)
        let epicenter = GeoCoord::new(37.174, 37.085);
        // Antakya city center (approx 36.202, 36.160)
        let antakya = GeoCoord::new(36.202, 36.160);

        let dist = epicenter.distance_haversine_km(&antakya);
        // Distance is ~135-145 km
        assert!(dist > 130.0 && dist < 150.0, "Calculated distance: {dist}");

        let rhypo = epicenter.hypocentral_distance_km(&antakya, 10.0);
        assert!(rhypo > dist);
        assert_relative_eq!((dist.powi(2) + 100.0).sqrt(), rhypo, epsilon = 1e-4);
    }

    #[test]
    fn test_grid_generation() {
        let bbox = BoundingBox::new(36.0, 38.0, 35.0, 37.0);
        let grid = bbox.generate_grid(3, 3);
        assert_eq!(grid.len(), 9);
        assert_eq!(grid[0], GeoCoord::new(36.0, 35.0));
        assert_eq!(grid[8], GeoCoord::new(38.0, 37.0));
    }
}
