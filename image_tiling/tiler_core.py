"""
tiler_core.py
Core logic for imagery tiling — no CLI, no GUI, no file watching.

This file exposes a single entrypoint:

    run_tiling(...)

which returns a dictionary summarizing results for each AOI.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List

# Import all functions from your existing script that remain unchanged
# (We'll paste them in next)
from shapely.ops import unary_union
from shapely.geometry import Point, box
from shapely.ops import transform as shapely_transform
from pyproj import CRS, Transformer
import geopandas as gpd
import csv

# ------------------------------------------------------
# PUBLIC API ENTRYPOINT
# ------------------------------------------------------

def run_tiling(
    use_circle_aoi: bool,
    aoi_input_path: Optional[str],
    tile_size_km: float,
    out_dir: str,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    radius_km: Optional[float] = None,
    min_tile_inside_fraction: float = 0.2,
    coverage_floor: float = 0.98,
    minimal_coverage_floor: float = 0.95,
    offsets_x: List[float] = None,
    offsets_y: List[float] = None,
) -> Dict[str, Any]:
    """
    Main tiling function. Returns a dictionary summarizing AOI results, instead of printing or writing directly.
    GUI / CLI / watchdog scripts will call this.
    """

    from .tiler_internal import (
        build_aois_from_file,
        build_circle_aoi_local,
        generate_tiles_with_offset,
        prune_tiles,
        compute_solution_metrics,
        get_local_crs,
        transform_geom,
        export_tiles_geojson,
        export_centerpoints_csv,
        export_kml,
    )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {"aois": []}

    # Build AOIs ----------------------------
    if use_circle_aoi:
        aois = [{
            "name": "circle_aoi",
            "type": "circle",
            "geom_wgs": None,
            "center_lat": center_lat,
            "center_lon": center_lon,
            "radius_km": radius_km,
        }]
    else:
        aois = build_aois_from_file(Path(aoi_input_path))

    # Offsets default
    if offsets_x is None: offsets_x = [0.0, 0.25, 0.5, 0.75]
    if offsets_y is None: offsets_y = [0.0, 0.25, 0.5, 0.75]

    # Process each AOI ----------------------
    for aoi in aois:
        local_results = _process_single_aoi(
            aoi=aoi,
            tile_size_km=tile_size_km,
            base_out_dir=out_dir,
            min_tile_inside_fraction=min_tile_inside_fraction,
            coverage_floor=coverage_floor,
            minimal_coverage_floor=minimal_coverage_floor,
            offsets_x=offsets_x,
            offsets_y=offsets_y,
        )
        results["aois"].append(local_results)

    return results


# ------------------------------------------------------
# INTERNAL DRIVER (formerly main() loop)
# ------------------------------------------------------

def _process_single_aoi(
    aoi: Dict[str, Any],
    tile_size_km: float,
    base_out_dir: Path,
    min_tile_inside_fraction: float,
    coverage_floor: float,
    minimal_coverage_floor: float,
    offsets_x: List[float],
    offsets_y: List[float],
) -> Dict[str, Any]:
    """
    Internal version of process_single_aoi that returns metadata instead of printing and writing files.
    """

    # TODO: paste your existing internal logic here,
    # but instead of printing, accumulate a dictionary like:

    result = {
        "aoi_name": aoi["name"],
        "strategies": {
            # filled in later like:
            # "balanced": {"tiles": [...], "metrics": {...}}
        },
        "output_paths": {}
    }

    # return result
    return result
