"""Core conversion: Excel/CSV → GeoJSON FeatureCollection."""
import json
import os
from datetime import datetime
from typing import Callable

import pandas as pd

from .mgrs_utils import mgrs_to_latlon


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip().lower().replace(" ", "").replace("_", "") for c in df.columns]
    return df


def _find_column(df: pd.DataFrame, *aliases: str):
    lookup = {c.lower() for c in df.columns}
    for alias in aliases:
        if alias.lower() in lookup:
            # Return actual column name (already lowercased after normalize)
            return alias.lower()
    return None


def _is_valid_geojson_point(value) -> bool:
    try:
        obj = json.loads(value) if isinstance(value, str) else value
        if not isinstance(obj, dict):
            return False
        coords = obj.get("coordinates")
        return (
            obj.get("type") == "Point"
            and isinstance(coords, list)
            and len(coords) == 2
            and all(isinstance(c, (int, float)) for c in coords)
        )
    except Exception:
        return False


def convert_to_geojson(input_path: str, output_dir: str, logger: Callable = print) -> str:
    """
    Convert a CSV or Excel file to a GeoJSON FeatureCollection.

    Returns the path to the written .geojson file.
    Raises on unrecoverable errors.
    """
    # ── Load ─────────────────────────────────────────────────────────────────
    ext = input_path.lower()
    if ext.endswith((".xls", ".xlsx")):
        df = pd.read_excel(input_path, engine="openpyxl", sheet_name=0)
    elif ext.endswith(".csv"):
        df = pd.read_csv(input_path)
    else:
        raise ValueError(f"Unsupported file type: '{input_path}'")

    if df.empty:
        raise ValueError("Input file is empty.")

    df = _normalize_columns(df)

    # ── Locate coordinate columns ────────────────────────────────────────────
    lat_col  = _find_column(df, "lat", "latitude")
    lon_col  = _find_column(df, "lon", "longitude")
    mgrs_col = _find_column(df, "mgrs")

    latlon_valid = (
        lat_col and lon_col
        and df[lat_col].notnull().any()
        and df[lon_col].notnull().any()
    )

    # ── MGRS fallback ────────────────────────────────────────────────────────
    if not latlon_valid:
        if not mgrs_col or df[mgrs_col].isnull().all():
            raise ValueError("No lat/lon columns and no MGRS column found. Cannot convert.")

        logger("No valid lat/lon found — converting from MGRS...")
        lats, lons = [], []
        for idx, val in df[mgrs_col].items():
            try:
                if pd.isna(val):
                    raise ValueError("blank MGRS value")
                lat, lon = mgrs_to_latlon(str(val))
                lats.append(lat)
                lons.append(lon)
                logger(f"  Row {idx + 2}: MGRS → ({lat:.6f}, {lon:.6f})")
            except Exception as exc:
                lats.append(None)
                lons.append(None)
                logger(f"  Row {idx + 2}: MGRS conversion failed — {exc}")

        df["latitude"]  = lats
        df["longitude"] = lons
        lat_col, lon_col = "latitude", "longitude"
    else:
        logger(f"Using coordinate columns: '{lat_col}', '{lon_col}'")

    # ── Drop rows without valid geometry ─────────────────────────────────────
    df = df[df[lat_col].notnull() & df[lon_col].notnull()].copy()
    if df.empty:
        raise ValueError("No rows with valid coordinates remain after filtering.")

    # ── Derive regionText (WKT) ───────────────────────────────────────────────
    if "regiontext" not in df.columns or df["regiontext"].isnull().all():
        df["regiontext"] = df.apply(
            lambda r: f"POINT({r[lon_col]} {r[lat_col]})", axis=1
        )

    # ── Derive regionGeoJSON ──────────────────────────────────────────────────
    def _make_point_geojson(row):
        existing = row.get("regiongeojson")
        if _is_valid_geojson_point(existing):
            return existing
        return json.dumps({"type": "Point", "coordinates": [row[lon_col], row[lat_col]]})

    df["regiongeojson"] = df.apply(_make_point_geojson, axis=1)

    # ── Build GeoJSON features ────────────────────────────────────────────────
    features = []
    for idx, row in df.iterrows():
        try:
            geom = json.loads(row["regiongeojson"])
            props = {}
            for k in df.columns:
                if k == "regiongeojson":
                    continue
                v = row[k]
                if pd.isna(v) if not isinstance(v, (dict, list)) else False:
                    continue
                props[k] = v.isoformat() if isinstance(v, (datetime, pd.Timestamp)) else v
            features.append({"type": "Feature", "geometry": geom, "properties": props})
        except Exception as exc:
            logger(f"  Row {idx + 2}: skipped — {exc}")

    if not features:
        raise ValueError("No valid features produced. File may be corrupt or all rows invalid.")

    # ── Write output ──────────────────────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, stem + ".geojson")

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh, indent=2)

    logger(f"GeoJSON saved — {len(features)} features → {output_path}")
    return output_path
