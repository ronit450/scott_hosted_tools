#!/usr/bin/env python

"""
Daedalus — AOI Tiling Engine
(Previously tiling_v6.py)

Features:

- AOI INPUT:
    * Circle AOI (point + radius) OR
    * AOIs loaded from a vector file:
        - GeoJSON / .json
        - Shapefile (.shp)
        - GeoPackage (.gpkg)
        - KML (.kml)
        - KMZ (.kmz)
    * If AOI file:
        - Each Polygon/MultiPolygon feature -> separate AOI
        - Each Point -> separate AOI buffered by POINT_RADIUS_KM

- For each AOI:
    * Uses a local UTM CRS (based on AOI centroid).
    * Generates fixed-size square tiles (e.g., 5x5 km).
    * Tests multiple grid offsets.
    * Filters out tiles that barely touch the AOI.
    * Greedy-prunes tiles while maintaining coverage ≥ COVERAGE_FLOOR.
    * Computes metrics and produces FIVE strategies:
        balanced, full, minimal, max_coverage, compact.

- Outputs per AOI:
    * <strategy>_centerpoints.csv  (with rich metadata)
    * <strategy>_tiles_and_aoi.geojson (with metadata)
    * tiling_solutions.kml (AOI + all strategies)
    * strategy_summary.csv (one row per strategy with key metrics)
"""

import xml.etree.ElementTree as ET
import csv
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List

from shapely.geometry import Point, box
from shapely.ops import unary_union
from pyproj import CRS, Transformer
import geopandas as gpd
from shapely.ops import transform as shapely_transform


# ------------------------------------------------------
# CONFIG (defaults – used by main() and as run_tiling defaults)
# ------------------------------------------------------

# 1) Choose circle mode (point + radius) OR file-based AOIs
USE_CIRCLE_AOI: bool = False

# If USE_CIRCLE_AOI = True, these are used:
CENTER_LAT = 55.61918         # AOI center latitude
CENTER_LON = 29.21093         # AOI center longitude
RADIUS_KM = 10                # Circle radius in km

# If USE_CIRCLE_AOI = False, set AOI_INPUT to a vector file:
#   - .geojson/.json
#   - .shp
#   - .gpkg
#   - .kml
#   - .kmz
AOI_INPUT: Optional[Path] = Path(
    r"F:\TayBec llc\DataDocs - Documents\001-Mission\11080 – Emergent\09-Route & AOI Analysis in Lebanon\Data Layers\OLD - Do not use\Lebanon Route Main Hwys.kml"
)
AOI_LAYER: Optional[str] = None   # For multi-layer formats (e.g., GPKG); usually None is fine.

# Global radius (km) for point features when AOI_INPUT is used:
POINT_RADIUS_KM = 10.0

# Tile configuration (fixed – analyst chooses this)
TILE_SIZE_KM = 5              # Square tile size in km

OUT_DIR = Path(r"F:\Tiling_Imagery_Output\v6")   # Change as needed

# Fractions of tile size to use as grid offsets in X/Y.
OFFSET_FRACTIONS_X = [0.0, 0.25, 0.5, 0.75]
OFFSET_FRACTIONS_Y = [0.0, 0.25, 0.5, 0.75]

# ---- Tile usefulness / coverage controls ----

# Minimum fraction of tile area that must be inside AOI to be considered at all
MIN_TILE_INSIDE_FRACTION = 0.20   # 0.20 = at least 20% of tile inside AOI

# Minimum overall AOI coverage after pruning "sliver" tiles
COVERAGE_FLOOR = 0.98             # 0.98 = keep at least 98% coverage in pruning

# Coverage requirement for "minimal tiles" solution
MINIMAL_COVERAGE_FLOOR = 0.95     # minimal strategy must cover at least 95% of AOI

# Compact strategy: minimum fraction of each tile that must be inside AOI
# to be considered part of the "core" AOI.
COMPACT_MIN_INSIDE_FRACTION = 0.60


# ------------------------------------------------------
# OUTPUT FILE NAME PATTERNS
# ------------------------------------------------------

def csv_name(strategy: str) -> str:
    return f"{strategy}_centerpoints.csv"


def geojson_name(strategy: str) -> str:
    return f"{strategy}_tiles_and_aoi.geojson"


KML_NAME = "tiling_solutions.kml"
STRATEGY_SUMMARY_NAME = "strategy_summary.csv"


# ------------------------------------------------------
# HELPERS
# ------------------------------------------------------

def get_local_crs(center_lat: float, center_lon: float) -> CRS:
    """
    Manually compute appropriate UTM zone and return a projected CRS.
    """
    zone = int((center_lon + 180) / 6) + 1
    if center_lat >= 0:
        epsg = 32600 + zone
    else:
        epsg = 32700 + zone
    return CRS.from_epsg(epsg)


def transform_geom(geom, transformer: Transformer):
    """
    Generic Shapely geometry transformer using a pyproj Transformer.
    """
    def _func(x, y, z=None):
        return transformer.transform(x, y)
    return shapely_transform(_func, geom)


# ------------------------------------------------------
# AOI BUILDING
# ------------------------------------------------------

def build_circle_aoi_local(center_lat: float, center_lon: float, radius_km: float,
                           transformer_to_local: Transformer):
    """
    Return AOI geometry (circle) in local CRS, plus center and radius in meters.
    """
    cx, cy = transformer_to_local.transform(center_lon, center_lat)
    radius_m = radius_km * 1000.0
    aoi_geom_local = Point(cx, cy).buffer(radius_m)
    return aoi_geom_local, (cx, cy), radius_m


def read_vector_file(path: Path, layer: Optional[str] = None) -> gpd.GeoDataFrame:
    """
    Read AOI vector file.

    - For GeoJSON / SHP / GPKG, we use GeoPandas + Fiona as usual.
    - For KML / KMZ, we **avoid Fiona/GDAL entirely** and parse the XML
      ourselves into Shapely geometries, then build a GeoDataFrame.

    This avoids the 'LIBKML' / 'KML' driver problem inside the frozen EXE.
    """
    suffix = path.suffix.lower()

    # ------------- KML / KMZ: custom parser (no Fiona) -------------
    if suffix in (".kml", ".kmz"):
        # Get KML text either directly or by extracting from KMZ
        if suffix == ".kmz":
            with zipfile.ZipFile(path, "r") as zf, tempfile.TemporaryDirectory() as tmpdir:
                kml_files = [name for name in zf.namelist() if name.lower().endswith(".kml")]
                if not kml_files:
                    raise ValueError("KMZ file does not contain any KML files.")
                first_kml = kml_files[0]
                kml_path = Path(tmpdir) / "doc.kml"
                with zf.open(first_kml) as src, open(kml_path, "wb") as dst:
                    dst.write(src.read())
                kml_file_to_read = kml_path
        else:
            kml_file_to_read = path

        # Parse KML XML
        tree = ET.parse(kml_file_to_read)
        root = tree.getroot()

        # KML namespace handling
        # Typical root tag: '{http://www.opengis.net/kml/2.2}kml'
        ns = {}
        if root.tag.startswith("{") and "}kml" in root.tag:
            uri = root.tag.split("}")[0].strip("{")
            ns["k"] = uri
        else:
            # fallback: no namespace prefix
            ns["k"] = ""

        def findall(elem, tag):
            # Helper that works whether we have a namespace or not
            if ns["k"]:
                return elem.findall(f".//{{{ns['k']}}}{tag}")
            else:
                return elem.findall(f".//{tag}")

        placemarks = findall(root, "Placemark")
        geoms = []
        names = []

        for pm in placemarks:
            # Name (if present)
            name_elem = None
            if ns["k"]:
                name_elem = pm.find(f"{{{ns['k']}}}name")
            else:
                name_elem = pm.find("name")
            pm_name = name_elem.text.strip() if (name_elem is not None and name_elem.text) else None

            # Handle Polygon or MultiGeometry
            polygons = []

            # All Polygon elements under this placemark
            polys = findall(pm, "Polygon")
            for poly in polys:
                # Outer boundary
                outer = None
                if ns["k"]:
                    outer = poly.find(f".//{{{ns['k']}}}outerBoundaryIs/{{{ns['k']}}}LinearRing/{{{ns['k']}}}coordinates")
                else:
                    outer = poly.find(".//outerBoundaryIs/LinearRing/coordinates")

                if outer is None or outer.text is None:
                    continue

                outer_coords = []
                for coord_str in outer.text.strip().split():
                    parts = coord_str.split(",")
                    if len(parts) < 2:
                        continue
                    lon = float(parts[0])
                    lat = float(parts[1])
                    outer_coords.append((lon, lat))

                if len(outer_coords) < 3:
                    continue

                # Inner boundaries (holes) if any
                holes = []
                if ns["k"]:
                    inner_list = poly.findall(
                        f".//{{{ns['k']}}}innerBoundaryIs/{{{ns['k']}}}LinearRing/{{{ns['k']}}}coordinates"
                    )
                else:
                    inner_list = poly.findall(".//innerBoundaryIs/LinearRing/coordinates")

                for inner in inner_list:
                    if inner is None or inner.text is None:
                        continue
                    hole_coords = []
                    for coord_str in inner.text.strip().split():
                        parts = coord_str.split(",")
                        if len(parts) < 2:
                            continue
                        lon = float(parts[0])
                        lat = float(parts[1])
                        hole_coords.append((lon, lat))
                    if len(hole_coords) >= 3:
                        holes.append(hole_coords)

                from shapely.geometry import Polygon
                polygons.append(Polygon(outer_coords, holes))

            if not polygons:
                continue

            # If multiple polygons under one placemark, treat as MultiPolygon
            if len(polygons) == 1:
                geom = polygons[0]
            else:
                from shapely.geometry import MultiPolygon
                geom = MultiPolygon(polygons)

            geoms.append(geom)
            names.append(pm_name if pm_name is not None else "aoi")

        if not geoms:
            raise ValueError(f"No Polygon geometries found in KML: {path}")

        gdf = gpd.GeoDataFrame(
            {"name": names},
            geometry=geoms,
            crs="EPSG:4326",
        )
        return gdf

    # ------------- All other formats: normal GeoPandas -------------
    # GeoJSON, SHP, GPKG, etc. use the existing Fiona/GDAL stack.
    gdf = gpd.read_file(path, layer=layer)
    return gdf




def build_aois_from_file(path: Path, layer: Optional[str]) -> List[Dict[str, Any]]:
    """
    Load AOIs from a vector file.
    - Each Polygon/MultiPolygon is one AOI.
    - Each Point is one AOI buffered by POINT_RADIUS_KM.
    """
    gdf = read_vector_file(path, layer)

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    aois: List[Dict[str, Any]] = []

    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        # Basic name heuristic: use "name" or "Name" or fallback
        name = (
            str(row.get("name"))
            if row.get("name") not in [None, "nan"]
            else row.get("Name", None)
        )
        if name is None:
            name = f"aoi_{idx + 1}"

        gtype = geom.geom_type

        if gtype in ("Polygon", "MultiPolygon"):
            centroid = geom.centroid
            aois.append(
                {
                    "name": str(name),
                    "type": "polygon",
                    "geom_wgs": geom,
                    "center_lat": centroid.y,
                    "center_lon": centroid.x,
                    "radius_km": None,
                }
            )
        elif gtype == "Point":
            # Treat as point+radius AOI
            aois.append(
                {
                    "name": str(name),
                    "type": "point",
                    "geom_wgs": geom,
                    "center_lat": geom.y,
                    "center_lon": geom.x,
                    "radius_km": POINT_RADIUS_KM,
                }
            )
        else:
            # You can add LineString handling here later if needed
            print(f"Skipping unsupported geometry type {gtype} for feature {idx}")

    return aois


def build_aois_with_config(
    use_circle_aoi: bool,
    center_lat: float,
    center_lon: float,
    radius_km: float,
    aoi_input: Optional[Path],
    aoi_layer: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Build AOIs based on explicit config (used by run_tiling).
    """
    if use_circle_aoi:
        return [
            {
                "name": "circle_aoi",
                "type": "circle",
                "geom_wgs": None,
                "center_lat": center_lat,
                "center_lon": center_lon,
                "radius_km": radius_km,
            }
        ]

    if aoi_input is None:
        raise ValueError("aoi_input must be set when use_circle_aoi is False.")

    path = Path(aoi_input) if isinstance(aoi_input, (str, Path)) else aoi_input
    aois_from_file = build_aois_from_file(path, aoi_layer)
    if not aois_from_file:
        raise ValueError(f"No valid AOIs extracted from {path}")
    return aois_from_file


# ------------------------------------------------------
# TILING + METRICS
# ------------------------------------------------------

def generate_tiles_with_offset(aoi_geom_local, tile_size_km: float,
                               offset_x_frac: float, offset_y_frac: float):
    """
    Generate tiles over AOI bounding box with given offset fractions.
    Tiles store geometry and precomputed intersection with AOI in local CRS.
    """
    tile_size_m = tile_size_km * 1000.0
    minx, miny, maxx, maxy = aoi_geom_local.bounds

    # Expand by one tile to avoid clipping edges
    minx -= tile_size_m
    miny -= tile_size_m
    maxx += tile_size_m
    maxy += tile_size_m

    tiles = []
    tile_id = 1
    half = tile_size_m / 2.0

    dx = offset_x_frac * tile_size_m
    dy = offset_y_frac * tile_size_m

    x = minx + half + dx
    while x <= maxx:
        y = miny + half + dy
        while y <= maxy:
            poly = box(x - half, y - half, x + half, y + half)
            if poly.intersects(aoi_geom_local):
                inter = poly.intersection(aoi_geom_local)
                inside_area = inter.area
                tile_area = tile_size_m * tile_size_m
                inside_fraction = inside_area / tile_area if tile_area > 0 else 0.0

                tiles.append(
                    {
                        "tile_id": tile_id,
                        "poly": poly,
                        "cx": x,
                        "cy": y,
                        "intersection": inter,
                        "inside_area": inside_area,
                        "inside_fraction": inside_fraction,
                    }
                )
                tile_id += 1
            y += tile_size_m
        x += tile_size_m

    return tiles


def compute_coverage_from_tiles(aoi_geom_local, tiles):
    """
    Given an AOI and a list of tiles (with 'intersection' precomputed),
    compute coverage area and fraction.
    """
    aoi_area = aoi_geom_local.area
    if not tiles:
        return aoi_area, 0.0

    intersections = [t["intersection"] for t in tiles if not t["intersection"].is_empty]
    if not intersections:
        return aoi_area, 0.0

    coverage_union = unary_union(intersections)
    if coverage_union.is_empty:
        return aoi_area, 0.0

    coverage_area = coverage_union.area
    coverage_fraction = coverage_area / aoi_area if aoi_area > 0 else 0.0
    return aoi_area, coverage_fraction


def prune_tiles(aoi_geom_local, tiles, tile_size_m: float,
                min_inside_fraction: float,
                coverage_floor: float):
    """
    1) Drop tiles whose inside_fraction < min_inside_fraction.
    2) Greedy pruning: remove tiles with smallest inside_area while keeping
       coverage >= coverage_floor.
    """
    # Step 1: drop tiles that barely touch AOI
    filtered = [t for t in tiles if t["inside_fraction"] >= min_inside_fraction]
    if not filtered:
        return tiles

    # Step 2: greedy pruning
    filtered.sort(key=lambda t: t["inside_area"])
    aoi_area = aoi_geom_local.area
    current_tiles = list(filtered)
    aoi_area, current_cov_frac = compute_coverage_from_tiles(aoi_geom_local, current_tiles)

    changed = True
    while changed:
        changed = False
        for t in list(current_tiles):
            candidate_tiles = [x for x in current_tiles if x["tile_id"] != t["tile_id"]]
            _, cov_frac_candidate = compute_coverage_from_tiles(aoi_geom_local, candidate_tiles)
            if cov_frac_candidate >= coverage_floor:
                current_tiles = candidate_tiles
                current_cov_frac = cov_frac_candidate
                changed = True
                break

    current_tiles.sort(key=lambda t: t["tile_id"])
    return current_tiles


def compute_solution_metrics(aoi_geom_local, tiles, tile_size_m: float):
    """
    Compute:
    - coverage_fraction
    - overlap_ratio       (overlap area / coverage area)
    - overlap_percent     (overlap_ratio * 100)
    - overlap_equiv_tiles (overlap area / single tile area)
    - num_tiles
    - score (higher is better)
    """
    aoi_area = aoi_geom_local.area

    if not tiles:
        return {
            "num_tiles": 0,
            "coverage_fraction": 0.0,
            "overlap_ratio": 0.0,
            "overlap_percent": 0.0,
            "overlap_equiv_tiles": 0.0,
            "score": -1e9,
            "coverage_area": 0.0,
            "aoi_area": aoi_area,
        }

    intersections = [t["intersection"] for t in tiles if not t["intersection"].is_empty]
    if not intersections:
        coverage_area = 0.0
    else:
        coverage_union = unary_union(intersections)
        coverage_area = coverage_union.area if not coverage_union.is_empty else 0.0

    coverage_fraction = coverage_area / aoi_area if aoi_area > 0 else 0.0

    num_tiles = len(tiles)
    tile_area = tile_size_m * tile_size_m
    sum_tile_area = num_tiles * tile_area

    if coverage_area > 0:
        overlap_area = max(sum_tile_area - coverage_area, 0.0)
        overlap_ratio = overlap_area / coverage_area if coverage_area > 0 else 0.0
        overlap_equiv_tiles = overlap_area / tile_area if tile_area > 0 else 0.0
    else:
        overlap_area = 0.0
        overlap_ratio = 0.0
        overlap_equiv_tiles = 0.0

    overlap_percent = overlap_ratio * 100.0

    ideal_tiles = max(aoi_area / tile_area, 1.0)

    # Weights: coverage >> overlap >> tile count
    w_overlap = 0.1
    w_tiles = 0.05

    score = (
        coverage_fraction
        - w_overlap * overlap_ratio
        - w_tiles * (num_tiles / ideal_tiles)
    )

    return {
        "num_tiles": num_tiles,
        "coverage_fraction": coverage_fraction,
        "overlap_ratio": overlap_ratio,
        "overlap_percent": overlap_percent,
        "overlap_equiv_tiles": overlap_equiv_tiles,
        "score": score,
        "coverage_area": coverage_area,
        "aoi_area": aoi_area,
    }


# ------------------------------------------------------
# EXPORTS
# ------------------------------------------------------

def export_centerpoints_csv(
    tiles,
    transformer_to_wgs84,
    output_path: Path,
    aoi_name: str,
    strategy_name: str,
    metrics: Dict[str, Any],
    offset_x: float,
    offset_y: float,
):
    """
    Export centerpoints CSV with rich metadata per tile and per strategy.
    """
    rows = []
    for t in tiles:
        cx, cy = t["cx"], t["cy"]
        lon, lat = transformer_to_wgs84.transform(cx, cy)
        rows.append(
            {
                "aoi_name": aoi_name,
                "strategy": strategy_name,
                "tile_id": t["tile_id"],
                "center_lat": lat,
                "center_lon": lon,
                "inside_fraction": t.get("inside_fraction", None),
                "inside_area_m2": t.get("inside_area", None),
                "offset_x_frac": offset_x,
                "offset_y_frac": offset_y,
                "aoi_coverage_fraction": metrics["coverage_fraction"],
                "aoi_coverage_percent": metrics["coverage_fraction"] * 100.0,
                "aoi_overlap_ratio": metrics["overlap_ratio"],
                "aoi_overlap_percent": metrics["overlap_percent"],
                "aoi_overlap_equiv_tiles": metrics["overlap_equiv_tiles"],
                "aoi_num_tiles": metrics["num_tiles"],
            }
        )

    fieldnames = [
        "aoi_name",
        "strategy",
        "tile_id",
        "center_lat",
        "center_lon",
        "inside_fraction",
        "inside_area_m2",
        "offset_x_frac",
        "offset_y_frac",
        "aoi_coverage_fraction",
        "aoi_coverage_percent",
        "aoi_overlap_ratio",
        "aoi_overlap_percent",
        "aoi_overlap_equiv_tiles",
        "aoi_num_tiles",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_tiles_geojson(
    aoi_geom_local,
    tiles,
    transformer_to_wgs84,
    output_path: Path,
    aoi_name: str,
    strategy_name: str,
    metrics: Dict[str, Any],
    offset_x: float,
    offset_y: float,
):
    """
    Export AOI and tiles to GeoJSON with metadata.
    """
    features = []
    feature_types = []
    tile_ids = []
    aoi_names = []
    strategies = []
    inside_fracs = []
    inside_areas = []
    offset_x_list = []
    offset_y_list = []
    aoi_cov_fracs = []
    aoi_cov_percents = []
    aoi_overlap_ratios = []
    aoi_overlap_percents = []
    aoi_overlap_tiles = []
    aoi_num_tiles_list = []

    # AOI
    aoi_wgs = transform_geom(aoi_geom_local, transformer_to_wgs84)
    features.append(aoi_wgs)
    feature_types.append("AOI")
    tile_ids.append(None)
    aoi_names.append(aoi_name)
    strategies.append("AOI")
    inside_fracs.append(None)
    inside_areas.append(None)
    offset_x_list.append(None)
    offset_y_list.append(None)
    aoi_cov_fracs.append(metrics["coverage_fraction"])
    aoi_cov_percents.append(metrics["coverage_fraction"] * 100.0)
    aoi_overlap_ratios.append(metrics["overlap_ratio"])
    aoi_overlap_percents.append(metrics["overlap_percent"])
    aoi_overlap_tiles.append(metrics["overlap_equiv_tiles"])
    aoi_num_tiles_list.append(metrics["num_tiles"])

    # Tiles
    for t in tiles:
        tile_wgs = transform_geom(t["poly"], transformer_to_wgs84)
        features.append(tile_wgs)
        feature_types.append("TILE")
        tile_ids.append(t["tile_id"])
        aoi_names.append(aoi_name)
        strategies.append(strategy_name)
        inside_fracs.append(t.get("inside_fraction", None))
        inside_areas.append(t.get("inside_area", None))
        offset_x_list.append(offset_x)
        offset_y_list.append(offset_y)
        aoi_cov_fracs.append(metrics["coverage_fraction"])
        aoi_cov_percents.append(metrics["coverage_fraction"] * 100.0)
        aoi_overlap_ratios.append(metrics["overlap_ratio"])
        aoi_overlap_percents.append(metrics["overlap_percent"])
        aoi_overlap_tiles.append(metrics["overlap_equiv_tiles"])
        aoi_num_tiles_list.append(metrics["num_tiles"])

    gdf = gpd.GeoDataFrame(
        {
            "feature_type": feature_types,
            "aoi_name": aoi_names,
            "strategy": strategies,
            "tile_id": tile_ids,
            "inside_fraction": inside_fracs,
            "inside_area_m2": inside_areas,
            "offset_x_frac": offset_x_list,
            "offset_y_frac": offset_y_list,
            "aoi_coverage_fraction": aoi_cov_fracs,
            "aoi_coverage_percent": aoi_cov_percents,
            "aoi_overlap_ratio": aoi_overlap_ratios,
            "aoi_overlap_percent": aoi_overlap_percents,
            "aoi_overlap_equiv_tiles": aoi_overlap_tiles,
            "aoi_num_tiles": aoi_num_tiles_list,
        },
        geometry=features,
        crs="EPSG:4326",
    )
    gdf.to_file(output_path, driver="GeoJSON")


def export_kml(aoi_geom_local, strategies: Dict[str, Dict[str, Any]],
               transformer_to_wgs84, output_path: Path):
    """
    Create a KML with:
      - AOI (once)
      - One Folder per strategy (balanced, full, minimal, max_coverage, compact)
    """
    def polygon_to_kml_coords(geom):
        # Only handle simple Polygons (no holes) for now
        if geom.geom_type != "Polygon":
            geom = geom.convex_hull
        coords = list(geom.exterior.coords)
        coord_strs = [f"{x:.8f},{y:.8f},0" for x, y in coords]
        return " ".join(coord_strs)

    aoi_wgs = transform_geom(aoi_geom_local, transformer_to_wgs84)

    kml_parts = []
    kml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    kml_parts.append('<kml xmlns="http://www.opengis.net/kml/2.2">')
    kml_parts.append("<Document>")
    kml_parts.append("<name>Imagery Tiling Solutions</name>")

    # AOI folder
    kml_parts.append("<Folder><name>AOI</name>")
    kml_parts.append("<Placemark><name>AOI</name>")
    kml_parts.append("<Style><LineStyle><color>ff00ffff</color></LineStyle>"
                     "<PolyStyle><color>4000ffff</color></PolyStyle></Style>")
    kml_parts.append("<Polygon><outerBoundaryIs><LinearRing><coordinates>")
    kml_parts.append(polygon_to_kml_coords(aoi_wgs))
    kml_parts.append("</coordinates></LinearRing></outerBoundaryIs></Polygon>")
    kml_parts.append("</Placemark></Folder>")

    # Strategy folders (fixed order if present)
    for strat_name in ["balanced", "full", "minimal", "max_coverage", "compact"]:
        if strat_name not in strategies:
            continue
        strat_data = strategies[strat_name]
        tiles = strat_data["tiles"]
        metrics = strat_data["metrics"]

        kml_parts.append(f"<Folder><name>{strat_name.capitalize()}</name>")
        kml_parts.append(
            f"<description>Tiles: {metrics['num_tiles']}, "
            f"Coverage: {metrics['coverage_fraction']*100:.2f}%, "
            f"Overlap: {metrics['overlap_percent']:.2f}% "
            f"(≈{metrics['overlap_equiv_tiles']:.2f} tiles)</description>"
        )

        for t in tiles:
            tile_wgs = transform_geom(t["poly"], transformer_to_wgs84)
            kml_parts.append(f"<Placemark><name>{strat_name}_T{t['tile_id']}</name>")
            kml_parts.append(
                "<Style><LineStyle><color>ff0000ff</color></LineStyle>"
                "<PolyStyle><color>400000ff</color></PolyStyle></Style>"
            )
            kml_parts.append("<Polygon><outerBoundaryIs><LinearRing><coordinates>")
            kml_parts.append(polygon_to_kml_coords(tile_wgs))
            kml_parts.append("</coordinates></LinearRing></outerBoundaryIs></Polygon>")
            kml_parts.append("</Placemark>")

        kml_parts.append("</Folder>")

    kml_parts.append("</Document></kml>")

    with output_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(kml_parts))


def export_strategy_summary(aoi_name: str, strategies: Dict[str, Dict[str, Any]],
                            out_dir: Path):
    """
    Write a CSV summarizing all strategies for this AOI.
    """
    path = out_dir / STRATEGY_SUMMARY_NAME
    fieldnames = [
        "aoi_name",
        "strategy",
        "num_tiles",
        "coverage_fraction",
        "coverage_percent",
        "overlap_ratio",
        "overlap_percent",
        "overlap_equiv_tiles",
        "offset_x_frac",
        "offset_y_frac",
        "aoi_area_km2",
        "coverage_area_km2",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for strat_name in ["balanced", "full", "minimal", "max_coverage", "compact"]:
            if strat_name not in strategies:
                continue
            m = strategies[strat_name]["metrics"]
            aoi_area_km2 = m["aoi_area"] / 1_000_000.0
            cov_area_km2 = m["coverage_area"] / 1_000_000.0
            writer.writerow(
                {
                    "aoi_name": aoi_name,
                    "strategy": strat_name,
                    "num_tiles": m["num_tiles"],
                    "coverage_fraction": m["coverage_fraction"],
                    "coverage_percent": m["coverage_fraction"] * 100.0,
                    "overlap_ratio": m["overlap_ratio"],
                    "overlap_percent": m["overlap_percent"],
                    "overlap_equiv_tiles": m["overlap_equiv_tiles"],
                    "offset_x_frac": m.get("offset_x_frac", None),
                    "offset_y_frac": m.get("offset_y_frac", None),
                    "aoi_area_km2": aoi_area_km2,
                    "coverage_area_km2": cov_area_km2,
                }
            )


# ------------------------------------------------------
# MAIN AOI PROCESSING (now returns a result dict)
# ------------------------------------------------------

def process_single_aoi(
    aoi: Dict[str, Any],
    base_out_dir: Path,
    tile_size_km: float,
    offset_fractions_x: List[float],
    offset_fractions_y: List[float],
    min_tile_inside_fraction: float,
    coverage_floor: float,
    minimal_coverage_floor: float,
    compact_min_inside_fraction: float,
    global_radius_km_default: float,
) -> Dict[str, Any]:
    """
    Run the tiling optimization for a single AOI dict, write outputs,
    and return a summary dictionary for this AOI.
    """
    name = aoi["name"]
    center_lat = aoi["center_lat"]
    center_lon = aoi["center_lon"]
    radius_km = aoi["radius_km"]
    aoi_type = aoi["type"]
    geom_wgs = aoi["geom_wgs"]

    print(f"\n=== Processing AOI: {name} (type={aoi_type}) ===")

    # Local CRS per AOI
    local_crs = get_local_crs(center_lat, center_lon)
    print(f"Local CRS selected for {name}: {local_crs.to_string()}")

    transformer_to_local = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True)
    transformer_to_wgs84 = Transformer.from_crs(local_crs, "EPSG:4326", always_xy=True)

    # Build AOI geometry in local CRS
    if aoi_type in ("circle", "point"):
        # Circle defined by center + radius
        r_km = radius_km if radius_km is not None else global_radius_km_default
        aoi_geom_local, (cx, cy), radius_m = build_circle_aoi_local(
            center_lat, center_lon, r_km, transformer_to_local
        )
        print(f"{name}: center (m)=({cx:.2f},{cy:.2f}), radius={radius_m:.2f} m")
    elif aoi_type == "polygon":
        # polygon AOI from geom_wgs
        if geom_wgs is None:
            raise ValueError(f"{name}: polygon AOI missing geometry.")
        aoi_geom_local = transform_geom(geom_wgs, transformer_to_local)
        cx, cy = aoi_geom_local.centroid.x, aoi_geom_local.centroid.y
        print(f"{name}: centroid (m)=({cx:.2f},{cy:.2f})")
    else:
        raise ValueError(f"Unknown AOI type: {aoi_type}")

    tile_size_m = tile_size_km * 1000.0
    candidates: List[Dict[str, Any]] = []

    # Generate / prune / score candidates
    for ox in offset_fractions_x:
        for oy in offset_fractions_y:
            raw_tiles = generate_tiles_with_offset(aoi_geom_local, tile_size_km, ox, oy)
            pruned_tiles = prune_tiles(
                aoi_geom_local,
                raw_tiles,
                tile_size_m,
                min_tile_inside_fraction,
                coverage_floor,
            )
            metrics = compute_solution_metrics(aoi_geom_local, pruned_tiles, tile_size_m)
            metrics["offset_x_frac"] = ox
            metrics["offset_y_frac"] = oy
            metrics["tiles"] = pruned_tiles
            candidates.append(metrics)

    # Sort by score
    candidates_sorted = sorted(candidates, key=lambda c: c["score"], reverse=True)

    print("\nCandidate Summary (Top 5 by score):")
    for c in candidates_sorted[:5]:
        print(
            f"  Offset ({c['offset_x_frac']:.2f}, {c['offset_y_frac']:.2f}) | "
            f"Tiles: {c['num_tiles']:3d} | "
            f"Coverage: {c['coverage_fraction']*100:6.2f}% | "
            f"Overlap: {c['overlap_percent']:6.2f}% "
            f"(≈{c['overlap_equiv_tiles']:.2f} tiles) | "
            f"Score: {c['score']:.4f}"
        )

    # ---- Base strategies ----

    # Balanced: best by score
    balanced = candidates_sorted[0]

    # Full: highest coverage, then fewest tiles
    full = max(
        candidates,
        key=lambda c: (c["coverage_fraction"], -c["num_tiles"])
    )

    # Minimal: fewest tiles with coverage >= minimal_coverage_floor
    minimal_pool = [
        c for c in candidates if c["coverage_fraction"] >= minimal_coverage_floor
    ]
    if minimal_pool:
        minimal = min(minimal_pool, key=lambda c: c["num_tiles"])
    else:
        minimal = full  # fallback

    strategies: Dict[str, Dict[str, Any]] = {
        "balanced": {"metrics": balanced, "tiles": balanced["tiles"]},
        "full": {"metrics": full, "tiles": full["tiles"]},
        "minimal": {"metrics": minimal, "tiles": minimal["tiles"]},
    }

    # ---- Extra strategies ----

    # 4) max_coverage: same offset as 'full', but NO greedy pruning
    full_ox = full["offset_x_frac"]
    full_oy = full["offset_y_frac"]
    raw_tiles_full = generate_tiles_with_offset(aoi_geom_local, tile_size_km, full_ox, full_oy)
    maxcov_tiles = [t for t in raw_tiles_full if t["inside_fraction"] >= min_tile_inside_fraction]
    maxcov_metrics = compute_solution_metrics(aoi_geom_local, maxcov_tiles, tile_size_m)
    maxcov_metrics["offset_x_frac"] = full_ox
    maxcov_metrics["offset_y_frac"] = full_oy
    strategies["max_coverage"] = {"metrics": maxcov_metrics, "tiles": maxcov_tiles}

    # 5) compact: based on 'balanced' tiles, keep only tiles with high inside_fraction
    compact_source_tiles = balanced["tiles"]
    compact_tiles = [
        t for t in compact_source_tiles if t.get("inside_fraction", 0.0) >= compact_min_inside_fraction
    ]
    compact_metrics = compute_solution_metrics(aoi_geom_local, compact_tiles, tile_size_m)
    compact_metrics["offset_x_frac"] = balanced["offset_x_frac"]
    compact_metrics["offset_y_frac"] = balanced["offset_y_frac"]
    strategies["compact"] = {"metrics": compact_metrics, "tiles": compact_tiles}

    print("\nSelected Strategies:")
    for strat_name in ["balanced", "full", "minimal", "max_coverage", "compact"]:
        if strat_name not in strategies:
            continue
        m = strategies[strat_name]["metrics"]
        print(
            f"  {strat_name.capitalize():12s}: Tiles={m['num_tiles']:3d}, "
            f"Coverage={m['coverage_fraction']*100:6.2f}%, "
            f"Overlap={m['overlap_percent']:6.2f}% "
            f"(≈{m['overlap_equiv_tiles']:.2f} tiles), "
            f"Offset=({m['offset_x_frac']:.2f},{m['offset_y_frac']:.2f})"
        )

    # Decide AOI output directory
    out_dir = base_out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Export per-strategy CSV + GeoJSON
    strategy_outputs: Dict[str, Dict[str, Any]] = {}

    for strat_name, data in strategies.items():
        tiles = data["tiles"]
        metrics = data["metrics"]
        ox = metrics.get("offset_x_frac", 0.0)
        oy = metrics.get("offset_y_frac", 0.0)

        csv_path = out_dir / csv_name(strat_name)
        geojson_path = out_dir / geojson_name(strat_name)

        export_centerpoints_csv(
            tiles, transformer_to_wgs84, csv_path,
            name, strat_name, metrics, ox, oy
        )
        export_tiles_geojson(
            aoi_geom_local, tiles, transformer_to_wgs84, geojson_path,
            name, strat_name, metrics, ox, oy
        )

        print(
            f"  {strat_name.capitalize():12s} CSV: {csv_path.resolve()}\n"
            f"  {strat_name.capitalize():12s} GeoJSON: {geojson_path.resolve()}"
        )

        strategy_outputs[strat_name] = {
            "metrics": metrics,
            "csv_path": str(csv_path.resolve()),
            "geojson_path": str(geojson_path.resolve()),
        }

    # Export combined KML for all strategies for this AOI
    kml_path = out_dir / KML_NAME
    export_kml(
        aoi_geom_local,
        strategies,
        transformer_to_wgs84,
        kml_path,
    )
    print(f"  KML: {kml_path.resolve()}")

    # Export strategy summary CSV
    strategy_summary_path = out_dir / STRATEGY_SUMMARY_NAME
    export_strategy_summary(name, strategies, out_dir)
    print(f"  Strategy summary: {strategy_summary_path.resolve()}")
    print(f"Finished AOI: {name}")

    # Return summary for this AOI (for GUI/CLI use)
    return {
        "aoi_name": name,
        "output_dir": str(out_dir.resolve()),
        "kml_path": str(kml_path.resolve()),
        "strategy_summary_path": str(strategy_summary_path.resolve()),
        "strategies": strategy_outputs,
    }


# ------------------------------------------------------
# PUBLIC API: run_tiling(...)
# ------------------------------------------------------

def run_tiling(
    use_circle_aoi: bool = USE_CIRCLE_AOI,
    center_lat: float = CENTER_LAT,
    center_lon: float = CENTER_LON,
    radius_km: float = RADIUS_KM,
    aoi_input: Optional[str] = None,
    aoi_layer: Optional[str] = AOI_LAYER,
    tile_size_km: float = TILE_SIZE_KM,
    out_dir: Optional[str] = None,
    min_tile_inside_fraction: float = MIN_TILE_INSIDE_FRACTION,
    coverage_floor: float = COVERAGE_FLOOR,
    minimal_coverage_floor: float = MINIMAL_COVERAGE_FLOOR,
    compact_min_inside_fraction: float = COMPACT_MIN_INSIDE_FRACTION,
    offset_fractions_x: Optional[List[float]] = None,
    offset_fractions_y: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Main tiling engine callable from GUI/CLI code.

    Returns:
        {
          "aois": [
             {
               "aoi_name": ...,
               "output_dir": ...,
               "kml_path": ...,
               "strategy_summary_path": ...,
               "strategies": {
                   "balanced": {
                       "metrics": {...},
                       "csv_path": "...",
                       "geojson_path": "..."
                   },
                   ...
               }
             },
             ...
          ]
        }
    """
    # Resolve defaults
    if out_dir is None:
        base_out_dir = OUT_DIR
    else:
        base_out_dir = Path(out_dir)

    if aoi_input is None and not use_circle_aoi:
        aoi_input_path = AOI_INPUT
    else:
        aoi_input_path = Path(aoi_input) if aoi_input is not None else None

    if offset_fractions_x is None:
        offset_fractions_x = OFFSET_FRACTIONS_X
    if offset_fractions_y is None:
        offset_fractions_y = OFFSET_FRACTIONS_Y

    base_out_dir.mkdir(parents=True, exist_ok=True)

    print(f"USE_CIRCLE_AOI = {use_circle_aoi}")
    print(f"TILE_SIZE_KM = {tile_size_km}")
    print(f"OUT_DIR = {base_out_dir}")
    print(f"MIN_TILE_INSIDE_FRACTION = {min_tile_inside_fraction}")
    print(f"COVERAGE_FLOOR = {coverage_floor}")
    print(f"MINIMAL_COVERAGE_FLOOR = {minimal_coverage_floor}")
    print(f"COMPACT_MIN_INSIDE_FRACTION = {compact_min_inside_fraction}")

    # Build AOIs
    aois = build_aois_with_config(
        use_circle_aoi=use_circle_aoi,
        center_lat=center_lat,
        center_lon=center_lon,
        radius_km=radius_km,
        aoi_input=aoi_input_path,
        aoi_layer=aoi_layer,
    )
    print(f"\nTotal AOIs to process: {len(aois)}")

    multi = len(aois) > 1
    all_aoi_results: List[Dict[str, Any]] = []

    for idx, aoi in enumerate(aois, start=1):
        if multi:
            aoi_dir = base_out_dir / f"{aoi['name']}"
        else:
            aoi_dir = base_out_dir

        aoi_result = process_single_aoi(
            aoi=aoi,
            base_out_dir=aoi_dir,
            tile_size_km=tile_size_km,
            offset_fractions_x=offset_fractions_x,
            offset_fractions_y=offset_fractions_y,
            min_tile_inside_fraction=min_tile_inside_fraction,
            coverage_floor=coverage_floor,
            minimal_coverage_floor=minimal_coverage_floor,
            compact_min_inside_fraction=compact_min_inside_fraction,
            global_radius_km_default=radius_km,
        )
        all_aoi_results.append(aoi_result)

    print("\nAll AOIs processed. Done ✔")

    return {"aois": all_aoi_results}


# ------------------------------------------------------
# CLI ENTRYPOINT (unchanged behavior)
# ------------------------------------------------------

def main():
    """
    CLI entrypoint – keeps your existing behavior, but now calls run_tiling()
    with the module-level defaults.
    """
    run_tiling()


if __name__ == "__main__":
    main()
