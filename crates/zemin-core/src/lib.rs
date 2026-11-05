//! ZeminRisk Core: High-performance computational engine for seismic risk,
//! ground motion simulation, and spatial analysis.

pub mod gmpe;
pub mod raster;
pub mod spatial;

pub use gmpe::{
    calculate_ground_motion, EarthquakeSource, FaultMechanism, GmpeModel, GroundMotionIntensity,
    SiteCondition,
};
pub use raster::{ShakeMapRaster, ShakeMapStats};
pub use spatial::{BoundingBox, FaultRupture, GeoCoord, EARTH_RADIUS_KM};

#[cfg(feature = "python")]
#[allow(clippy::too_many_arguments, clippy::useless_conversion)]
mod pyo3_bindings {
    use super::*;
    use pyo3::prelude::*;

    #[pyfunction]
    #[pyo3(signature = (mag, depth_km, strike_slip, vs30, r_jb_km))]
    fn calc_gmpe(
        mag: f64,
        depth_km: f64,
        strike_slip: bool,
        vs30: f64,
        r_jb_km: f64,
    ) -> PyResult<String> {
        let mech = if strike_slip {
            FaultMechanism::StrikeSlip
        } else {
            FaultMechanism::Normal
        };
        let src = EarthquakeSource::new(mag, depth_km, mech);
        let site = SiteCondition::new(vs30);
        let res = calculate_ground_motion(&src, &site, r_jb_km, GmpeModel::AkkarBommer2014);

        serde_json::to_string(&res)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    #[pyfunction]
    #[pyo3(signature = (mag, depth_km, epi_lat, epi_lon, min_lat, max_lat, min_lon, max_lon, nrows, ncols, vs30=360.0, use_finite_fault=false))]
    fn compute_shakemap_geojson(
        mag: f64,
        depth_km: f64,
        epi_lat: f64,
        epi_lon: f64,
        min_lat: f64,
        max_lat: f64,
        min_lon: f64,
        max_lon: f64,
        nrows: usize,
        ncols: usize,
        vs30: f64,
        use_finite_fault: bool,
    ) -> PyResult<String> {
        let src = EarthquakeSource::new(mag, depth_km, FaultMechanism::StrikeSlip);
        let bbox = BoundingBox::new(min_lat, max_lat, min_lon, max_lon);

        let rupture = if use_finite_fault && mag >= 7.0 {
            FaultRupture::east_anatolian_fault_2023()
        } else {
            FaultRupture::point(epi_lat, epi_lon)
        };

        let raster = ShakeMapRaster::compute_with_rupture(
            &src,
            &rupture,
            &bbox,
            nrows,
            ncols,
            vs30,
            GmpeModel::AkkarBommer2014,
        );

        let geojson = raster.to_geojson_features(5.0);
        serde_json::to_string(&geojson)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    #[pymodule]
    fn zemin_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add_function(wrap_pyfunction!(calc_gmpe, m)?)?;
        m.add_function(wrap_pyfunction!(compute_shakemap_geojson, m)?)?;
        Ok(())
    }
}
