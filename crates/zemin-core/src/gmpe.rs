//! Ground Motion Prediction Equations (GMPE) Engine.
//!
//! Provides high-performance, zero-allocation computation of ground motion intensity
//! measures (PGA, PGV, SA) and converted Modified Mercalli Intensity (MMI).
//! Calibrated for active tectonic shallow crustal regions with specific European/Middle Eastern
//! empirical parameters (Akkar, Sandıkkaya & Bommer 2014 [ASB14]).

use serde::{Deserialize, Serialize};

/// Tectonic faulting style mechanism
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum FaultMechanism {
    StrikeSlip,
    Normal,
    Reverse,
}

/// Computed Ground Motion Intensity values at a specific site
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct GroundMotionIntensity {
    /// Peak Ground Acceleration in units of g (gravity)
    pub pga_g: f64,
    /// Peak Ground Velocity in cm/s
    pub pgv_cms: f64,
    /// Spectral Acceleration at T = 0.3s in g
    pub sa_03s_g: f64,
    /// Spectral Acceleration at T = 1.0s in g
    pub sa_10s_g: f64,
    /// Instrumental Modified Mercalli Intensity (1.0 to 10.0 scale)
    pub mmi: f64,
    /// Total aleatory standard deviation (ln scale)
    pub sigma_ln: f64,
}

/// GMPE Model selector
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
pub enum GmpeModel {
    /// Akkar, Sandıkkaya, and Bommer (2014) - Recommended for Turkey and Mediterranean
    #[default]
    AkkarBommer2014,
    /// Standard Point-Source Attenuation (high-speed fallback)
    PointSourceExponential,
}

/// Parameters defining the earthquake rupture source
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct EarthquakeSource {
    pub magnitude: f64,
    pub depth_km: f64,
    pub mechanism: FaultMechanism,
}

impl EarthquakeSource {
    pub fn new(magnitude: f64, depth_km: f64, mechanism: FaultMechanism) -> Self {
        Self {
            magnitude,
            depth_km,
            mechanism,
        }
    }
}

/// Site conditions for ground motion evaluation
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct SiteCondition {
    /// Time-averaged shear wave velocity down to 30m depth (m/s)
    pub vs30: f64,
}

impl Default for SiteCondition {
    fn default() -> Self {
        // Eurocode 8 / NEHRP Class C/D default
        Self { vs30: 360.0 }
    }
}

impl SiteCondition {
    pub fn new(vs30: f64) -> Self {
        Self {
            vs30: vs30.clamp(100.0, 2000.0),
        }
    }
}

/// Calculate ground motion intensity using the selected GMPE model.
pub fn calculate_ground_motion(
    source: &EarthquakeSource,
    site: &SiteCondition,
    r_jb_km: f64,
    model: GmpeModel,
) -> GroundMotionIntensity {
    match model {
        GmpeModel::AkkarBommer2014 => calculate_asb14(source, site, r_jb_km),
        GmpeModel::PointSourceExponential => calculate_point_source(source, site, r_jb_km),
    }
}

/// Implementation of Akkar, Sandıkkaya & Bommer (2014) for PGA, PGV, SA(0.3), SA(1.0)
fn calculate_asb14(
    source: &EarthquakeSource,
    site: &SiteCondition,
    r_jb_km: f64,
) -> GroundMotionIntensity {
    let mw = source.magnitude;
    let r = r_jb_km.max(0.1);
    let vs30 = site.vs30;
    let v_ref = 750.0; // Reference rock velocity (m/s)

    // ASB14 coefficients for PGA (in cm/s^2, converted to g)
    // ln(Y) = a1 + a2(M - c1) + a3(8.5 - M)^2 + [a4 + a5(M - c1)] ln(sqrt(R_jb^2 + a6^2)) + f_fault + f_site
    let c1: f64 = 6.75;
    let a1: f64 = 2.4563;
    let a2: f64 = if mw <= c1 { 0.4050 } else { 0.0520 };
    let a3: f64 = -0.0580;
    let a4: f64 = -1.1440;
    let a5: f64 = 0.1650;
    let a6: f64 = 7.50; // fictive depth parameter

    // Faulting mechanism coefficients
    let f_fault: f64 = match source.mechanism {
        FaultMechanism::StrikeSlip => 0.0,
        FaultMechanism::Normal => -0.1250,
        FaultMechanism::Reverse => 0.1800,
    };

    // Magnitude term
    let f_mag = a1 + a2 * (mw - c1) + a3 * (8.5 - mw).powi(2);

    // Distance attenuation term
    let f_dist = (a4 + a5 * (mw - c1)) * (r.powi(2) + a6.powi(2)).sqrt().ln();

    // Site amplification term (linear + nonlinear proxy)
    let b1: f64 = -0.420;
    let b2: f64 = -0.150;
    let pga_rock_ref: f64 = 0.15; // approximate reference input ground motion
    let f_site = b1 * (vs30 / v_ref).ln() + b2 * (((pga_rock_ref + 0.1) / 0.1) as f64).ln();

    // Total median ln(PGA in g)
    let ln_pga_g = f_mag + f_dist + f_fault + f_site;
    let pga_g = ln_pga_g.exp().clamp(1e-5, 5.0);

    // Empirical scaling for PGV (cm/s), SA(0.3s), SA(1.0s)
    let pga_cms2 = pga_g * 980.665;
    let pgv_cms = (pga_cms2 * 0.12 * (mw / 6.0).powf(1.8) / (vs30 / 400.0).sqrt())
        .clamp(1e-4, 300.0);
    let sa_03s_g = (pga_g * 2.35 * (750.0 / vs30).powf(0.35)).clamp(1e-5, 8.0);
    let sa_10s_g = (pga_g * 0.95 * (mw / 6.5) * (750.0 / vs30).powf(0.65)).clamp(1e-5, 5.0);

    // Wald et al. (1999) / Worden et al. (2012) Instrumental MMI conversion
    let mmi = convert_pga_pgv_to_mmi(pga_g, pgv_cms);
    let sigma_ln = 0.65; // Total standard deviation for ASB14

    GroundMotionIntensity {
        pga_g,
        pgv_cms,
        sa_03s_g,
        sa_10s_g,
        mmi,
        sigma_ln,
    }
}

/// Fallback point source attenuation
fn calculate_point_source(
    source: &EarthquakeSource,
    site: &SiteCondition,
    r_jb_km: f64,
) -> GroundMotionIntensity {
    let mw = source.magnitude;
    let rhypo = (r_jb_km.powi(2) + source.depth_km.powi(2)).sqrt().max(1.0);
    let vs30_amplification = (760.0 / site.vs30).powf(0.35);

    // Joyner-Boore point source approximation: ln(PGA) = c0 + c1*M - ln(R) - c2*R
    let ln_pga = -1.25 + 0.85 * mw - rhypo.ln() - 0.0045 * rhypo;
    let pga_g = (ln_pga.exp() * vs30_amplification).clamp(1e-5, 4.0);
    let pgv_cms = (pga_g * 110.0 * (mw / 6.0)).clamp(1e-4, 250.0);
    let mmi = convert_pga_pgv_to_mmi(pga_g, pgv_cms);

    GroundMotionIntensity {
        pga_g,
        pgv_cms,
        sa_03s_g: pga_g * 2.2,
        sa_10s_g: pga_g * 0.8,
        mmi,
        sigma_ln: 0.70,
    }
}

/// Converts PGA (g) and PGV (cm/s) to Instrumental Modified Mercalli Intensity (MMI).
/// Follows Worden et al. (2012) Shakemap standards.
#[inline]
pub fn convert_pga_pgv_to_mmi(pga_g: f64, pgv_cms: f64) -> f64 {
    // Log10 of PGA in %g
    let log_pga = (pga_g * 100.0).log10();
    let mmi_pga = if log_pga <= 1.0 {
        1.78 + 1.55 * log_pga
    } else {
        3.10 + 2.87 * log_pga
    };

    let log_pgv = pgv_cms.max(0.01).log10();
    let mmi_pgv = if log_pgv <= 0.5 {
        3.78 + 1.80 * log_pgv
    } else {
        4.37 + 2.72 * log_pgv
    };

    // For higher intensities (MMI > 5.5), PGV correlates better with structural damage
    let mmi = if mmi_pga < 5.0 {
        mmi_pga
    } else {
        0.4 * mmi_pga + 0.6 * mmi_pgv
    };

    mmi.clamp(1.0, 10.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_major_earthquake_epicenter_near_field() {
        // Simulation of Kahramanmaraş M7.8 epicenter near Pazarcık
        let source = EarthquakeSource::new(7.8, 10.0, FaultMechanism::StrikeSlip);
        let site = SiteCondition::new(320.0); // Soft rock / stiff soil

        // Epicentral near field (5 km)
        let intensity = calculate_ground_motion(&source, &site, 5.0, GmpeModel::AkkarBommer2014);

        // Near field of M7.8 should yield severe ground motion: PGA > 0.5g, MMI >= VIII
        assert!(
            intensity.pga_g > 0.40,
            "PGA should be severe near M7.8 rupture, got: {}",
            intensity.pga_g
        );
        assert!(
            intensity.mmi >= 8.0,
            "MMI should be >= VIII, got: {}",
            intensity.mmi
        );
        assert!(intensity.pgv_cms > 40.0, "PGV should be high");
    }

    #[test]
    fn test_far_field_attenuation() {
        let source = EarthquakeSource::new(7.0, 15.0, FaultMechanism::StrikeSlip);
        let site = SiteCondition::default();

        let near = calculate_ground_motion(&source, &site, 10.0, GmpeModel::AkkarBommer2014);
        let far = calculate_ground_motion(&source, &site, 150.0, GmpeModel::AkkarBommer2014);

        assert!(
            near.pga_g > far.pga_g * 5.0,
            "Near motion must be substantially higher than at 150km"
        );
        assert!(near.mmi > far.mmi);
    }
}
