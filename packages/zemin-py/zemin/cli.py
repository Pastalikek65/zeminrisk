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

    # assess command
    assess_parser = subparsers.add_parser(
        "assess", help="Assess building stock damage and fatalities"
    )
    assess_parser.add_argument("--pga", type=float, default=0.65, help="PGA in g (default: 0.65)")
    assess_parser.add_argument(
        "--count", type=int, default=50, help="Number of sample buildings (default: 50)"
    )
    assess_parser.add_argument("--output", type=str, help="Output GeoJSON path")

    # insar command
    insar_parser = subparsers.add_parser("insar", help="Simulate InSAR Damage Proxy Map (DPM)")
    insar_parser.add_argument("--mag", type=float, default=7.8, help="Magnitude")
    insar_parser.add_argument("--cog", type=str, help="Export result as GeoTIFF / COG")

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

    elif args.command == "assess":
        from zemin.damage import assess_building_stock_damage, generate_sample_antakya_buildings

        blds = generate_sample_antakya_buildings(count=args.count)
        res = assess_building_stock_damage(blds, pga_g=args.pga)
        collapsed = (res["damage_grade"] == "D4_Collapse").sum()
        fatalities = res["estimated_fatalities"].sum()
        print("🏢 Building Damage Assessment Complete:")
        print(f"   Evaluated: {len(res)} buildings")
        print(f"   Collapsed (D4): {collapsed} ({collapsed / len(res) * 100:.1f}%)")
        print(f"   Estimated Fatalities: {fatalities:.1f}")

        if args.output:
            res.to_file(args.output, driver="GeoJSON")
            print(f"💾 Saved assessed footprints to {args.output}")

    elif args.command == "insar":
        from zemin.insar import simulate_insar_damage_proxy, write_cog

        bounds = (35.9, 35.9, 36.4, 36.4)
        epicenter = (36.160, 36.202)
        dpm_res = simulate_insar_damage_proxy(bounds, epicenter, magnitude=args.mag)
        print("🛰️ InSAR Damage Proxy Map (DPM) Generated:")
        print(f"   Severe Damage Ratio: {dpm_res.severe_damage_ratio * 100:.2f}%")
        print(f"   Mean Coherence Loss: {float(dpm_res.dpm.mean()):.3f}")

        if args.cog:
            write_cog(args.cog, dpm_res.dpm, dpm_res.bounds)
            print(f"💾 Exported Cloud-Optimized GeoTIFF to {args.cog}")


if __name__ == "__main__":
    main()
