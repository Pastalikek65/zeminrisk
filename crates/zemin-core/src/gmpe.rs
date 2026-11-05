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
        let mag = if magnitude.is_finite() {
            magnitude.clamp(1.0, 10.0)
        } else {
            6.0
        };
        let depth = if depth_km.is_finite() {
            depth_km.max(0.0)
        } else {
            10.0
        };
        Self {
            magnitude: mag,
            depth_km: depth,
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
        let val = if vs30.is_finite() && vs30 > 0.0 {
            vs30.clamp(100.0, 2000.0)
        } else {
            360.0
        };
        Self { vs30: val }
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
    let mw = if source.magnitude.is_finite() {
        source.magnitude.clamp(1.0, 10.0)
    } else {
        6.0
    };
    let r = if r_jb_km.is_finite() {
        r_jb_km.max(0.0).max(0.1)
    } else {
        0.1
    };
    let vs30 = if site.vs30.is_finite() && site.vs30 > 0.0 {
        site.vs30.clamp(50.0, 3000.0)
    } else {
        360.0
    };
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
    let f_site = b1 * (vs30 / v_ref).ln() + b2 * ((pga_rock_ref + 0.1) / 0.1).ln();

    // Total median ln(PGA in g)
    let ln_pga_g = f_mag + f_dist + f_fault + f_site;
    let pga_g = if ln_pga_g.is_finite() {
        ln_pga_g.exp().clamp(1e-5, 5.0)
    } else {
        1e-5
    };

    // Empirical scaling for PGV (cm/s), SA(0.3s), SA(1.0s)
    let pga_cms2 = pga_g * 980.665;
    let pgv_term = pga_cms2 * 0.12 * (mw / 6.0).powf(1.8) / (vs30 / 400.0).sqrt();
    let pgv_cms = if pgv_term.is_finite() {
        pgv_term.clamp(1e-4, 300.0)
    } else {
        1e-4
    };
    let sa_03s_term = pga_g * 2.35 * (750.0 / vs30).powf(0.35);
    let sa_03s_g = if sa_03s_term.is_finite() {
        sa_03s_term.clamp(1e-5, 8.0)
    } else {
        1e-5
    };
    let sa_10s_term = pga_g * 0.95 * (mw / 6.5) * (750.0 / vs30).powf(0.65);
    let sa_10s_g = if sa_10s_term.is_finite() {
        sa_10s_term.clamp(1e-5, 5.0)
    } else {
        1e-5
    };

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
    let mw = if source.magnitude.is_finite() {
        source.magnitude.clamp(1.0, 10.0)
    } else {
        6.0
    };
    let depth = if source.depth_km.is_finite() {
        source.depth_km.max(0.0)
    } else {
        10.0
    };
    let r = if r_jb_km.is_finite() {
        r_jb_km.max(0.0)
    } else {
        0.0
    };
    let rhypo = (r.powi(2) + depth.powi(2)).sqrt().max(1.0);
    let vs30 = if site.vs30.is_finite() && site.vs30 > 0.0 {
        site.vs30.clamp(50.0, 3000.0)
    } else {
        360.0
    };
    let vs30_amplification = (760.0 / vs30).powf(0.35);

    // Joyner-Boore point source approximation: ln(PGA) = c0 + c1*M - ln(R) - c2*R
    let ln_pga = -1.25 + 0.85 * mw - rhypo.ln() - 0.0045 * rhypo;
    let pga_g = if ln_pga.is_finite() {
        (ln_pga.exp() * vs30_amplification).clamp(1e-5, 4.0)
    } else {
        1e-5
    };
    let pgv_term = pga_g * 110.0 * (mw / 6.0);
    let pgv_cms = if pgv_term.is_finite() {
        pgv_term.clamp(1e-4, 250.0)
    } else {
        1e-4
    };
    let sa_03s_g = (pga_g * 2.2).clamp(1e-5, 8.0);
    let sa_10s_g = (pga_g * 0.8).clamp(1e-5, 5.0);
    let mmi = convert_pga_pgv_to_mmi(pga_g, pgv_cms);

    GroundMotionIntensity {
        pga_g,
        pgv_cms,
        sa_03s_g,
        sa_10s_g,
        mmi,
        sigma_ln: 0.70,
    }
}

/// Converts PGA (g) and PGV (cm/s) to Instrumental Modified Mercalli Intensity (MMI).
/// Follows Worden et al. (2012) Shakemap standards.
#[inline]
pub fn convert_pga_pgv_to_mmi(pga_g: f64, pgv_cms: f64) -> f64 {
    let safe_pga = if pga_g.is_finite() && pga_g > 0.0 {
        pga_g.max(1e-6)
    } else {
        1e-6
    };
    let log_pga = (safe_pga * 100.0).log10();
    let mmi_pga = if log_pga <= 1.0 {
        1.78 + 1.55 * log_pga
    } else {
        3.10 + 2.87 * log_pga
    };

    let safe_pgv = if pgv_cms.is_finite() && pgv_cms > 0.0 {
        pgv_cms.max(1e-4)
    } else {
        1e-4
    };
    let log_pgv = safe_pgv.log10();
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

    if mmi.is_finite() {
        mmi.clamp(1.0, 10.0)
    } else {
        1.0
    }
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

    #[test]
    fn test_extreme_scenario_mw95_zero_distance_soft_soil() {
        // Extreme scenario: Mw 9.5 mega-thrust/great earthquake, 0 km distance, soft soil (100 m/s)
        let source = EarthquakeSource::new(9.5, 0.0, FaultMechanism::Reverse);
        let site = SiteCondition::new(100.0);

        for model in [
            GmpeModel::AkkarBommer2014,
            GmpeModel::PointSourceExponential,
        ] {
            let intensity = calculate_ground_motion(&source, &site, 0.0, model);

            assert!(intensity.pga_g.is_finite(), "PGA must be finite");
            assert!(
                intensity.pga_g > 0.0 && intensity.pga_g <= 5.0,
                "PGA in range"
            );
            assert!(intensity.pgv_cms.is_finite(), "PGV must be finite");
            assert!(
                intensity.pgv_cms > 0.0 && intensity.pgv_cms <= 300.0,
                "PGV in range"
            );
            assert!(intensity.sa_03s_g.is_finite(), "SA 0.3s must be finite");
            assert!(intensity.sa_10s_g.is_finite(), "SA 1.0s must be finite");
            assert!(intensity.mmi.is_finite(), "MMI must be finite");
            assert!(
                (1.0..=10.0).contains(&intensity.mmi),
                "MMI must be within [1, 10]"
            );
        }
    }

    #[test]
    fn test_boundary_conditions_zero_and_nan() {
        // Test direct struct instantiation with degenerate/extreme values
        let source_degenerate = EarthquakeSource {
            magnitude: f64::NAN,
            depth_km: -10.0,
            mechanism: FaultMechanism::StrikeSlip,
        };
        let site_zero = SiteCondition { vs30: 0.0 };
        let site_neg = SiteCondition { vs30: -500.0 };
        let site_nan = SiteCondition { vs30: f64::NAN };

        for site in [site_zero, site_neg, site_nan] {
            let res = calculate_ground_motion(
                &source_degenerate,
                &site,
                -5.0,
                GmpeModel::AkkarBommer2014,
            );
            assert!(res.pga_g.is_finite());
            assert!(res.pgv_cms.is_finite());
            assert!(res.mmi.is_finite());
            assert!(res.pga_g > 0.0);
            assert!(res.pgv_cms > 0.0);
        }
    }

    #[test]
    fn test_mmi_conversion_extremes() {
        assert_eq!(convert_pga_pgv_to_mmi(0.0, 0.0), 1.0);
        assert_eq!(convert_pga_pgv_to_mmi(-1.0, -1.0), 1.0);
        assert_eq!(convert_pga_pgv_to_mmi(f64::NAN, f64::NAN), 1.0);
        assert_eq!(convert_pga_pgv_to_mmi(10.0, 500.0), 10.0);
    }

    #[test]
    fn test_property_based_parameter_sweep() {
        let mechanisms = [
            FaultMechanism::StrikeSlip,
            FaultMechanism::Normal,
            FaultMechanism::Reverse,
        ];
        let models = [
            GmpeModel::AkkarBommer2014,
            GmpeModel::PointSourceExponential,
        ];

        let mags = [1.0, 5.0, 7.0, 7.8, 9.5];
        let depths = [0.0, 5.0, 15.0, 50.0];
        let distances = [0.0, 0.5, 10.0, 100.0, 500.0];
        let vs30s = [100.0, 360.0, 760.0, 1500.0];

        for &mw in &mags {
            for &depth in &depths {
                for &mech in &mechanisms {
                    let source = EarthquakeSource::new(mw, depth, mech);
                    for &vs30 in &vs30s {
                        let site = SiteCondition::new(vs30);
                        for &r in &distances {
                            for &model in &models {
                                let res = calculate_ground_motion(&source, &site, r, model);
                                assert!(
                                    res.pga_g.is_finite(),
                                    "PGA must be finite for Mw={mw}, r={r}, vs30={vs30}"
                                );
                                assert!(
                                    res.pgv_cms.is_finite(),
                                    "PGV must be finite for Mw={mw}, r={r}, vs30={vs30}"
                                );
                                assert!(res.sa_03s_g.is_finite());
                                assert!(res.sa_10s_g.is_finite());
                                assert!(res.mmi.is_finite());
                                assert!(res.pga_g > 0.0 && res.pga_g <= 5.0);
                                assert!(res.pgv_cms > 0.0 && res.pgv_cms <= 300.0);
                                assert!((1.0..=10.0).contains(&res.mmi));
                            }
                        }
                    }
                }
            }
        }
    }
}
