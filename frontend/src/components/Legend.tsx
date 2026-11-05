import React, { useState } from 'react';
import { Info, ChevronDown, ChevronUp } from 'lucide-react';
import { LayerVisibility } from '../types';

interface LegendProps {
  visibility: LayerVisibility;
}

export const Legend: React.FC<LegendProps> = ({ visibility }) => {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`gis-legend-card ${collapsed ? 'legend-collapsed' : ''}`}>
      <div className="legend-header" onClick={() => setCollapsed(!collapsed)}>
        <div className="flex items-center gap-1.5">
          <Info size={14} className="text-cyan-400" />
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-300">
            Map Legend
          </span>
        </div>
        <button className="legend-toggle-btn">
          {collapsed ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {!collapsed && (
        <div className="legend-body">
          {/* Building Damage Grade Legend */}
          {visibility.buildings3d && (
            <div className="legend-section">
              <div className="legend-section-title">3D Building Damage (EMS-98)</div>
              <div className="legend-items">
                <div className="legend-item">
                  <span className="legend-swatch" style={{ background: '#10b981' }}></span>
                  <span className="legend-text">D1: Slight Damage</span>
                </div>
                <div className="legend-item">
                  <span className="legend-swatch" style={{ background: '#eab308' }}></span>
                  <span className="legend-text">D2: Moderate Damage</span>
                </div>
                <div className="legend-item">
                  <span className="legend-swatch" style={{ background: '#f97316' }}></span>
                  <span className="legend-text">D3: Heavy / Extensive</span>
                </div>
                <div className="legend-item">
                  <span className="legend-swatch" style={{ background: '#ef4444' }}></span>
                  <span className="legend-text">D4: Collapse / Destruction</span>
                </div>
              </div>
            </div>
          )}

          {/* ShakeMap Legend */}
          {visibility.shakemap && (
            <div className="legend-section">
              <div className="legend-section-title">Ground Shaking (PGA / MMI)</div>
              <div className="shakemap-ramp-bar">
                <div className="ramp-gradient"></div>
              </div>
              <div className="ramp-labels text-xs font-mono">
                <span>0.1g (V)</span>
                <span>0.3g (VII)</span>
                <span>0.6g+ (IX+)</span>
              </div>
            </div>
          )}

          {/* InSAR DPM Legend */}
          {visibility.insar && (
            <div className="legend-section">
              <div className="legend-section-title">InSAR Coherence Loss (DPM)</div>
              <div className="legend-items">
                <div className="legend-item">
                  <span className="legend-swatch" style={{ background: '#a855f7', opacity: 0.6 }}></span>
                  <span className="legend-text">High Coherence Loss (&gt; 0.65)</span>
                </div>
                <div className="legend-item">
                  <span className="legend-swatch" style={{ background: '#6366f1', opacity: 0.4 }}></span>
                  <span className="legend-text">Moderate Loss (0.35 - 0.65)</span>
                </div>
              </div>
            </div>
          )}

          {/* Isochrone Legend */}
          {visibility.isochrones && (
            <div className="legend-section">
              <div className="legend-section-title">Emergency Reachability</div>
              <div className="legend-items">
                <div className="legend-item">
                  <span className="legend-line" style={{ borderColor: '#06b6d4' }}></span>
                  <span className="legend-text">&le; 5 min response</span>
                </div>
                <div className="legend-item">
                  <span className="legend-line" style={{ borderColor: '#f59e0b' }}></span>
                  <span className="legend-text">5 - 10 min response</span>
                </div>
                <div className="legend-item">
                  <span className="legend-line" style={{ borderColor: '#8b5cf6' }}></span>
                  <span className="legend-text">10 - 15 min response</span>
                </div>
              </div>
            </div>
          )}

          {/* Fault Line Legend */}
          {visibility.faults && (
            <div className="legend-section">
              <div className="legend-section-title">Active Fault Traces</div>
              <div className="legend-items">
                <div className="legend-item">
                  <span className="legend-line" style={{ borderColor: '#ff2d55', borderWidth: '3px' }}></span>
                  <span className="legend-text">MTA Active Rupture Segment</span>
                </div>
              </div>
            </div>
          )}

          {/* Stations Legend */}
          {visibility.stations && (
            <div className="legend-section">
              <div className="legend-section-title">Strong-Motion Network</div>
              <div className="legend-items">
                <div className="legend-item">
                  <span
                    className="legend-swatch"
                    style={{ background: '#0891b2', borderRadius: '50%', border: '1.5px solid #fff' }}
                  ></span>
                  <span className="legend-text">AFAD Seismometer Station</span>
                </div>
              </div>
            </div>
          )}

          {/* Liquefaction Legend */}
          {visibility.liquefaction && (
            <div className="legend-section">
              <div className="legend-section-title">Soil Liquefaction (LPI)</div>
              <div className="legend-items">
                <div className="legend-item">
                  <span className="legend-swatch" style={{ background: '#ef4444', opacity: 0.65 }}></span>
                  <span className="legend-text">Very High (LPI &gt; 15, Spread &gt; 1m)</span>
                </div>
                <div className="legend-item">
                  <span className="legend-swatch" style={{ background: '#f59e0b', opacity: 0.5 }}></span>
                  <span className="legend-text">High Susceptibility (5 &lt; LPI &le; 15)</span>
                </div>
                <div className="legend-item">
                  <span className="legend-swatch" style={{ background: '#14b8a6', opacity: 0.35 }}></span>
                  <span className="legend-text">Low / Non-Liquefiable (LPI &le; 5)</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
