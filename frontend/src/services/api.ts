import { EarthquakeScenario, HazardMetrics, CustomSimulationParams } from '../types';

const API_BASE_URL = 'http://localhost:8000';

export const PRESET_SCENARIOS: EarthquakeScenario[] = [
  {
    id: 'pazarcik',
    name: '6 Feb 2023 Pazarcık (Mw 7.8)',
    shortName: 'Pazarcık Mw 7.8',
    magnitude: 7.8,
    depthKm: 8.6,
    epicenter: [37.043, 37.288], // [lon, lat]
    faultMechanism: 'strike-slip',
    description: 'Mainshock on East Anatolian Fault Zone, producing extreme near-fault velocity pulses and widespread collapse across Hatay/Antakya.',
    dateStr: '2023-02-06 01:17:34 UTC',
  },
  {
    id: 'elbistan',
    name: '6 Feb 2023 Elbistan (Mw 7.6)',
    shortName: 'Elbistan Mw 7.6',
    magnitude: 7.6,
    depthKm: 7.0,
    epicenter: [37.203, 38.089], // [lon, lat]
    faultMechanism: 'strike-slip',
    description: 'Triggered rupture on Çardak Fault 9 hours later, compounding progressive structural failure in damaged infrastructure.',
    dateStr: '2023-02-06 10:24:49 UTC',
  },
  {
    id: 'custom',
    name: 'Custom Digital Twin Simulation',
    shortName: 'Custom Scenario',
    magnitude: 7.2,
    depthKm: 10.0,
    epicenter: [36.160, 36.202], // centered on Antakya
    faultMechanism: 'strike-slip',
    description: 'User-calibrated seismic scenario to test local soil amplification, building stock fragility, and emergency response.',
    dateStr: 'Real-time Simulation',
  },
];

// Check if backend FastAPI service is responding
export async function checkApiHealth(): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000);
    const res = await fetch(`${API_BASE_URL}/healthz`, { credentials: 'omit', signal: controller.signal });
    clearTimeout(timeoutId);
    return res.ok;
  } catch {
    return false;
  }
}

// -------------------------------------------------------------
// Sample Fallback Data Generators (Self-Contained & Deterministic)
// -------------------------------------------------------------

function getDistanceKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return 6371 * c;
}

// ASB14 GMPE approximation for fallback
function computePGA(mw: number, depthKm: number, distKm: number, vs30: number = 360): number {
  const rJb = Math.max(0.5, distKm);
  const c1 = 6.75;
  const a1 = 2.4563;
  const a2 = mw <= c1 ? 0.405 : 0.052;
  const a3 = -0.058;
  const a4 = -1.144;
  const a5 = 0.165;
  const a6 = 7.5;

  const fMag = a1 + a2 * (mw - c1) + a3 * Math.pow(8.5 - mw, 2);
  const fDist = (a4 + a5 * (mw - c1)) * Math.log(Math.sqrt(rJb * rJb + a6 * a6));
  const fSite = -0.42 * Math.log(vs30 / 750.0);

  const lnPga = fMag + fDist + fSite;
  return Math.max(0.01, Math.min(3.5, Math.exp(lnPga)));
}

function pgaToMmi(pgaG: number): number {
  const logPga = Math.log10(pgaG * 100);
  let mmi = logPga <= 1.0 ? 1.78 + 1.55 * logPga : 3.1 + 2.87 * logPga;
  return Math.max(1.0, Math.min(10.5, mmi));
}

// Generate ShakeMap GeoJSON
export async function getShakeMapData(scenario: EarthquakeScenario): Promise<GeoJSON.FeatureCollection> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/shakemap/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        magnitude: scenario.magnitude,
        depth_km: scenario.depthKm,
        epicenter_lat: scenario.epicenter[1],
        epicenter_lon: scenario.epicenter[0],
        fault_mechanism: scenario.faultMechanism,
        default_vs30: 360.0,
        grid_resolution: 35,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.geojson && data.geojson.features && data.geojson.features.length > 0) {
        return data.geojson;
      }
    }
  } catch {
    // Graceful fallback below
  }

  // Synthesize regional ShakeMap covering Hatay & Epicenter
  const features: GeoJSON.Feature[] = [];
  const minLat = 35.8;
  const maxLat = 37.6;
  const minLon = 35.7;
  const maxLon = 37.6;
  const steps = 28;

  const latStep = (maxLat - minLat) / steps;
  const lonStep = (maxLon - minLon) / steps;

  for (let r = 0; r <= steps; r++) {
    const lat = minLat + r * latStep;
    for (let c = 0; c <= steps; c++) {
      const lon = minLon + c * lonStep;
      const distKm = getDistanceKm(scenario.epicenter[0], scenario.epicenter[1], lon, lat);
      const pga = computePGA(scenario.magnitude, scenario.depthKm, distKm);
      const mmi = pgaToMmi(pga);

      if (mmi >= 4.0) {
        features.push({
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [parseFloat(lon.toFixed(4)), parseFloat(lat.toFixed(4))],
          },
          properties: {
            pga_g: parseFloat(pga.toFixed(3)),
            mmi: parseFloat(mmi.toFixed(1)),
            pgv_cms: parseFloat((pga * 98.1 * 0.15).toFixed(1)),
            dist_km: Math.round(distKm),
          },
        });
      }
    }
  }

  return {
    type: 'FeatureCollection',
    features,
  };
}

// Generate InSAR DPM GeoJSON & metrics
export async function getInsarDpmData(scenario: EarthquakeScenario): Promise<{
  geojson: GeoJSON.FeatureCollection;
  severeRatio: number;
  meanDpm: number;
}> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/insar/simulate-dpm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        min_lon: 36.12,
        min_lat: 36.17,
        max_lon: 36.20,
        max_lat: 36.24,
        epicenter_lon: scenario.epicenter[0],
        epicenter_lat: scenario.epicenter[1],
        magnitude: scenario.magnitude,
        resolution: 25,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      return {
        geojson: generateInsarPolygons(scenario.magnitude, scenario.epicenter),
        severeRatio: data.severe_damage_ratio || 0.42,
        meanDpm: data.mean_dpm || 0.58,
      };
    }
  } catch {
    // fallback
  }

  const severeRatio = scenario.magnitude >= 7.8 ? 0.485 : scenario.magnitude >= 7.5 ? 0.382 : 0.224;
  const meanDpm = scenario.magnitude >= 7.8 ? 0.642 : 0.495;
  return {
    geojson: generateInsarPolygons(scenario.magnitude, scenario.epicenter),
    severeRatio,
    meanDpm,
  };
}

function generateInsarPolygons(magnitude: number, epicenter: [number, number]): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  const minLon = 36.13;
  const maxLon = 36.19;
  const minLat = 36.17;
  const maxLat = 36.23;
  const cols = 20;
  const rows = 20;
  const dLon = (maxLon - minLon) / cols;
  const dLat = (maxLat - minLat) / rows;

  for (let i = 0; i < cols; i++) {
    for (let j = 0; j < rows; j++) {
      const cLon = minLon + (i + 0.5) * dLon;
      const cLat = minLat + (j + 0.5) * dLat;
      const distKm = getDistanceKm(epicenter[0], epicenter[1], cLon, cLat);
      // Coherence drop function: higher near fault & river alluvial basin
      const basinAmplification = Math.sin((cLon - 36.13) * 30) * Math.cos((cLat - 36.17) * 30) * 0.15;
      const baseDpm = Math.max(0.05, Math.min(0.98, 0.85 * Math.exp(-distKm / 150) + basinAmplification + 0.1));
      const dpmVal = parseFloat(baseDpm.toFixed(3));

      // Filter low noise to keep visualization clean
      if (dpmVal > 0.28) {
        const polyCoords = [
          [minLon + i * dLon, minLat + j * dLat],
          [minLon + (i + 1) * dLon, minLat + j * dLat],
          [minLon + (i + 1) * dLon, minLat + (j + 1) * dLat],
          [minLon + i * dLon, minLat + (j + 1) * dLat],
          [minLon + i * dLon, minLat + j * dLat],
        ];

        features.push({
          type: 'Feature',
          geometry: {
            type: 'Polygon',
            coordinates: [polyCoords],
          },
          properties: {
            dpm: dpmVal,
            loss_percent: Math.round(dpmVal * 100),
            severity: dpmVal > 0.65 ? 'Critical' : dpmVal > 0.45 ? 'Heavy' : 'Moderate',
          },
        });
      }
    }
  }

  return {
    type: 'FeatureCollection',
    features,
  };
}

// -------------------------------------------------------------
// 3D Building Footprints & Structural Damage
// -------------------------------------------------------------

export async function getBuildingDamageData(pgaInputG: number): Promise<{
  geojson: GeoJSON.FeatureCollection;
  total: number;
  collapsed: number;
  fatalities: number;
}> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/damage/sample-antakya`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pga_g: pgaInputG,
        building_count: 85,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.geojson && data.geojson.features) {
        // Ensure height property exists for 3D extrusion
        data.geojson.features.forEach((f: any, idx: number) => {
          if (!f.properties.height) {
            const floors = f.properties.occupancy ? Math.max(3, Math.min(14, Math.round(f.properties.occupancy / 2.5))) : (idx % 6) + 4;
            f.properties.height = floors * 3.2;
            f.properties.floors = floors;
          }
        });
        return {
          geojson: data.geojson,
          total: data.summary.total_buildings,
          collapsed: data.summary.collapsed_buildings,
          fatalities: data.summary.estimated_fatalities,
        };
      }
    }
  } catch {
    // fallback
  }

  // Realistic synthetic Antakya city center building stock
  const features: GeoJSON.Feature[] = [];
  const baseLon = 36.1605;
  const baseLat = 36.2025;
  let collapsed = 0;
  let fatalities = 0;
  const total = 90;

  // Typologies and fragilities
  const typologies = [
    { type: 'RC_PRE_2000', label: 'Pre-1999 RC Frame (Non-ductile)', med: 0.68, beta: 0.62, weight: 0.55 },
    { type: 'RC_POST_2000', label: 'Modern RC Frame (Compliant)', med: 1.15, beta: 0.58, weight: 0.25 },
    { type: 'URM', label: 'Unreinforced Masonry (Historic)', med: 0.48, beta: 0.65, weight: 0.15 },
    { type: 'STEEL', label: 'Structural Steel / Commercial', med: 1.55, beta: 0.55, weight: 0.05 },
  ];

  for (let i = 0; i < total; i++) {
    // Cluster along urban blocks
    const blockRow = Math.floor(i / 10);
    const blockCol = i % 10;
    const cLon = baseLon + (blockCol - 4.5) * 0.0035 + (Math.sin(i * 13) * 0.0008);
    const cLat = baseLat + (blockRow - 4.5) * 0.0028 + (Math.cos(i * 17) * 0.0006);

    const bSizeX = 0.00075 + (Math.sin(i * 3) * 0.00025);
    const bSizeY = 0.00065 + (Math.cos(i * 5) * 0.0002);

    const poly = [
      [cLon - bSizeX / 2, cLat - bSizeY / 2],
      [cLon + bSizeX / 2, cLat - bSizeY / 2],
      [cLon + bSizeX / 2, cLat + bSizeY / 2],
      [cLon - bSizeX / 2, cLat + bSizeY / 2],
      [cLon - bSizeX / 2, cLat - bSizeY / 2],
    ];

    const randT = (i * 7) % 100;
    let typo = typologies[0];
    if (randT > 80) typo = typologies[1];
    else if (randT > 65) typo = typologies[2];
    else if (randT > 60) typo = typologies[3];

    // Fragility lognormal calculation
    const z = (Math.log(pgaInputG) - Math.log(typo.med)) / typo.beta;
    // Cumulative normal approximation
    const pCollapse = 1 / (1 + Math.exp(-1.7 * z));
    const clampedPCollapse = Math.max(0.01, Math.min(0.99, pCollapse));

    let damageGrade = 'D1_Slight';
    if (clampedPCollapse >= 0.48) {
      damageGrade = 'D4_Collapse';
      collapsed++;
    } else if (clampedPCollapse >= 0.28) {
      damageGrade = 'D3_Extensive';
    } else if (clampedPCollapse >= 0.12) {
      damageGrade = 'D2_Moderate';
    }

    const floors = 3 + (i % 8);
    const heightM = floors * 3.2;
    const occupants = floors * 4;
    const buildingFatalities = damageGrade === 'D4_Collapse' ? Math.round(occupants * 0.25 * 10) / 10 : 0;
    fatalities += buildingFatalities;

    features.push({
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [poly],
      },
      properties: {
        building_id: `BLD_${String(i + 1).padStart(4, '0')}`,
        typology: typo.type,
        typology_label: typo.label,
        floors: floors,
        height: heightM,
        occupancy: occupants,
        pga_g: pgaInputG,
        p_collapse: parseFloat(clampedPCollapse.toFixed(3)),
        damage_grade: damageGrade,
        estimated_fatalities: buildingFatalities,
      },
    });
  }

  return {
    geojson: {
      type: 'FeatureCollection',
      features,
    },
    total,
    collapsed,
    fatalities: Math.round(fatalities),
  };
}

// -------------------------------------------------------------
// Emergency Reachability Isochrones (5, 10, 15 min)
// -------------------------------------------------------------

export async function getIsochronesData(centerLon: number = 36.160, centerLat: number = 36.202): Promise<GeoJSON.FeatureCollection> {
  const cutoffs = [15, 10, 5]; // Outer to inner so inner renders on top or colored cleanly
  const features: GeoJSON.Feature[] = [];

  for (const cutoff of cutoffs) {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/routing/isochrone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          center_lon: centerLon,
          center_lat: centerLat,
          cutoff_minutes: cutoff,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.isochrone_geojson) {
          features.push({
            type: 'Feature',
            geometry: data.isochrone_geojson,
            properties: {
              cutoff_minutes: cutoff,
              label: `${cutoff} min reachability`,
            },
          });
          continue;
        }
      }
    } catch {
      // Fall through to synthetic polygon
    }

    // High quality synthetic isochrone polygon with realistic road corridor asymmetry
    const radiusDeg = cutoff === 5 ? 0.012 : cutoff === 10 ? 0.024 : 0.038;
    const numPoints = 28;
    const ring: [number, number][] = [];

    for (let step = 0; step <= numPoints; step++) {
      const angle = (step / numPoints) * 2 * Math.PI;
      // Asymmetric stretch along Hatay valley (North-South axis) and debris barriers
      const rModifier = 1.0 + 0.28 * Math.cos(2 * angle) - 0.15 * Math.sin(3 * angle);
      const r = radiusDeg * rModifier;
      const px = centerLon + r * Math.cos(angle) * 1.15;
      const py = centerLat + r * Math.sin(angle);
      ring.push([parseFloat(px.toFixed(5)), parseFloat(py.toFixed(5))]);
    }

    features.push({
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [ring],
      },
      properties: {
        cutoff_minutes: cutoff,
        label: `${cutoff} min Reachability`,
      },
    });
  }

  return {
    type: 'FeatureCollection',
    features,
  };
}

// -------------------------------------------------------------
// Combined Scenario Hazard Evaluation
// -------------------------------------------------------------

export async function loadScenarioData(scenario: EarthquakeScenario, customPga?: number): Promise<{
  shakeMap: GeoJSON.FeatureCollection;
  insarDpm: GeoJSON.FeatureCollection;
  buildings: GeoJSON.FeatureCollection;
  isochrones: GeoJSON.FeatureCollection;
  metrics: HazardMetrics;
  isLiveApi: boolean;
}> {
  const isLive = await checkApiHealth();

  // 1. ShakeMap
  const shakeMap = await getShakeMapData(scenario);

  // Derive local PGA in Antakya [36.16, 36.20]
  const antakyaDist = getDistanceKm(scenario.epicenter[0], scenario.epicenter[1], 36.16, 36.20);
  const localPga = customPga !== undefined ? customPga : computePGA(scenario.magnitude, scenario.depthKm, antakyaDist);
  const localMmi = pgaToMmi(localPga);

  // 2. InSAR DPM
  const insarRes = await getInsarDpmData(scenario);

  // 3. Buildings
  const buildingRes = await getBuildingDamageData(localPga);

  // 4. Isochrones
  const isochrones = await getIsochronesData(36.160, 36.202);

  const collapsedPercent = (buildingRes.collapsed / buildingRes.total) * 100;

  const metrics: HazardMetrics = {
    maxPga: parseFloat(localPga.toFixed(3)),
    maxMmi: parseFloat(localMmi.toFixed(1)),
    totalBuildings: buildingRes.total,
    collapsedBuildings: buildingRes.collapsed,
    collapsedPercent: parseFloat(collapsedPercent.toFixed(1)),
    estimatedFatalities: buildingRes.fatalities,
    severeCoherenceLossPercent: parseFloat((insarRes.severeRatio * 100).toFixed(1)),
    meanDpm: parseFloat(insarRes.meanDpm.toFixed(3)),
  };

  return {
    shakeMap,
    insarDpm: insarRes.geojson,
    buildings: buildingRes.geojson,
    isochrones,
    metrics,
    isLiveApi: isLive,
  };
}
