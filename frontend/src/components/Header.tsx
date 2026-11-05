import React, { useState, useEffect } from 'react';
import { Activity, Radio, Clock, Navigation, ShieldCheck, Database } from 'lucide-react';

interface HeaderProps {
  currentCoordinates: { lat: number; lng: number };
  isLiveApi: boolean;
  activeScenarioName: string;
}

export const Header: React.FC<HeaderProps> = ({
  currentCoordinates,
  isLiveApi,
  activeScenarioName,
}) => {
  const [utcTime, setUtcTime] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const iso = now.toISOString().replace('T', ' ').substring(0, 19);
      setUtcTime(`${iso} UTC`);
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="gis-header">
      <div className="header-brand">
        <div className="brand-logo-glow">
          <Activity className="icon-pulse text-cyan-400" size={26} />
        </div>
        <div>
          <div className="brand-title-wrap">
            <h1 className="brand-title">ZeminRisk</h1>
            <span className="brand-tag">v2.4 GIS</span>
          </div>
          <p className="brand-subtitle">Seismic Hazard & Digital Twin Platform</p>
        </div>
      </div>

      <div className="header-center-info">
        <div className="scenario-chip">
          <span className="chip-indicator"></span>
          <span className="chip-label">Active Scenario:</span>
          <span className="chip-value">{activeScenarioName}</span>
        </div>
      </div>

      <div className="header-meta">
        {/* Live Coordinate readout */}
        <div className="meta-box coords-box" title="Center Coordinates">
          <Navigation size={14} className="meta-icon text-cyan-400" />
          <span className="coords-text font-mono">
            {currentCoordinates.lat.toFixed(4)}°N, {currentCoordinates.lng.toFixed(4)}°E
          </span>
        </div>

        {/* UTC Clock */}
        <div className="meta-box clock-box" title="Global Coordinated Time">
          <Clock size={14} className="meta-icon text-blue-400" />
          <span className="clock-text font-mono">{utcTime || 'Syncing...'}</span>
        </div>

        {/* System & API Status Badge */}
        <div className={`status-badge ${isLiveApi ? 'status-online' : 'status-fallback'}`}>
          <span className="status-dot"></span>
          {isLiveApi ? (
            <>
              <Database size={13} className="inline mr-1" />
              <span>LIVE API (PORT 8000)</span>
            </>
          ) : (
            <>
              <ShieldCheck size={13} className="inline mr-1" />
              <span>CALIBRATED TWIN</span>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
