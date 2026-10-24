"""
Reference data ingestion & geo prep.
Generates simplified GeoJSON files (< 500 KB each) for:
- 100 NC Counties
- 14 NC Congressional Districts (CD)
- 50 NC State Senate Districts (SD)
- 120 NC State House Districts (HD)
"""

import json
import logging
import math
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

GEO_DIR = Path(__file__).resolve().parents[3] / "data" / "geo"


def fetch_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def _p_dist(p1, p2, p):
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]
    x0, y0 = p[0], p[1]
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x0 - x1, y0 - y1)
    return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / math.hypot(dx, dy)


def rdp(points, epsilon: float = 0.003):
    """Ramer-Douglas-Peucker line simplification."""
    if len(points) < 3:
        return points
    dmax = 0.0
    index = 0
    for i in range(1, len(points) - 1):
        d = _p_dist(points[0], points[-1], points[i])
        if d > dmax:
            index = i
            dmax = d
    if dmax > epsilon:
        r1 = rdp(points[: index + 1], epsilon)
        r2 = rdp(points[index:], epsilon)
        return r1[:-1] + r2
    return [points[0], points[-1]]


def simplify_geom(geom, eps: float = 0.003):
    gtype = geom["type"]
    coords = geom["coordinates"]
    if gtype == "Polygon":
        new_coords = [rdp(ring, eps) for ring in coords if len(ring) >= 3]
        return {"type": "Polygon", "coordinates": new_coords}
    elif gtype == "MultiPolygon":
        new_coords = [[rdp(ring, eps) for ring in poly if len(ring) >= 3] for poly in coords]
        return {"type": "MultiPolygon", "coordinates": new_coords}
    return geom


def build_county_geojson(force: bool = False) -> Path:
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    out_file = GEO_DIR / "county.geojson"
    if out_file.exists() and not force:
        return out_file

    url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
    data = fetch_json(url)

    nc_features = []
    for f in data.get("features", []):
        fips = str(f.get("id") or f.get("properties", {}).get("GEO_ID", "")[-5:]).zfill(5)
        if fips.startswith("37"):
            name = f.get("properties", {}).get("NAME", fips)
            feat = {
                "type": "Feature",
                "id": fips,
                "properties": {
                    "unit_id": fips,
                    "county_fips": fips,
                    "name": name,
                    "unit_type": "county"
                },
                "geometry": simplify_geom(f["geometry"], eps=0.002)
            }
            nc_features.append(feat)

    collection = {"type": "FeatureCollection", "features": nc_features}
    out_file.write_text(json.dumps(collection))
    logger.info(f"Saved {len(nc_features)} counties to {out_file} ({out_file.stat().st_size / 1024:.1f} KB)")
    return out_file


def build_cd_geojson(force: bool = False) -> Path:
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    out_file = GEO_DIR / "cd.geojson"
    if out_file.exists() and not force:
        return out_file

    url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/0/query?where=STATE%3D%2737%27&outFields=*&f=geojson"
    data = fetch_json(url)
    features = []
    for f in data.get("features", []):
        props = f.get("properties", {})
        cd_num = str(props.get("BASENAME") or props.get("CD120") or props.get("CD119") or props.get("GEOID", "")[-2:]).lstrip("0") or "1"
        unit_id = f"CD{cd_num}"
        feat = {
            "type": "Feature",
            "id": unit_id,
            "properties": {
                "unit_id": unit_id,
                "name": f"Congressional District {cd_num}",
                "district_num": int(cd_num) if cd_num.isdigit() else cd_num,
                "unit_type": "cd"
            },
            "geometry": simplify_geom(f["geometry"], eps=0.003)
        }
        features.append(feat)

    features.sort(key=lambda x: int(x["properties"]["district_num"]) if str(x["properties"]["district_num"]).isdigit() else 999)
    collection = {"type": "FeatureCollection", "features": features}
    out_file.write_text(json.dumps(collection))
    logger.info(f"Saved {len(features)} CDs to {out_file} ({out_file.stat().st_size / 1024:.1f} KB)")
    return out_file


def build_sd_geojson(force: bool = False) -> Path:
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    out_file = GEO_DIR / "sd.geojson"
    if out_file.exists() and not force:
        return out_file

    url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/1/query?where=STATE%3D%2737%27&outFields=*&f=geojson"
    data = fetch_json(url)
    features = []
    for f in data.get("features", []):
        props = f.get("properties", {})
        sd_num = str(props.get("BASENAME") or props.get("SLDU") or props.get("NAME", "")).replace("State Senate District ", "").lstrip("0") or "1"
        unit_id = f"SD{sd_num}"
        feat = {
            "type": "Feature",
            "id": unit_id,
            "properties": {
                "unit_id": unit_id,
                "name": f"State Senate District {sd_num}",
                "district_num": int(sd_num) if sd_num.isdigit() else sd_num,
                "unit_type": "sd"
            },
            "geometry": simplify_geom(f["geometry"], eps=0.003)
        }
        features.append(feat)

    features.sort(key=lambda x: int(x["properties"]["district_num"]) if str(x["properties"]["district_num"]).isdigit() else 999)
    collection = {"type": "FeatureCollection", "features": features}
    out_file.write_text(json.dumps(collection))
    logger.info(f"Saved {len(features)} SDs to {out_file} ({out_file.stat().st_size / 1024:.1f} KB)")
    return out_file


def build_hd_geojson(force: bool = False) -> Path:
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    out_file = GEO_DIR / "hd.geojson"
    if out_file.exists() and not force:
        return out_file

    url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/2/query?where=STATE%3D%2737%27&outFields=*&f=geojson"
    data = fetch_json(url)
    features = []
    for f in data.get("features", []):
        props = f.get("properties", {})
        hd_num = str(props.get("BASENAME") or props.get("SLDL") or props.get("NAME", "")).replace("State House District ", "").lstrip("0") or "1"
        unit_id = f"HD{hd_num}"
        feat = {
            "type": "Feature",
            "id": unit_id,
            "properties": {
                "unit_id": unit_id,
                "name": f"State House District {hd_num}",
                "district_num": int(hd_num) if hd_num.isdigit() else hd_num,
                "unit_type": "hd"
            },
            "geometry": simplify_geom(f["geometry"], eps=0.003)
        }
        features.append(feat)

    features.sort(key=lambda x: int(x["properties"]["district_num"]) if str(x["properties"]["district_num"]).isdigit() else 999)
    collection = {"type": "FeatureCollection", "features": features}
    out_file.write_text(json.dumps(collection))
    logger.info(f"Saved {len(features)} HDs to {out_file} ({out_file.stat().st_size / 1024:.1f} KB)")
    return out_file


def run_all(force: bool = True):
    logging.basicConfig(level=logging.INFO)
    logger.info("Building simplified county GeoJSON...")
    build_county_geojson(force=force)
    logger.info("Building simplified CD GeoJSON...")
    build_cd_geojson(force=force)
    logger.info("Building simplified SD GeoJSON...")
    build_sd_geojson(force=force)
    logger.info("Building simplified HD GeoJSON...")
    build_hd_geojson(force=force)
    logger.info("Simplified GeoJSON generation completed successfully.")


if __name__ == "__main__":
    run_all(force=True)
