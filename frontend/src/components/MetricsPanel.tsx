import React from 'react';
import { HazardMetrics } from '../types';
import { Zap, AlertTriangle, Building2, Users2, Satellite, Gauge } from 'lucide-react';

interface MetricsPanelProps {
  metrics: HazardMetrics | null;
  loading: boolean;
}

// Convert numeric MMI to Roman Numeral representation
function formatMmiRoman(mmi: number): string {
  if (mmi >= 10) return 'X+ (Extreme)';
  if (mmi >= 9) return 'IX (Violent)';
  if (mmi >= 8) return 'VIII (Severe)';
  if (mmi >= 7) return 'VII (Very Strong)';
  if (mmi >= 6) return 'VI (Strong)';
  if (mmi >= 5) return 'V (Moderate)';
  return 'IV (Light)';
}

export const MetricsPanel: React.FC<MetricsPanelProps> = ({ metrics, loading }) => {
  if (!metrics) {
    return (
      <div className="metrics-container loading-state">
        <div className="metrics-skeleton">Aggregating seismic sensors & synthetic twin...</div>
      </div>
    );
  }

  // PGA hazard color category
  const getPgaBadgeClass = (pga: number) => {
    if (pga >= 0.6) return 'badge-catastrophic';
    if (pga >= 0.35) return 'badge-severe';
    if (pga >= 0.15) return 'badge-moderate';
    return 'badge-minor';
  };

  return (
    <div className={`metrics-container ${loading ? 'opacity-70 pointer-events-none' : ''}`}>
      <div className="metrics-grid">
        {/* Metric 1: Peak Ground Acceleration */}
        <div className="metric-card card-pga">
          <div className="metric-header">
            <div className="metric-title-group">
              <Zap className="metric-icon text-amber-400" size={18} />
              <span className="metric-label">Max PGA</span>
            </div>
            <span className={`hazard-badge ${getPgaBadgeClass(metrics.maxPga)}`}>
              {metrics.maxPga >= 0.5 ? 'Violent' : 'Strong'}
            </span>
          </div>
          <div className="metric-value-row">
            <span className="metric-main-val font-mono">{metrics.maxPga.toFixed(3)}</span>
            <span className="metric-unit">g</span>
          </div>
          <div className="metric-subtext">Peak Ground Accel at target grid</div>
          <div className="metric-bar-bg">
            <div
              className="metric-bar-fill fill-pga"
              style={{ width: `${Math.min(100, (metrics.maxPga / 1.2) * 100)}%` }}
            ></div>
          </div>
        </div>

        {/* Metric 2: Mercalli Intensity (MMI) */}
        <div className="metric-card card-mmi">
          <div className="metric-header">
            <div className="metric-title-group">
              <Gauge className="metric-icon text-rose-400" size={18} />
              <span className="metric-label">Mercalli Intensity</span>
            </div>
            <span className="hazard-badge badge-catastrophic">MMI</span>
          </div>
          <div className="metric-value-row">
            <span className="metric-main-val font-mono">{metrics.maxMmi.toFixed(1)}</span>
            <span className="metric-tag">{formatMmiRoman(metrics.maxMmi)}</span>
          </div>
          <div className="metric-subtext">Worden et al. ShakeMap scale</div>
          <div className="metric-bar-bg">
            <div
              className="metric-bar-fill fill-mmi"
              style={{ width: `${Math.min(100, (metrics.maxMmi / 10.0) * 100)}%` }}
            ></div>
          </div>
        </div>

        {/* Metric 3: Collapsed Buildings % */}
        <div className="metric-card card-collapse">
          <div className="metric-header">
            <div className="metric-title-group">
              <Building2 className="metric-icon text-red-500" size={18} />
              <span className="metric-label">Collapsed Buildings</span>
            </div>
            <span className="hazard-badge badge-catastrophic">Grade D4</span>
          </div>
          <div className="metric-value-row">
            <span className="metric-main-val font-mono">{metrics.collapsedPercent}%</span>
            <span className="metric-counts font-mono">
              ({metrics.collapsedBuildings}/{metrics.totalBuildings} bldgs)
            </span>
          </div>
          <div className="metric-subtext">EMS-98 structural complete failure</div>
          <div className="metric-bar-bg">
            <div
              className="metric-bar-fill fill-collapse"
              style={{ width: `${Math.min(100, metrics.collapsedPercent)}%` }}
            ></div>
          </div>
        </div>

        {/* Metric 4: Estimated Fatalities */}
        <div className="metric-card card-fatalities">
          <div className="metric-header">
            <div className="metric-title-group">
              <Users2 className="metric-icon text-orange-400" size={18} />
              <span className="metric-label">Est. Fatalities</span>
            </div>
            <span className="hazard-badge badge-warning">Cas. Model</span>
          </div>
          <div className="metric-value-row">
            <span className="metric-main-val font-mono">{metrics.estimatedFatalities}</span>
            <span className="metric-unit">est. victims</span>
          </div>
          <div className="metric-subtext">Coburn & Spence lethality matrix</div>
          <div className="metric-bar-bg">
            <div
              className="metric-bar-fill fill-fatalities"
              style={{ width: `${Math.min(100, (metrics.estimatedFatalities / 150) * 100)}%` }}
            ></div>
          </div>
        </div>

        {/* Metric 5: Severe Coherence Loss % */}
        <div className="metric-card card-insar">
          <div className="metric-header">
            <div className="metric-title-group">
              <Satellite className="metric-icon text-purple-400" size={18} />
              <span className="metric-label">Severe InSAR Loss</span>
            </div>
            <span className="hazard-badge badge-radar">Sentinel-1</span>
          </div>
          <div className="metric-value-row">
            <span className="metric-main-val font-mono">{metrics.severeCoherenceLossPercent}%</span>
            <span className="metric-counts font-mono">DPM &gt; 0.45</span>
          </div>
          <div className="metric-subtext">Co-seismic CCD radar decorrelation</div>
          <div className="metric-bar-bg">
            <div
              className="metric-bar-fill fill-insar"
              style={{ width: `${Math.min(100, metrics.severeCoherenceLossPercent)}%` }}
            ></div>
          </div>
        </div>
      </div>
    </div>
  );
};
