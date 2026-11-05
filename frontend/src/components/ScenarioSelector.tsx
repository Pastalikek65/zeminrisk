import React from 'react';
import { EarthquakeScenario } from '../types';
import { Zap, SlidersHorizontal, AlertCircle, Compass } from 'lucide-react';

interface ScenarioSelectorProps {
  scenarios: EarthquakeScenario[];
  activeScenarioId: string;
  onSelectScenario: (scenarioId: string) => void;
  onOpenCustomModal: () => void;
  loading: boolean;
}

export const ScenarioSelector: React.FC<ScenarioSelectorProps> = ({
  scenarios,
  activeScenarioId,
  onSelectScenario,
  onOpenCustomModal,
  loading,
}) => {
  return (
    <div className="scenario-selector-panel">
      <div className="scenario-selector-title">
        <Zap className="text-amber-400" size={16} />
        <span>Scenario Replay & Simulation</span>
      </div>

      <div className="scenario-buttons-row">
        {scenarios.map((sc) => {
          const isActive = sc.id === activeScenarioId;
          const isCustom = sc.id === 'custom';

          return (
            <button
              key={sc.id}
              disabled={loading}
              onClick={() => {
                if (isCustom) {
                  onSelectScenario('custom');
                  onOpenCustomModal();
                } else {
                  onSelectScenario(sc.id);
                }
              }}
              className={`scenario-btn ${isActive ? 'scenario-btn-active' : ''} ${
                isCustom ? 'scenario-btn-custom' : ''
              }`}
            >
              <div className="scenario-btn-content">
                <div className="scenario-btn-top">
                  {isCustom ? (
                    <SlidersHorizontal size={14} className="text-cyan-400" />
                  ) : (
                    <span className="scenario-mag-tag">Mw {sc.magnitude.toFixed(1)}</span>
                  )}
                  <span className="scenario-btn-label">{sc.shortName}</span>
                </div>
                {sc.dateStr && (
                  <span className="scenario-btn-date font-mono text-xs">{sc.dateStr.split(' ')[0]}</span>
                )}
              </div>
              {isActive && <div className="scenario-active-glow"></div>}
            </button>
          );
        })}
      </div>
    </div>
  );
};
