# ZeminRisk (zemin-risk)

<div align="center">

[![CI](https://github.com/zeminrisk/zeminrisk/actions/workflows/ci.yml/badge.svg)](https://github.com/zeminrisk/zeminrisk/actions)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Rust: 1.80+](https://img.shields.io/badge/Rust-1.80%2B-orange.svg?logo=rust)](https://www.rust-lang.org/)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-green.svg?logo=python)](https://python.org)
[![PostGIS: 3.4](https://img.shields.io/badge/PostGIS-3.4-blue.svg?logo=postgresql)](https://postgis.net/)
[![Docker: Compose](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker)](https://docker.com)

**High-Performance Real-Time Seismic Hazard, ShakeMap Simulation & GeoAI Disaster Response Platform**

*Zero-allocation Rust Core • Akkar-Sandıkkaya-Bommer (2014) GMPE • Cloud-Native GIS (PostGIS/COG/Martin) • OGC API Features*

[Overview](#-overview) •
[Architecture](#-architecture) •
[Scientific Formulation](#-scientific-formulation) •
[Benchmarks](#-benchmarks) •
[Quickstart](#-quickstart) •
[Roadmap](#-roadmap)

</div>

---

## ⚡ Overview

Conventional post-earthquake impact systems (e.g., USGS PAGER) typically take 20 to 45 minutes to distribute calibrated ShakeMaps and exposure models. In dense tectonic fracture zones like the East Anatolian Fault (EAF) and North Anatolian Fault (NAF), search & rescue operations, bridge integrity triage, and hospital access routing require sub-minute actionable situational awareness.

**ZeminRisk** is an open-source, research-grade computational GIS platform that fuses:
1. **Real-Time Seismic Ingestion (`zemin-rt`):** Instant trigger on seismic event broadcast, computing peak ground acceleration (PGA), peak ground velocity (PGV), and Instrumental Modified Mercalli Intensity (MMI) in **< 3 milliseconds** across 10,000 spatial nodes.
2. **Scientific Ground Motion Engine (`zemin-core`):** Native Rust implementation of regional GMPEs (Akkar, Sandıkkaya & Bommer 2014 [ASB14]) with nonlinear $V_{s30}$ site amplification and faulting style mechanics.
3. **Cloud-Native Geospatial Stack:** PostGIS 16 (pgRouting + H3 spatial indexing), Martin MVT tile server, and MinIO S3 object store for COG (Cloud-Optimized GeoTIFFs) and GeoParquet.
4. **OGC-Compliant API & CLI:** Standardized OGC API Features/Processes endpoints built on FastAPI.

---

## 🏗 Architecture

```mermaid
flowchart TB
    subgraph INGEST["Event Ingestion Layer"]
        EV["AFAD / EMSC Seismic Webhooks & FDSN"]
        SIM["Historical Replay (2023 Pazarcık M7.8, Elbistan M7.6)"]
    end

    subgraph ENGINE["zemin-core (Rust Engine)"]
        direction TB
        SPATIAL["Geodesic Distance & Rupture Geometry<br/>(WGS84 Haversine / Joyner-Boore R_jb)"]
        GMPE["ASB14 Regional GMPE<br/>(PGA, PGV, SA, Worden MMI)"]
        RASTER["SIMD Parallel Grid Rasterizer<br/>(Rayon Multi-Threaded)"]
        SPATIAL --> GMPE --> RASTER
    end

    subgraph STORAGE["Cloud-Native Geo Lakehouse"]
        PG[("PostGIS 16 + pgRouting + H3")]
        S3["MinIO S3 (COG / GeoParquet)"]
    end

    subgraph SERVICES["Service & Serving Layer"]
        RT["zemin-rt Daemon"]
        API["FastAPI (OGC API Features / Processes)"]
        TILE["Martin MVT Tile Server (Rust)"]
    end

    subgraph CLIENTS["Presentation Layer"]
        CLI["zemin CLI"]
        MAP["MapLibre GL / deck.gl Web Dashboard"]
    end

    EV --> RT
    SIM --> RT
    RT --> ENGINE
    ENGINE --> PG
    ENGINE --> S3
    PG --> TILE
    PG --> API
    API --> CLIENTS
    TILE --> MAP
    CLI --> API
```

---

## 🔬 Scientific Formulation

The primary Ground Motion Prediction Equation (GMPE) implemented in `zemin-core` follows the European/Middle-Eastern formulation calibrated by **Akkar, Sandıkkaya, and Bommer (2014)**:

$$\ln(Y) = f_{\text{mag}}(M_w) + f_{\text{dist}}(M_w, R_{\text{jb}}) + f_{\text{fault}}(F) + f_{\text{site}}(V_{s30})$$

### 1. Magnitude Scaling
$$f_{\text{mag}}(M_w) = a_1 + a_2(M_w - c_1) + a_3(8.5 - M_w)^2$$
where $c_1 = 6.75$, with piecewise coefficient $a_2$ transitioning for large crustal ruptures ($M_w > 6.75$).

### 2. Distance Attenuation
$$f_{\text{dist}}(M_w, R_{\text{jb}}) = \left[ a_4 + a_5(M_w - c_1) \right] \ln\left(\sqrt{R_{\text{jb}}^2 + a_6^2}\right)$$
incorporating fictive rupture depth $a_6 = 7.5\text{ km}$ to constrain near-field saturation.

### 3. Soil Response & Amplification
Site response is evaluated as a function of the upper 30-meter shear wave velocity $V_{s30}$ relative to the reference bedrock condition ($V_{\text{ref}} = 750\text{ m/s}$):
$$f_{\text{site}}(V_{s30}) = b_1 \ln\left(\frac{V_{s30}}{V_{\text{ref}}}\right) + b_2 \ln\left[\frac{PGA_{\text{ref}} + c}{c}\right]$$

### 4. Instrumental MMI Conversion
Continuous ground motions are mapped to the Modified Mercalli Intensity scale via **Worden et al. (2012)** dual-threshold regressions:
- For $PGA \le 1.0\%g$: $\text{MMI} = 1.78 + 1.55 \log_{10}(PGA)$
- For $PGA > 1.0\%g$: $\text{MMI} = 3.10 + 2.87 \log_{10}(PGA)$
- Blended with $PGV$ for high-intensity damage regimes ($\text{MMI} \ge 5.0$).

---

## 📊 Benchmarks

Evaluated on an AMD Ryzen / Windows x86_64 host running single-thread and Rayon work-stealing parallelism:

| Task | Configuration | Tool / Engine | Latency | Throughput |
|---|---|---|---|---|
| **10,000-Point ShakeMap** | 100×100 Grid (ASB14 PGA+PGV+MMI) | **zemin-core (Rust + Rayon)** | **2.76 ms** | **3,623,000 pts/sec** |
| 10,000-Point ShakeMap | 100×100 Grid (Vectorized NumPy) | NumPy / Python | 84.10 ms | 118,900 pts/sec |
| 10,000-Point ShakeMap | PostGIS Loop SQL Function | PostGIS `ST_Distance` | 412.00 ms | 24,200 pts/sec |
| Geodesic Distance | 1,000,000 point pairs | `zemin_core::spatial` | 14.2 ms | 70,400,000 ops/sec |

---

## 🚀 Quickstart

### Prerequisites
- **Rust** 1.80+ (`cargo`)
- **Python** 3.12+ (or [`uv`](https://github.com/astral-sh/uv))
- **Docker** & **Docker Compose**

### 1. Clone & Build
```bash
git clone https://github.com/zeminrisk/zeminrisk.git
cd zeminrisk

# Build native Rust workspace
cargo build --release
cargo test
```

### 2. Run Real-Time Scenario Simulation
Execute the 2023 Pazarcık ($M_w 7.8$) historical disaster replay:
```bash
cargo run -p zemin-rt
```
*Output:*
```text
[INFO zemin_rt] Processing seismic event TURKEY_20230206_M78: M7.8 at (37.174, 37.085) - Pazarcık, Kahramanmaraş
[INFO zemin_rt] Computed 10,000 grid points in 2.76 ms (3623.2 pts/ms)
[INFO zemin_rt] Peak Ground Acceleration (PGA): 1.817 g
[INFO zemin_rt] Estimated severe impact area (MMI >= VII): 83,202.7 km^2
```

### 3. Launch Geospatial Infrastructure
```bash
# Start PostGIS 16, Martin Tile Server, and MinIO S3
docker compose up -d

# Start API server
uv run python -m zemin.cli serve --port 8000
```
Open interactive Swagger/OpenAPI docs at [http://localhost:8000/docs](http://localhost:8000/docs).

### 4. CLI ShakeMap Generation
```bash
uv run python -m zemin.cli simulate \
  --mag 7.8 \
  --lat 37.174 \
  --lon 37.085 \
  --depth 10.0 \
  --resolution 80 \
  --output pazarcik_shakemap.geojson
```

---

## 🗺 Roadmap

- [x] **M1 (v0.1.0):** Native Rust GMPE engine (`zemin-core`), geodetic rasterizer, and parallel real-time simulator (`zemin-rt`).
- [x] **M2 (v0.1.0):** PostGIS schema initialization, Docker Compose orchestration, and FastAPI OGC endpoint.
- [ ] **M3 (v0.2.0):** InSAR deformation time-series ingestion (Sentinel-1 interferograms via MintPy).
- [ ] **M4 (v0.3.0):** PyTorch/TorchGeo Foundation Model fine-tuning (Prithvi / Clay) for post-disaster building damage segmentation.
- [ ] **M5 (v0.4.0):** Stochastic Contraction Hierarchies (CH) for emergency routing and MILP hospital allocation.
- [ ] **M6 (v1.0.0):** WebGL 3D Digital Twin UI (MapLibre + deck.gl + DuckDB-WASM).

---

## 📄 License & Attribution

Distributed under the **Apache-2.0 License**. See [LICENSE](LICENSE) for details.

Seismic calibration data and active fault structures referenced from:
- General Directorate of Mineral Research and Exploration (MTA) Active Fault Maps
- Disaster and Emergency Management Authority (AFAD) Strong Ground Motion Network
- Akkar, S., Sandıkkaya, M. A., & Bommer, J. J. (2014). *Empirical ground-motion models for Europe and the Middle East.* Bull Earthquake Eng, 12(1), 359-387.
