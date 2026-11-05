import React, { useState } from 'react';
import { CustomSimulationParams } from '../types';
import { Sliders, X, Play, RefreshCw, Info } from 'lucide-react';

interface CustomSimulationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRunSimulation: (params: CustomSimulationParams) => void;
  initialParams?: Partial<CustomSimulationParams>;
}

export const CustomSimulationModal: React.FC<CustomSimulationModalProps> = ({
  isOpen,
  onClose,
  onRunSimulation,
  initialParams,
}) => {
  const [magnitude, setMagnitude] = useState<number>(initialParams?.magnitude ?? 7.4);
  const [depthKm, setDepthKm] = useState<number>(initialParams?.depthKm ?? 8.0);
  const [epicenterLat, setEpicenterLat] = useState<number>(initialParams?.epicenterLat ?? 36.202);
  const [epicenterLon, setEpicenterLon] = useState<number>(initialParams?.epicenterLon ?? 36.160);
  const [vs30, setVs30] = useState<number>(initialParams?.vs30 ?? 320);
  const [mechanism, setMechanism] = useState<'strike-slip' | 'normal' | 'reverse'>('strike-slip');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onRunSimulation({
      magnitude,
      depthKm,
      epicenterLat,
      epicenterLon,
      faultMechanism: mechanism,
      vs30,
    });
    onClose();
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-dialog">
        <div className="modal-header">
          <div className="flex items-center gap-2">
            <Sliders className="text-cyan-400" size={18} />
            <h2 className="modal-title">Custom Seismic Digital Twin Simulation</h2>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          <div className="form-group">
            <div className="form-label-row">
              <label>Moment Magnitude (Mw):</label>
              <span className="form-val font-mono text-cyan-400">{magnitude.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min="5.0"
              max="8.2"
              step="0.1"
              value={magnitude}
              onChange={(e) => setMagnitude(parseFloat(e.target.value))}
              className="gis-range"
            />
            <div className="flex justify-between text-xs text-gray-500">
              <span>Mw 5.0 (Moderate)</span>
              <span>Mw 7.0 (Major)</span>
              <span>Mw 8.2 (Great)</span>
            </div>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label>Focal Depth (km):</label>
              <input
                type="number"
                min="1.0"
                max="50.0"
                step="0.5"
                value={depthKm}
                onChange={(e) => setDepthKm(parseFloat(e.target.value))}
                className="gis-input font-mono"
              />
            </div>
            <div className="form-group">
              <label>Vs30 Soil Velocity (m/s):</label>
              <input
                type="number"
                min="150"
                max="1200"
                step="10"
                value={vs30}
                onChange={(e) => setVs30(parseFloat(e.target.value))}
                className="gis-input font-mono"
              />
            </div>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label>Epicenter Latitude (°N):</label>
              <input
                type="number"
                step="0.001"
                value={epicenterLat}
                onChange={(e) => setEpicenterLat(parseFloat(e.target.value))}
                className="gis-input font-mono"
              />
            </div>
            <div className="form-group">
              <label>Epicenter Longitude (°E):</label>
              <input
                type="number"
                step="0.001"
                value={epicenterLon}
                onChange={(e) => setEpicenterLon(parseFloat(e.target.value))}
                className="gis-input font-mono"
              />
            </div>
          </div>

          <div className="form-group">
            <label>Fault Rupture Kinematics:</label>
            <div className="mechanism-options">
              {(['strike-slip', 'normal', 'reverse'] as const).map((m) => (
                <button
                  type="button"
                  key={m}
                  onClick={() => setMechanism(m)}
                  className={`mech-btn ${mechanism === m ? 'mech-btn-active' : ''}`}
                >
                  {m.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="simulation-info-callout">
            <Info size={16} className="text-blue-400 shrink-0" />
            <p className="text-xs text-gray-300">
              Evaluates Akkar-Sandikkaya-Bommer GMPE attenuation, EMS-98 typology fragility curves,
              and debris-obstructed routing graph in real time.
            </p>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary">
              <Play size={15} />
              Execute Simulation
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
