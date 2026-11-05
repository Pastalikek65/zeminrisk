import React, { useEffect, useRef, useState, useCallback } from 'react';
import maplibregl, { Map as MapLibreMap, NavigationControl, ScaleControl, FullscreenControl, Popup } from 'maplibre-gl';
import { Header } from './components/Header';
import { MetricsPanel } from './components/MetricsPanel';
import { LayerControls } from './components/LayerControls';
import { ScenarioSelector } from './components/ScenarioSelector';
import { CustomSimulationModal } from './components/CustomSimulationModal';
import { ResponseSpectrumModal } from './components/ResponseSpectrumModal';
import { Legend } from './components/Legend';
import {
  PRESET_SCENARIOS,
  loadScenarioData,
  checkApiHealth,
} from './services/api';
import {
  EarthquakeScenario,
  HazardMetrics,
  LayerVisibility,
  CustomSimulationParams,
} from './types';
import { Eye, Compass, Building, Activity, RotateCcw, Download, TrendingUp } from 'lucide-react';
import './App.css';

// Sleek dark Carto basemap style
const DARK_BASEMAP_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    'carto-dark': {
      type: 'raster',
      tiles: [
        'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
        'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
        'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
        'https://d.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
      ],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    },
  },
  layers: [
    {
      id: 'carto-dark-tiles',
      type: 'raster',
      source: 'carto-dark',
      minzoom: 0,
      maxzoom: 20,
    },
  ],
};

export const App: React.FC = () => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const popupRef = useRef<Popup | null>(null);

  // Application State
  const [activeScenario, setActiveScenario] = useState<EarthquakeScenario>(PRESET_SCENARIOS[0]);
  const [isLiveApi, setIsLiveApi] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [metrics, setMetrics] = useState<HazardMetrics | null>(null);
  const [isCustomModalOpen, setIsCustomModalOpen] = useState<boolean>(false);
  const [isSpectrumModalOpen, setIsSpectrumModalOpen] = useState<boolean>(false);
  const [spectrumData, setSpectrumData] = useState<{
    title: string;
    pga: number;
    highlightPeriod?: number;
  }>({
    title: 'Antakya Central Basin',
    pga: 1.05,
    highlightPeriod: 0.5,
  });
  const [currentCoords, setCurrentCoords] = useState<{ lat: number; lng: number }>({
    lat: 36.202,
    lng: 36.160,
  });

  const [layersVisibility, setLayersVisibility] = useState<LayerVisibility>({
    shakemap: true,
    insar: true,
    buildings3d: true,
    isochrones: true,
    faults: true,
    stations: true,
    liquefaction: true,
  });

  // Keep a reference to current GeoJSON for export
  const currentDataRef = useRef<{
    shakeMap?: GeoJSON.FeatureCollection;
    insarDpm?: GeoJSON.FeatureCollection;
  }>({});

  // Layer toggling
  const handleToggleLayer = (key: keyof LayerVisibility) => {
    setLayersVisibility((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      applyLayerVisibility(next);
      return next;
    });
  };

  const handleToggleAllLayers = (enable: boolean) => {
    const updated: LayerVisibility = {
      shakemap: enable,
      insar: enable,
      buildings3d: enable,
      isochrones: enable,
      faults: enable,
      stations: enable,
      liquefaction: enable,
    };
    setLayersVisibility(updated);
    applyLayerVisibility(updated);
  };

  // Sync visibility with MapLibre layers
  const applyLayerVisibility = (vis: LayerVisibility) => {
    const map = mapRef.current;
    if (!map) return;

    const setVis = (layerId: string, visible: boolean) => {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
      }
    };

    setVis('shakemap-points', vis.shakemap);
    setVis('shakemap-labels', vis.shakemap);
    setVis('insar-fill', vis.insar);
    setVis('buildings-3d', vis.buildings3d);
    setVis('isochrones-fill', vis.isochrones);
    setVis('isochrones-line', vis.isochrones);
    setVis('faults-line', vis.faults);
    setVis('faults-glow', vis.faults);
    setVis('stations-circles', vis.stations);
    setVis('stations-pulse', vis.stations);
    setVis('liquefaction-fill', vis.liquefaction);
  };

  // Populate data into MapLibre
  const updateMapData = useCallback(
    (data: {
      shakeMap: GeoJSON.FeatureCollection;
      insarDpm: GeoJSON.FeatureCollection;
      buildings: GeoJSON.FeatureCollection;
      isochrones: GeoJSON.FeatureCollection;
      faultLines: GeoJSON.FeatureCollection;
      stations: GeoJSON.FeatureCollection;
      liquefaction: GeoJSON.FeatureCollection;
    }) => {
      const map = mapRef.current;
      if (!map) return;

      const setSourceData = (sourceId: string, geojson: GeoJSON.FeatureCollection) => {
        const src = map.getSource(sourceId) as maplibregl.GeoJSONSource | undefined;
        if (src) {
          src.setData(geojson);
        }
      };

      setSourceData('shakemap-source', data.shakeMap);
      setSourceData('insar-source', data.insarDpm);
      setSourceData('buildings-source', data.buildings);
      setSourceData('isochrones-source', data.isochrones);
      setSourceData('faults-source', data.faultLines);
      setSourceData('stations-source', data.stations);
      setSourceData('liquefaction-source', data.liquefaction);

      currentDataRef.current = {
        shakeMap: data.shakeMap,
        insarDpm: data.insarDpm,
      };
    },
    []
  );

  // Load Scenario Data
  const runScenario = useCallback(
    async (scenario: EarthquakeScenario, customPga?: number) => {
      setLoading(true);
      try {
        const result = await loadScenarioData(scenario, customPga);
        setMetrics(result.metrics);
        setIsLiveApi(result.isLiveApi);
        updateMapData({
          shakeMap: result.shakeMap,
          insarDpm: result.insarDpm,
          buildings: result.buildings,
          isochrones: result.isochrones,
          faultLines: result.faultLines,
          stations: result.stations,
          liquefaction: result.liquefaction,
        });
      } catch (err) {
        console.error('Error running scenario:', err);
      } finally {
        setLoading(false);
      }
    },
    [updateMapData]
  );

  // Initialize MapLibre
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    // Centered on Antakya, SE Turkey [36.160, 36.202]
    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: DARK_BASEMAP_STYLE,
      center: [36.160, 36.202],
      zoom: 13.8,
      pitch: 52,
      bearing: -20,
      antialias: true,
      maxPitch: 85,
    });

    map.addControl(new NavigationControl({ visualizePitch: true }), 'bottom-right');
    map.addControl(new ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-left');
    map.addControl(new FullscreenControl(), 'bottom-right');

    map.on('mousemove', (e) => {
      setCurrentCoords({
        lat: e.lngLat.lat,
        lng: e.lngLat.lng,
      });
    });

    map.on('load', () => {
      // 1. InSAR DPM Source & Layer
      map.addSource('insar-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      map.addLayer({
        id: 'insar-fill',
        type: 'fill',
        source: 'insar-source',
        paint: {
          'fill-color': [
            'interpolate',
            ['linear'],
            ['get', 'dpm'],
            0.25,
            'rgba(99, 102, 241, 0.2)',
            0.45,
            'rgba(168, 85, 247, 0.45)',
            0.7,
            'rgba(236, 72, 153, 0.7)',
          ],
          'fill-outline-color': 'rgba(168, 85, 247, 0.35)',
        },
      });

      // 2. Isochrones Source & Layers
      map.addSource('isochrones-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      map.addLayer({
        id: 'isochrones-fill',
        type: 'fill',
        source: 'isochrones-source',
        paint: {
          'fill-color': [
            'match',
            ['get', 'cutoff_minutes'],
            5,
            'rgba(6, 182, 212, 0.22)',
            10,
            'rgba(245, 158, 11, 0.16)',
            15,
            'rgba(139, 92, 246, 0.10)',
            'rgba(6, 182, 212, 0.15)',
          ],
        },
      });

      map.addLayer({
        id: 'isochrones-line',
        type: 'line',
        source: 'isochrones-source',
        paint: {
          'line-color': [
            'match',
            ['get', 'cutoff_minutes'],
            5,
            '#06b6d4',
            10,
            '#f59e0b',
            15,
            '#8b5cf6',
            '#06b6d4',
          ],
          'line-width': 2.2,
          'line-dasharray': [3, 1],
        },
      });

      // 3. ShakeMap Ground Motion Source & Layers
      map.addSource('shakemap-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      map.addLayer({
        id: 'shakemap-points',
        type: 'circle',
        source: 'shakemap-source',
        paint: {
          'circle-radius': [
            'interpolate',
            ['linear'],
            ['zoom'],
            6,
            4,
            9,
            7,
            14,
            12,
          ],
          'circle-color': [
            'interpolate',
            ['linear'],
            ['get', 'mmi'],
            4.0,
            '#10b981',
            5.5,
            '#eab308',
            7.0,
            '#f97316',
            8.5,
            '#ef4444',
            10.0,
            '#881337',
          ],
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 0.85,
        },
      });

      // 4. 3D Building Footprints (Extruded & Color-coded by EMS-98 Damage Grade)
      map.addSource('buildings-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      map.addLayer({
        id: 'buildings-3d',
        type: 'fill-extrusion',
        source: 'buildings-source',
        paint: {
          'fill-extrusion-color': [
            'match',
            ['get', 'damage_grade'],
            'D4_Collapse',
            '#ef4444', // Crimson Deep Red for Collapse
            'D3_Extensive',
            '#f97316', // Orange for Extensive
            'D2_Moderate',
            '#eab308', // Amber / Yellow for Moderate
            'D1_Slight',
            '#10b981', // Emerald Green for Slight
            '#38bdf8', // Default Cyan
          ],
          'fill-extrusion-height': ['get', 'height'],
          'fill-extrusion-base': 0,
          'fill-extrusion-opacity': 0.88,
        },
      });

      // Interactive Click Popup for Buildings
      map.on('click', 'buildings-3d', (e) => {
        if (!e.features || e.features.length === 0) return;
        const feat = e.features[0];
        const props = feat.properties as any;
        const coordinates = (e.lngLat);

        const gradeClass =
          props.damage_grade === 'D4_Collapse'
            ? 'badge-catastrophic'
            : props.damage_grade === 'D3_Extensive'
            ? 'badge-severe'
            : props.damage_grade === 'D2_Moderate'
            ? 'badge-warning'
            : 'status-online';

        const content = `
          <div class="popup-bld-header">
            <span class="popup-bld-id">${props.building_id || 'Building Footprint'}</span>
            <span class="hazard-badge ${gradeClass}">${props.damage_grade || 'Unknown'}</span>
          </div>
          <div class="popup-row">
            <span>Typology:</span>
            <span class="popup-val">${props.typology || 'RC Frame'}</span>
          </div>
          <div class="popup-row">
            <span>Height / Floors:</span>
            <span class="popup-val">${props.height}m (${props.floors} fl)</span>
          </div>
          <div class="popup-row">
            <span>Occupants:</span>
            <span class="popup-val">${props.occupancy}</span>
          </div>
          <div class="popup-row">
            <span>PGA Input:</span>
            <span class="popup-val font-mono">${props.pga_g} g</span>
          </div>
          <div class="popup-row">
            <span>Collapse Probability:</span>
            <span class="popup-val font-mono text-rose-400">${(props.p_collapse * 100).toFixed(1)}%</span>
          </div>
          <div class="popup-row">
            <span>Est. Fatalities:</span>
            <span class="popup-val font-mono text-red-500">${props.estimated_fatalities}</span>
          </div>
        `;

        if (popupRef.current) popupRef.current.remove();
        popupRef.current = new Popup({ offset: 15, maxWidth: '300px' })
          .setLngLat(coordinates)
          .setHTML(content)
          .addTo(map);
      });

      // Change cursor on building hover
      map.on('mouseenter', 'buildings-3d', () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', 'buildings-3d', () => {
        map.getCanvas().style.cursor = '';
      });

      // Click on ShakeMap points
      map.on('click', 'shakemap-points', (e) => {
        if (!e.features || e.features.length === 0) return;
        const props = e.features[0].properties as any;
        const coords = e.lngLat;

        const content = `
          <div class="popup-bld-header">
            <span class="popup-bld-id">ShakeMap Sensor</span>
            <span class="hazard-badge badge-severe">MMI ${props.mmi}</span>
          </div>
          <div class="popup-row">
            <span>PGA:</span>
            <span class="popup-val font-mono">${props.pga_g} g</span>
          </div>
          <div class="popup-row">
            <span>PGV:</span>
            <span class="popup-val font-mono">${props.pgv_cms} cm/s</span>
          </div>
          <div class="popup-row">
            <span>Epicentral Dist:</span>
            <span class="popup-val font-mono">${props.dist_km || '~'} km</span>
          </div>
        `;

        if (popupRef.current) popupRef.current.remove();
        popupRef.current = new Popup({ offset: 10 })
          .setLngLat(coords)
          .setHTML(content)
          .addTo(map);
      });

      // 5. MTA Active Fault Lines
      map.addSource('faults-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      map.addLayer({
        id: 'faults-glow',
        type: 'line',
        source: 'faults-source',
        paint: {
          'line-color': '#ef4444',
          'line-width': 8,
          'line-opacity': 0.35,
          'line-blur': 3,
        },
      });

      map.addLayer({
        id: 'faults-line',
        type: 'line',
        source: 'faults-source',
        paint: {
          'line-color': '#ff2d55',
          'line-width': 3.2,
          'line-opacity': 0.95,
        },
      });

      // Click on Fault Line
      map.on('click', 'faults-line', (e) => {
        if (!e.features || e.features.length === 0) return;
        const props = e.features[0].properties as any;
        const coords = e.lngLat;

        const content = `
          <div class="popup-bld-header">
            <span class="popup-bld-id text-red-400">Tectonic Fault Trace</span>
            <span class="hazard-badge badge-severe">${props.mechanism || 'Fault'}</span>
          </div>
          <div class="popup-row">
            <span>Name:</span>
            <span class="popup-val font-semibold text-rose-300">${props.name}</span>
          </div>
          <div class="popup-row">
            <span>Slip Rate:</span>
            <span class="popup-val font-mono">${props.slip_rate_mm_yr} mm/yr</span>
          </div>
          <div class="popup-row">
            <span>Length:</span>
            <span class="popup-val font-mono">${props.length_km} km</span>
          </div>
          <div class="popup-row">
            <span>Last Major Rupture:</span>
            <span class="popup-val text-amber-400">${props.last_rupture || 'Active'}</span>
          </div>
        `;

        if (popupRef.current) popupRef.current.remove();
        popupRef.current = new Popup({ offset: 10 })
          .setLngLat(coords)
          .setHTML(content)
          .addTo(map);
      });

      // 6. AFAD Strong-Motion Stations
      map.addSource('stations-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      map.addLayer({
        id: 'stations-pulse',
        type: 'circle',
        source: 'stations-source',
        paint: {
          'circle-radius': 14,
          'circle-color': '#06b6d4',
          'circle-opacity': 0.25,
        },
      });

      map.addLayer({
        id: 'stations-circles',
        type: 'circle',
        source: 'stations-source',
        paint: {
          'circle-radius': 7,
          'circle-color': '#0891b2',
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 0.95,
        },
      });

      // Click on Strong-Motion Station
      map.on('click', 'stations-circles', (e) => {
        if (!e.features || e.features.length === 0) return;
        const props = e.features[0].properties as any;
        const coords = e.lngLat;

        const content = `
          <div class="popup-bld-header">
            <span class="popup-bld-id text-cyan-400">AFAD Seismometer</span>
            <span class="hazard-badge status-online">${props.code}</span>
          </div>
          <div class="popup-row">
            <span>Station Name:</span>
            <span class="popup-val font-semibold">${props.name}</span>
          </div>
          <div class="popup-row">
            <span>Recorded PGA:</span>
            <span class="popup-val font-mono text-rose-400">${props.pga_recorded_g} g</span>
          </div>
          <div class="popup-row">
            <span>Recorded PGV:</span>
            <span class="popup-val font-mono text-amber-300">${props.pgv_recorded_cms} cm/s</span>
          </div>
          <div class="popup-row">
            <span>Observed MMI:</span>
            <span class="popup-val font-mono text-purple-300">MMI ${props.mmi_observed}</span>
          </div>
          <div class="popup-row">
            <span>Soil Vs30:</span>
            <span class="popup-val font-mono">${props.vs30_ms} m/s</span>
          </div>
        `;

        if (popupRef.current) popupRef.current.remove();
        popupRef.current = new Popup({ offset: 10 })
          .setLngLat(coords)
          .setHTML(content)
          .addTo(map);
      });

      // 7. Soil Liquefaction Susceptibility (Asi River Basin Alluvium)
      map.addSource('liquefaction-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      map.addLayer({
        id: 'liquefaction-fill',
        type: 'fill',
        source: 'liquefaction-source',
        paint: {
          'fill-color': [
            'interpolate',
            ['linear'],
            ['get', 'lpi'],
            2.0,
            'rgba(20, 184, 166, 0.22)',
            8.0,
            'rgba(245, 158, 11, 0.40)',
            15.0,
            'rgba(239, 68, 68, 0.65)',
          ],
          'fill-outline-color': 'rgba(20, 184, 166, 0.45)',
        },
      });

      // Click on Liquefaction Zone
      map.on('click', 'liquefaction-fill', (e) => {
        if (!e.features || e.features.length === 0) return;
        const props = e.features[0].properties as any;
        const coords = e.lngLat;

        const badgeClass =
          props.hazard_class === 'Very High'
            ? 'badge-catastrophic'
            : props.hazard_class === 'High'
            ? 'badge-severe'
            : 'badge-warning';

        const content = `
          <div class="popup-bld-header">
            <span class="popup-bld-id text-teal-400">Soil Liquefaction</span>
            <span class="hazard-badge ${badgeClass}">${props.hazard_class}</span>
          </div>
          <div class="popup-row">
            <span>Zone:</span>
            <span class="popup-val text-gray-300">${props.zone || 'Floodplain'}</span>
          </div>
          <div class="popup-row">
            <span>Liquefaction Index (LPI):</span>
            <span class="popup-val font-mono text-rose-400 font-bold">${props.lpi}</span>
          </div>
          <div class="popup-row">
            <span>Est. Lateral Spread:</span>
            <span class="popup-val font-mono text-amber-300 font-bold">${props.lateral_spread_m || 0} m</span>
          </div>
          <div class="popup-row">
            <span>Groundwater Depth:</span>
            <span class="popup-val font-mono">${props.gw_depth_m || '~1.5'} m</span>
          </div>
        `;

        if (popupRef.current) popupRef.current.remove();
        popupRef.current = new Popup({ offset: 10 })
          .setLngLat(coords)
          .setHTML(content)
          .addTo(map);
      });

      // Load initial scenario data
      runScenario(PRESET_SCENARIOS[0]);
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [runScenario]);

  // Handle Scenario Selection
  const handleSelectScenario = (id: string) => {
    const target = PRESET_SCENARIOS.find((s) => s.id === id);
    if (!target) return;
    setActiveScenario(target);
    runScenario(target);

    // Pan camera smoothly based on scenario focus
    if (mapRef.current) {
      if (id === 'pazarcik') {
        mapRef.current.flyTo({
          center: [36.160, 36.202],
          zoom: 13.8,
          pitch: 55,
          bearing: -15,
          speed: 1.2,
        });
      } else if (id === 'elbistan') {
        mapRef.current.flyTo({
          center: [36.165, 36.205],
          zoom: 13.2,
          pitch: 45,
          bearing: 10,
          speed: 1.2,
        });
      }
    }
  };

  // Handle Custom Simulation Execution
  const handleRunCustomSimulation = (params: CustomSimulationParams) => {
    const customScenario: EarthquakeScenario = {
      id: 'custom',
      name: `Custom Simulation (Mw ${params.magnitude.toFixed(1)})`,
      shortName: `Custom Mw ${params.magnitude.toFixed(1)}`,
      magnitude: params.magnitude,
      depthKm: params.depthKm,
      epicenter: [params.epicenterLon, params.epicenterLat],
      faultMechanism: params.faultMechanism,
      description: `User-defined scenario with depth ${params.depthKm}km, Vs30 ${params.vs30}m/s.`,
      dateStr: 'Custom Run',
    };
    setActiveScenario(customScenario);
    runScenario(customScenario);

    if (mapRef.current) {
      mapRef.current.flyTo({
        center: [params.epicenterLon, params.epicenterLat],
        zoom: 13.5,
        pitch: 50,
        bearing: -10,
        speed: 1.2,
      });
    }
  };

  // Camera presets
  const handleCameraPreset = (preset: 'antakya-3d' | 'regional' | 'hospital') => {
    if (!mapRef.current) return;
    if (preset === 'antakya-3d') {
      mapRef.current.flyTo({
        center: [36.160, 36.202],
        zoom: 14.2,
        pitch: 60,
        bearing: -25,
        speed: 1.4,
      });
    } else if (preset === 'regional') {
      mapRef.current.flyTo({
        center: [36.5, 36.8],
        zoom: 8.4,
        pitch: 0,
        bearing: 0,
        speed: 1.4,
      });
    } else if (preset === 'hospital') {
      mapRef.current.flyTo({
        center: [36.162, 36.204],
        zoom: 15.2,
        pitch: 50,
        bearing: 40,
        speed: 1.4,
      });
    }
  };

  const handleExportGeoJSON = () => {
    const data = currentDataRef.current.shakeMap;
    if (!data || !data.features || data.features.length === 0) {
      alert('No ShakeMap data available to export yet.');
      return;
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/geo+json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `zeminrisk_${activeScenario.id}_shakemap.geojson`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app-container">
      {/* 1. Header Bar */}
      <Header
        currentCoordinates={currentCoords}
        isLiveApi={isLiveApi}
        activeScenarioName={activeScenario.name}
      />

      {/* 2. Top-Center Live Metrics Panel */}
      <MetricsPanel metrics={metrics} loading={loading} />

      {/* 3. Floating Left Panel: Layer Controls & Scenario Selector */}
      <aside className="gis-floating-left">
        <ScenarioSelector
          scenarios={PRESET_SCENARIOS}
          activeScenarioId={activeScenario.id}
          onSelectScenario={handleSelectScenario}
          onOpenCustomModal={() => setIsCustomModalOpen(true)}
          loading={loading}
        />

        <LayerControls
          visibility={layersVisibility}
          onToggle={handleToggleLayer}
          onToggleAll={handleToggleAllLayers}
        />
      </aside>

      {/* 4. Floating Right Panel: Legend & Details */}
      <aside className="gis-floating-right">
        <Legend visibility={layersVisibility} />
      </aside>

      {/* 5. Camera View Presets */}
      <div className="camera-controls">
        <button
          className="cam-btn"
          onClick={() => handleCameraPreset('antakya-3d')}
          title="Tilt camera for 3D building perspective"
        >
          <Building size={14} className="text-cyan-400" />
          <span>Antakya 3D</span>
        </button>
        <button
          className="cam-btn"
          onClick={() => handleCameraPreset('regional')}
          title="Zoom out to regional ShakeMap"
        >
          <Activity size={14} className="text-amber-400" />
          <span>Regional ShakeMap</span>
        </button>
        <button
          className="cam-btn"
          onClick={() => handleCameraPreset('hospital')}
          title="Focus on emergency hospital dispatch"
        >
          <Compass size={14} className="text-purple-400" />
          <span>Response Hub</span>
        </button>
        <button
          className="cam-btn"
          onClick={() => {
            setSpectrumData({
              title: 'Antakya Central Basin',
              pga: metrics?.maxPga ?? 1.05,
              highlightPeriod: 0.5,
            });
            setIsSpectrumModalOpen(true);
          }}
          title="Inspect Response Spectrum Sa(T) vs TBDY-2018"
        >
          <TrendingUp size={14} className="text-rose-400" />
          <span>Response Spectrum</span>
        </button>
        <button
          className="cam-btn"
          onClick={handleExportGeoJSON}
          title="Download calibrated ShakeMap GeoJSON"
        >
          <Download size={14} className="text-emerald-400" />
          <span>Export GeoJSON</span>
        </button>
      </div>

      {/* 6. Custom Simulation Modal */}
      <CustomSimulationModal
        isOpen={isCustomModalOpen}
        onClose={() => setIsCustomModalOpen(false)}
        onRunSimulation={handleRunCustomSimulation}
      />

      {/* 7. Response Spectrum Modal */}
      <ResponseSpectrumModal
        isOpen={isSpectrumModalOpen}
        onClose={() => setIsSpectrumModalOpen(false)}
        title={spectrumData.title}
        pga={spectrumData.pga}
        highlightPeriod={spectrumData.highlightPeriod}
      />

      {/* 8. Interactive MapLibre WebGL Viewport */}
      <div ref={mapContainerRef} className="map-viewport" />
    </div>
  );
};

export default App;
