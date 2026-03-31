"""
Pure-Python exporters: GeoJSON → KML and GeoJSON → Shapefile (zipped).
No GDAL / ogr2ogr dependency — fully self-contained for .exe distribution.
"""

from __future__ import annotations

import json
import math
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import shapefile  # pyshp


# ═══════════════════════════════════════════════════════════════
#  KML export
# ═══════════════════════════════════════════════════════════════

def _geom_to_kml(geom: Dict[str, Any]) -> Optional[ET.Element]:
    gtype = geom.get("type")
    coords = geom.get("coordinates")

    if gtype == "Point":
        el = ET.Element("Point")
        ET.SubElement(el, "coordinates").text = f"{coords[0]},{coords[1]},0"
        return el

    if gtype == "MultiPoint":
        multi = ET.Element("MultiGeometry")
        for pt in coords:
            p = ET.SubElement(multi, "Point")
            ET.SubElement(p, "coordinates").text = f"{pt[0]},{pt[1]},0"
        return multi

    if gtype == "LineString":
        el = ET.Element("LineString")
        ET.SubElement(el, "coordinates").text = " ".join(f"{x},{y},0" for x, y in coords)
        return el

    if gtype == "MultiLineString":
        multi = ET.Element("MultiGeometry")
        for line in coords:
            ls = ET.SubElement(multi, "LineString")
            ET.SubElement(ls, "coordinates").text = " ".join(f"{x},{y},0" for x, y in line)
        return multi

    if gtype == "Polygon":
        el = ET.Element("Polygon")
        outer = ET.SubElement(ET.SubElement(el, "outerBoundaryIs"), "LinearRing")
        ET.SubElement(outer, "coordinates").text = " ".join(f"{x},{y},0" for x, y in coords[0])
        for hole in coords[1:]:
            inner = ET.SubElement(ET.SubElement(el, "innerBoundaryIs"), "LinearRing")
            ET.SubElement(inner, "coordinates").text = " ".join(f"{x},{y},0" for x, y in hole)
        return el

    if gtype == "MultiPolygon":
        multi = ET.Element("MultiGeometry")
        for poly in coords:
            p = ET.SubElement(multi, "Polygon")
            outer = ET.SubElement(ET.SubElement(p, "outerBoundaryIs"), "LinearRing")
            ET.SubElement(outer, "coordinates").text = " ".join(
                f"{x},{y},0" for x, y in poly[0]
            )
            for hole in poly[1:]:
                inner = ET.SubElement(ET.SubElement(p, "innerBoundaryIs"), "LinearRing")
                ET.SubElement(inner, "coordinates").text = " ".join(
                    f"{x},{y},0" for x, y in hole
                )
        return multi

    return None


def export_kml(geojson_path: str, output_dir: str, logger: Callable = print) -> str:
    """Convert a GeoJSON file to KML. Returns path to the written .kml file."""
    src = Path(geojson_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    kml_path = out / (src.stem + ".kml")

    with src.open("r", encoding="utf-8") as fh:
        gj = json.load(fh)

    features = gj.get("features", [])

    # Build XML tree
    kml_ns = "http://www.opengis.net/kml/2.2"
    ET.register_namespace("", kml_ns)
    kml_root = ET.Element(f"{{{kml_ns}}}kml")
    doc = ET.SubElement(kml_root, f"{{{kml_ns}}}Document")
    ET.SubElement(doc, f"{{{kml_ns}}}name").text = src.stem

    for feat in features:
        props = feat.get("properties") or {}
        geom  = feat.get("geometry")
        if not geom:
            continue

        pm = ET.SubElement(doc, f"{{{kml_ns}}}Placemark")

        # Name: prefer featureId / name / id, else unnamed
        name_val = (
            props.get("featureid")
            or props.get("featureId")
            or props.get("name")
            or props.get("id")
            or ""
        )
        ET.SubElement(pm, f"{{{kml_ns}}}name").text = str(name_val)

        # ExtendedData for all properties
        if props:
            ext = ET.SubElement(pm, f"{{{kml_ns}}}ExtendedData")
            for k, v in props.items():
                data = ET.SubElement(ext, f"{{{kml_ns}}}Data", name=str(k))
                ET.SubElement(data, f"{{{kml_ns}}}value").text = (
                    str(v) if not isinstance(v, (dict, list)) else json.dumps(v)
                )

        geom_el = _geom_to_kml(geom)
        if geom_el is not None:
            # Strip namespace from geometry elements (KML spec allows unqualified)
            pm.append(geom_el)

    # Indent for readability (Python 3.9+)
    try:
        ET.indent(kml_root, space="  ")
    except AttributeError:
        pass

    tree = ET.ElementTree(kml_root)
    tree.write(str(kml_path), encoding="unicode", xml_declaration=True)

    logger(f"KML saved → {kml_path}")
    return str(kml_path)


# ═══════════════════════════════════════════════════════════════
#  Shapefile export (pure Python via pyshp)
# ═══════════════════════════════════════════════════════════════

def _safe_field_name(name: str, used: set) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "_", name.strip()) or "field"
    base = base[:10]
    candidate = base
    i = 1
    while candidate.upper() in used:
        suffix = str(i)
        candidate = (base[: max(0, 10 - len(suffix))] + suffix)[:10]
        i += 1
    used.add(candidate.upper())
    return candidate


def _infer_field_spec(values: List[Any]) -> Tuple[str, int, int]:
    vals = [v for v in values if v is not None]
    if not vals:
        return ("C", 254, 0)

    if all(isinstance(v, bool) for v in vals):
        return ("L", 1, 0)

    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
        max_dec, max_int = 0, 1
        for v in vals:
            if isinstance(v, float) and not math.isfinite(v):
                continue
            s = f"{v}"
            if "e" in s or "E" in s:
                return ("C", 254, 0)
            if "." in s:
                int_p, dec_p = s.split(".", 1)
                max_dec = max(max_dec, len(dec_p.rstrip("0")))
                max_int = max(max_int, len(int_p.replace("-", "")))
            else:
                max_int = max(max_int, len(s.replace("-", "")))
        neg = any(isinstance(v, (int, float)) and v < 0 for v in vals)
        size = min(18, max_int + (1 if neg else 0) + (1 if max_dec > 0 else 0) + max_dec)
        return ("N", max(size, 3), min(8, max_dec))

    def _is_date(x) -> bool:
        if not isinstance(x, str):
            return False
        try:
            datetime.strptime(x[:10], "%Y-%m-%d")
            return True
        except Exception:
            return False

    if all(_is_date(v) for v in vals):
        return ("D", 8, 0)

    return ("C", 254, 0)


def _coerce_for_dbf(v: Any, ftype: str, size: int, dec: int) -> Any:
    if v is None:
        return None
    if ftype == "L":
        return bool(v)
    if ftype == "N":
        try:
            if isinstance(v, bool):
                return int(v)
            if isinstance(v, (int, float)):
                return None if (isinstance(v, float) and not math.isfinite(v)) else v
            if isinstance(v, str):
                return float(v) if "." in v else int(v)
        except Exception:
            return None
    if ftype == "D":
        if isinstance(v, str):
            try:
                return datetime.strptime(v[:10], "%Y-%m-%d").strftime("%Y%m%d")
            except Exception:
                return None
    # C
    s = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
    return s[:size]


def _choose_shp_type(geoms: List[Optional[Dict]]) -> int:
    for g in geoms:
        if not g:
            continue
        t = g.get("type")
        if t == "Point":            return shapefile.POINT
        if t == "MultiPoint":       return shapefile.MULTIPOINT
        if t in ("LineString", "MultiLineString"):  return shapefile.POLYLINE
        if t in ("Polygon", "MultiPolygon"):        return shapefile.POLYGON
    return shapefile.NULL


def _write_geom(w: shapefile.Writer, geom: Dict[str, Any]) -> None:
    gtype = geom["type"]
    coords = geom["coordinates"]

    if gtype == "Point":
        w.point(float(coords[0]), float(coords[1]))
    elif gtype == "MultiPoint":
        w.multipoint([[float(x), float(y)] for x, y in coords])
    elif gtype == "LineString":
        w.line([[[float(x), float(y)] for x, y in coords]])
    elif gtype == "MultiLineString":
        w.line([[[float(x), float(y)] for x, y in line] for line in coords])
    elif gtype == "Polygon":
        w.poly([[[float(x), float(y)] for x, y in ring] for ring in coords])
    elif gtype == "MultiPolygon":
        parts = []
        for poly in coords:
            parts.extend([[float(x), float(y)] for x, y in ring] for ring in poly)
        w.poly(parts)
    else:
        raise ValueError(f"Unsupported geometry type: {gtype}")


def export_shp(geojson_path: str, output_dir: str, logger: Callable = print) -> str:
    """Convert a GeoJSON file to a zipped Shapefile. Returns path to the .zip."""
    src = Path(geojson_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    with src.open("r", encoding="utf-8") as fh:
        gj = json.load(fh)

    features = gj.get("features", [])
    if not features:
        raise ValueError("GeoJSON has no features to export.")

    props_list = [f.get("properties") or {} for f in features]
    geoms_list = [f.get("geometry") for f in features]

    # Field schema
    all_keys = sorted({k for p in props_list for k in p})
    used_names: set = set()
    field_map = {k: _safe_field_name(k, used_names) for k in all_keys}
    field_specs = {k: _infer_field_spec([p.get(k) for p in props_list]) for k in all_keys}

    shp_type = _choose_shp_type(geoms_list)

    work_dir = out / f"{src.stem}_shp_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    shp_base = str(work_dir / src.stem)

    w = shapefile.Writer(shp_base, shapeType=shp_type)
    w.autoBalance = 1

    for orig_key in all_keys:
        shp_key = field_map[orig_key]
        ftype, size, dec = field_specs[orig_key]
        try:
            if ftype == "N":
                w.field(shp_key, ftype, size=size, decimal=dec)
            elif ftype == "L":
                w.field(shp_key, ftype, size=1)
            elif ftype == "D":
                w.field(shp_key, ftype, size=8)
            else:
                w.field(shp_key, "C", size=size)
        except Exception:
            w.field(shp_key, "C", size=254)
            field_specs[orig_key] = ("C", 254, 0)

    failures = 0
    for idx, (props, geom) in enumerate(zip(props_list, geoms_list), start=1):
        try:
            if geom is None:
                w.null()
            else:
                _write_geom(w, geom)
            rec = [
                _coerce_for_dbf(props.get(k), *field_specs[k])
                for k in all_keys
            ]
            w.record(*rec)
        except Exception as exc:
            failures += 1
            logger(f"  Feature {idx}: skipped in SHP — {exc}")
            try:
                w.null()
                w.record(*([None] * len(all_keys)))
            except Exception:
                pass

    w.close()

    # WGS84 projection + encoding files
    prj = work_dir / f"{src.stem}.prj"
    cpg = work_dir / f"{src.stem}.cpg"
    prj.write_text(
        'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]',
        encoding="utf-8",
    )
    cpg.write_text("UTF-8", encoding="utf-8")

    zip_path = out / f"{src.stem}_shp.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in work_dir.iterdir():
            if p.is_file():
                zf.write(p, arcname=p.name)

    if failures:
        logger(f"Shapefile saved ({failures} features skipped) → {zip_path}")
    else:
        logger(f"Shapefile saved → {zip_path}")
    return str(zip_path)
