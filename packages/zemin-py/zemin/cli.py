"""Command-line interface for ZeminRisk."""

import argparse
import asyncio
import json

import uvicorn

from zemin.api import EarthquakeEventRequest, simulate_shakemap


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="zemin",
        description="ZeminRisk CLI: Seismic Hazard, ShakeMap & Disaster Analytics",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start the OGC API / FastAPI server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable hot reload")

    # simulate command
    sim_parser = subparsers.add_parser(
        "simulate", help="Simulate a ShakeMap for an earthquake event"
    )
    sim_parser.add_argument("--mag", type=float, required=True, help="Moment magnitude (Mw)")
    sim_parser.add_argument("--lat", type=float, required=True, help="Epicenter latitude")
    sim_parser.add_argument("--lon", type=float, required=True, help="Epicenter longitude")
    sim_parser.add_argument(
        "--depth", type=float, default=10.0, help="Focal depth in km (default: 10.0)"
    )
    sim_parser.add_argument(
        "--mechanism",
        choices=["strike-slip", "normal", "reverse"],
        default="strike-slip",
        help="Fault mechanism",
    )
    sim_parser.add_argument(
        "--resolution", type=int, default=60, help="Grid size NxN (default: 60)"
    )
    sim_parser.add_argument("--output", type=str, help="Output path for GeoJSON result")

    args = parser.parse_args()

    if args.command == "serve":
        print(f"🚀 Starting ZeminRisk API on http://{args.host}:{args.port}")
        uvicorn.run("zemin.api:app", host=args.host, port=args.port, reload=args.reload)

    elif args.command == "simulate":
        req = EarthquakeEventRequest(
            magnitude=args.mag,
            depth_km=args.depth,
            epicenter_lat=args.lat,
            epicenter_lon=args.lon,
            fault_mechanism=args.mechanism,
            grid_resolution=args.resolution,
        )
        res = asyncio.run(simulate_shakemap(req))
        meta = res.metadata
        print("✅ Simulation complete:")
        print(f"   Max PGA: {meta['max_pga_g']} g")
        print(f"   Max MMI: {meta['max_mmi']}")
        print(f"   Points evaluated: {meta['total_points_evaluated']}")
        print(f"   Damaging points (MMI >= 5): {meta['points_exported']}")

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(res.geojson, f, indent=2)
            print(f"💾 Saved GeoJSON to {args.output}")
        else:
            print(f"GeoJSON Preview: {len(res.geojson['features'])} features generated.")


if __name__ == "__main__":
    main()
