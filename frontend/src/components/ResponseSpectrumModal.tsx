import React from 'react';
import { X, Activity, ShieldAlert, TrendingUp } from 'lucide-react';

interface ResponseSpectrumModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  pga?: number;
  highlightPeriod?: number; // e.g. estimated fundamental period of inspected building
}

export const ResponseSpectrumModal: React.FC<ResponseSpectrumModalProps> = ({
  isOpen,
  onClose,
  title = 'Antakya Central Basin',
  pga = 1.05,
  highlightPeriod,
}) => {
  if (!isOpen) return null;

  // Standard engineering periods (s)
  const periods = [0.01, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0];

  // Ground motion demand Sa(T)
  const demandSa = periods.map((t) => {
    if (t <= 0.02) return pga;
    const peakT = 0.28;
    const width = 0.55;
    const shape = Math.exp(-Math.pow(Math.log(t) - Math.log(peakT), 2) / (2 * width * width));
    return pga * (1.0 + 1.85 * shape);
  });

  // TBDY-2018 Design Spectrum (SDS = 1.50g, SD1 = 0.45g, Ta = 0.06s, Tb = 0.30s)
  const sDs = 1.50;
  const sD1 = 0.45;
  const tA = 0.06;
  const tB = 0.30;
  const designSa = periods.map((t) => {
    if (t < tA) return (0.4 + 0.6 * (t / tA)) * sDs;
    if (t <= tB) return sDs;
    return sD1 / t;
  });

  const maxDemand = Math.max(...demandSa);
  const maxDesign = Math.max(...designSa);
  const yMax = Math.ceil(Math.max(maxDemand, maxDesign) * 1.15);

  // SVG Chart Dimensions
  const width = 580;
  const height = 260;
  const padLeft = 45;
  const padBottom = 35;
  const padTop = 20;
  const padRight = 20;

  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const scaleX = (t: number) => padLeft + (t / 4.0) * plotW;
  const scaleY = (sa: number) => padTop + plotH - (sa / yMax) * plotH;

  const demandPath = periods
    .map((t, idx) => `${idx === 0 ? 'M' : 'L'} ${scaleX(t).toFixed(1)} ${scaleY(demandSa[idx]).toFixed(1)}`)
    .join(' ');

  const designPath = periods
    .map((t, idx) => `${idx === 0 ? 'M' : 'L'} ${scaleX(t).toFixed(1)} ${scaleY(designSa[idx]).toFixed(1)}`)
    .join(' ');

  return (
    <div className="modal-backdrop">
      <div className="modal-dialog" style={{ maxWidth: '640px' }}>
        <div className="modal-header">
          <div className="flex items-center gap-2">
            <Activity className="text-rose-400" size={18} />
            <h2 className="modal-title">Response Spectrum Sa(T) vs TBDY-2018</h2>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body" style={{ gap: '16px' }}>
          <div className="text-xs text-gray-400 flex items-center justify-between border-b border-gray-800 pb-2">
            <span>Location: <strong className="text-gray-200">{title}</strong></span>
            <span>Regime: <strong className="text-cyan-400">Shallow Crustal Near-Fault (ASB14)</strong></span>
          </div>

          {/* Metrics summary cards */}
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-gray-900/60 p-2.5 rounded border border-gray-800">
              <div className="text-[10px] text-gray-400 uppercase font-semibold">Peak Demand Sa</div>
              <div className="text-lg font-mono font-bold text-rose-400">{maxDemand.toFixed(2)} g</div>
              <div className="text-[10px] text-gray-500">at T ≈ 0.28s</div>
            </div>
            <div className="bg-gray-900/60 p-2.5 rounded border border-gray-800">
              <div className="text-[10px] text-gray-400 uppercase font-semibold">TBDY-2018 SDS</div>
              <div className="text-lg font-mono font-bold text-cyan-400">{sDs.toFixed(2)} g</div>
              <div className="text-[10px] text-gray-500">Plateau [0.06 - 0.30s]</div>
            </div>
            <div className="bg-gray-900/60 p-2.5 rounded border border-gray-800">
              <div className="text-[10px] text-gray-400 uppercase font-semibold">Demand / Capacity</div>
              <div className="text-lg font-mono font-bold text-amber-400">
                {(maxDemand / sDs).toFixed(2)}×
              </div>
              <div className="text-[10px] text-amber-500 font-semibold">Severe Inelastic Demand</div>
            </div>
          </div>

          {/* SVG Response Spectrum Chart */}
          <div className="bg-gray-950 p-3 rounded border border-gray-800 flex flex-col items-center">
            <svg width={width} height={height} className="overflow-visible">
              {/* Horizontal Grid lines */}
              {[0, yMax * 0.25, yMax * 0.5, yMax * 0.75, yMax].map((yVal, i) => (
                <g key={i}>
                  <line
                    x1={padLeft}
                    y1={scaleY(yVal)}
                    x2={width - padRight}
                    y2={scaleY(yVal)}
                    stroke="rgba(255, 255, 255, 0.08)"
                    strokeDasharray="2,2"
                  />
                  <text
                    x={padLeft - 8}
                    y={scaleY(yVal) + 4}
                    fill="#9ca3af"
                    fontSize="10"
                    textAnchor="end"
                    fontFamily="monospace"
                  >
                    {yVal.toFixed(1)}g
                  </text>
                </g>
              ))}

              {/* Vertical Grid lines (Periods) */}
              {[0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0].map((tVal, i) => (
                <g key={i}>
                  <line
                    x1={scaleX(tVal)}
                    y1={padTop}
                    x2={scaleX(tVal)}
                    y2={height - padBottom}
                    stroke="rgba(255, 255, 255, 0.08)"
                    strokeDasharray="2,2"
                  />
                  <text
                    x={scaleX(tVal)}
                    y={height - padBottom + 16}
                    fill="#9ca3af"
                    fontSize="10"
                    textAnchor="middle"
                    fontFamily="monospace"
                  >
                    {tVal}s
                  </text>
                </g>
              ))}

              {/* TBDY-2018 Design Curve */}
              <path d={designPath} fill="none" stroke="#06b6d4" strokeWidth="2.5" strokeDasharray="5,3" />

              {/* Simulated Demand Curve */}
              <path d={demandPath} fill="none" stroke="#ef4444" strokeWidth="2.8" />

              {/* Highlight building period if available */}
              {highlightPeriod && highlightPeriod <= 4.0 && (
                <g>
                  <line
                    x1={scaleX(highlightPeriod)}
                    y1={padTop}
                    x2={scaleX(highlightPeriod)}
                    y2={height - padBottom}
                    stroke="#eab308"
                    strokeWidth="2"
                    strokeDasharray="3,3"
                  />
                  <circle
                    cx={scaleX(highlightPeriod)}
                    cy={scaleY(
                      pga * (1.0 + 1.85 * Math.exp(-Math.pow(Math.log(highlightPeriod) - Math.log(0.28), 2) / (2 * 0.55 * 0.55)))
                    )}
                    r="5"
                    fill="#eab308"
                    stroke="#ffffff"
                    strokeWidth="1.5"
                  />
                  <text
                    x={scaleX(highlightPeriod)}
                    y={padTop - 6}
                    fill="#facc15"
                    fontSize="10"
                    fontWeight="bold"
                    textAnchor="middle"
                  >
                    T_bld ≈ {highlightPeriod.toFixed(2)}s
                  </text>
                </g>
              )}
            </svg>

            {/* Chart Legend */}
            <div className="flex items-center gap-6 mt-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="w-4 h-0.5 bg-red-500 rounded"></span>
                <span className="text-gray-300 font-medium">Simulated Ground Motion Sa(T)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-0.5 border-t-2 border-dashed border-cyan-400"></span>
                <span className="text-gray-300 font-medium">TBDY-2018 Elastic Design Spectrum</span>
              </div>
            </div>
          </div>

          <div className="text-[11px] text-gray-400 bg-amber-500/10 border border-amber-500/20 p-2.5 rounded flex items-start gap-2">
            <ShieldAlert size={16} className="text-amber-400 shrink-0 mt-0.5" />
            <div>
              Near-fault velocity pulses during Mw 7.8 produced spectral accelerations exceeding <strong>5.0g</strong> in the resonance period range (0.15s - 0.45s), overwhelming the elastic code design spectrum (SDS = 1.50g) by over <strong>300%</strong>, causing brittle shear collapse in non-ductile mid-rise reinforced concrete structures.
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="modal-btn-cancel" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
