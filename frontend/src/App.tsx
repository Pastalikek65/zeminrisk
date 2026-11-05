import React, { useEffect, useRef, useState, useCallback } from 'react';
import maplibregl, { Map as MapLibreMap, NavigationControl, ScaleControl, FullscreenControl, Popup } from 'maplibre-gl';
import { Header } from './components/Header';
import { MetricsPanel } from './components/MetricsPanel';
import { LayerControls } from './components/LayerControls';
import { ScenarioSelector } from './components/ScenarioSelector';
import { CustomSimulationModal } from './components/CustomSimulationModal';
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
import { Eye, Compass, Building, Activity, RotateCcw } from 'lucide-react';
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
  const [currentCoords, setCurrentCoords] = useState<{ lat: number; lng: number }>({
    lat: 36.202,
    lng: 36.160,
  });

  const [layersVisibility, setLayersVisibility] = useState<LayerVisibility>({
    shakemap: true,
    insar: true,
    buildings3d: true,
    isochrones: true,
  });

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
  };

  // Populate data into MapLibre
  const updateMapData = useCallback(
    (data: {
      shakeMap: GeoJSON.FeatureCollection;
      insarDpm: GeoJSON.FeatureCollection;
      buildings: GeoJSON.FeatureCollection;
      isochrones: GeoJSON.FeatureCollection;
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
      </div>

      {/* 6. Custom Simulation Modal */}
      <CustomSimulationModal
        isOpen={isCustomModalOpen}
        onClose={() => setIsCustomModalOpen(false)}
        onRunSimulation={handleRunCustomSimulation}
      />

      {/* 7. Interactive MapLibre WebGL Viewport */}
      <div ref={mapContainerRef} className="map-viewport" />
    </div>
  );
};

export default App;
