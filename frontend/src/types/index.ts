export type ScenarioId = 'pazarcik' | 'elbistan' | 'custom';

export interface EarthquakeScenario {
  id: ScenarioId;
  name: string;
  shortName: string;
  magnitude: number;
  depthKm: number;
  epicenter: [number, number]; // [lon, lat]
  faultMechanism: 'strike-slip' | 'normal' | 'reverse';
  description: string;
  dateStr?: string;
}

export interface HazardMetrics {
  maxPga: number;
  maxMmi: number;
  totalBuildings: number;
  collapsedBuildings: number;
  collapsedPercent: number;
  estimatedFatalities: number;
  severeCoherenceLossPercent: number;
  meanDpm: number;
}

export interface LayerVisibility {
  shakemap: boolean;
  insar: boolean;
  buildings3d: boolean;
  isochrones: boolean;
  faults: boolean;
  stations: boolean;
  liquefaction: boolean;
}

export interface CustomSimulationParams {
  magnitude: number;
  depthKm: number;
  epicenterLat: number;
  epicenterLon: number;
  faultMechanism: 'strike-slip' | 'normal' | 'reverse';
  vs30: number;
}
