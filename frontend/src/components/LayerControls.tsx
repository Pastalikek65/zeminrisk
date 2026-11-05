import React from 'react';
import { LayerVisibility } from '../types';
import { Layers, Eye, EyeOff, Boxes, Activity, Satellite, Route, Zap, Radio, Droplets } from 'lucide-react';

interface LayerControlsProps {
  visibility: LayerVisibility;
  onToggle: (layerKey: keyof LayerVisibility) => void;
  onToggleAll: (enable: boolean) => void;
}

export const LayerControls: React.FC<LayerControlsProps> = ({
  visibility,
  onToggle,
  onToggleAll,
}) => {
  const allEnabled = Object.values(visibility).every(Boolean);

  return (
    <div className="layer-controls-panel">
      <div className="layer-controls-header">
        <div className="flex items-center gap-2">
          <Layers className="text-cyan-400" size={17} />
          <span className="font-semibold text-sm tracking-wide text-gray-200">GIS Layers</span>
        </div>
        <button
          className="toggle-all-btn"
          onClick={() => onToggleAll(!allEnabled)}
          title={allEnabled ? 'Hide all layers' : 'Show all layers'}
        >
          {allEnabled ? 'Mute All' : 'Show All'}
        </button>
      </div>

      <div className="layers-list">
        {/* Layer 1: ShakeMap Ground Motion */}
        <div
          className={`layer-item ${visibility.shakemap ? 'layer-active' : 'layer-inactive'}`}
          onClick={() => onToggle('shakemap')}
        >
          <div className="layer-left">
            <div className="layer-icon-badge bg-amber-500/10 text-amber-400">
              <Activity size={15} />
            </div>
            <div className="layer-info">
              <div className="layer-name">ShakeMap Ground Motion</div>
              <div className="layer-meta-desc">PGA & MMI Seismic Intensity Points</div>
            </div>
          </div>
          <button className="layer-visibility-toggle">
            {visibility.shakemap ? (
              <Eye size={16} className="text-cyan-400" />
            ) : (
              <EyeOff size={16} className="text-gray-500" />
            )}
          </button>
        </div>

        {/* Layer 2: InSAR Coherence Loss */}
        <div
          className={`layer-item ${visibility.insar ? 'layer-active' : 'layer-inactive'}`}
          onClick={() => onToggle('insar')}
        >
          <div className="layer-left">
            <div className="layer-icon-badge bg-purple-500/10 text-purple-400">
              <Satellite size={15} />
            </div>
            <div className="layer-info">
              <div className="layer-name">InSAR Coherence Loss</div>
              <div className="layer-meta-desc">Damage Proxy Map (DPM 0.0 - 1.0)</div>
            </div>
          </div>
          <button className="layer-visibility-toggle">
            {visibility.insar ? (
              <Eye size={16} className="text-cyan-400" />
            ) : (
              <EyeOff size={16} className="text-gray-500" />
            )}
          </button>
        </div>

        {/* Layer 3: 3D Building Footprints */}
        <div
          className={`layer-item ${visibility.buildings3d ? 'layer-active' : 'layer-inactive'}`}
          onClick={() => onToggle('buildings3d')}
        >
          <div className="layer-left">
            <div className="layer-icon-badge bg-rose-500/10 text-rose-400">
              <Boxes size={15} />
            </div>
            <div className="layer-info">
              <div className="layer-name">3D Building Footprints</div>
              <div className="layer-meta-desc">Extruded & Classified (EMS-98 D1-D4)</div>
            </div>
          </div>
          <button className="layer-visibility-toggle">
            {visibility.buildings3d ? (
              <Eye size={16} className="text-cyan-400" />
            ) : (
              <EyeOff size={16} className="text-gray-500" />
            )}
          </button>
        </div>

        {/* Layer 4: Reachability Isochrones */}
        <div
          className={`layer-item ${visibility.isochrones ? 'layer-active' : 'layer-inactive'}`}
          onClick={() => onToggle('isochrones')}
        >
          <div className="layer-left">
            <div className="layer-icon-badge bg-emerald-500/10 text-emerald-400">
              <Route size={15} />
            </div>
            <div className="layer-info">
              <div className="layer-name">Emergency Reachability</div>
              <div className="layer-meta-desc">5m, 10m, 15m Post-Debris Isochrones</div>
            </div>
          </div>
          <button className="layer-visibility-toggle">
            {visibility.isochrones ? (
              <Eye size={16} className="text-cyan-400" />
            ) : (
              <EyeOff size={16} className="text-gray-500" />
            )}
          </button>
        </div>

        {/* Layer 5: MTA Active Tectonic Faults */}
        <div
          className={`layer-item ${visibility.faults ? 'layer-active' : 'layer-inactive'}`}
          onClick={() => onToggle('faults')}
        >
          <div className="layer-left">
            <div className="layer-icon-badge bg-red-500/10 text-red-400">
              <Zap size={15} />
            </div>
            <div className="layer-info">
              <div className="layer-name">Active Fault Traces</div>
              <div className="layer-meta-desc">MTA Tectonic Rupture Lines</div>
            </div>
          </div>
          <button className="layer-visibility-toggle">
            {visibility.faults ? (
              <Eye size={16} className="text-cyan-400" />
            ) : (
              <EyeOff size={16} className="text-gray-500" />
            )}
          </button>
        </div>

        {/* Layer 6: AFAD Strong-Motion Stations */}
        <div
          className={`layer-item ${visibility.stations ? 'layer-active' : 'layer-inactive'}`}
          onClick={() => onToggle('stations')}
        >
          <div className="layer-left">
            <div className="layer-icon-badge bg-cyan-500/10 text-cyan-400">
              <Radio size={15} />
            </div>
            <div className="layer-info">
              <div className="layer-name">Strong-Motion Stations</div>
              <div className="layer-meta-desc">AFAD Recorded PGA/PGV Seismometers</div>
            </div>
          </div>
          <button className="layer-visibility-toggle">
            {visibility.stations ? (
              <Eye size={16} className="text-cyan-400" />
            ) : (
              <EyeOff size={16} className="text-gray-500" />
            )}
          </button>
        </div>

        {/* Layer 7: Soil Liquefaction Susceptibility */}
        <div
          className={`layer-item ${visibility.liquefaction ? 'layer-active' : 'layer-inactive'}`}
          onClick={() => onToggle('liquefaction')}
        >
          <div className="layer-left">
            <div className="layer-icon-badge bg-teal-500/10 text-teal-400">
              <Droplets size={15} />
            </div>
            <div className="layer-info">
              <div className="layer-name">Soil Liquefaction (LPI)</div>
              <div className="layer-meta-desc">Asi River Alluvial Floodplain & Lateral Spread</div>
            </div>
          </div>
          <button className="layer-visibility-toggle">
            {visibility.liquefaction ? (
              <Eye size={16} className="text-cyan-400" />
            ) : (
              <EyeOff size={16} className="text-gray-500" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
