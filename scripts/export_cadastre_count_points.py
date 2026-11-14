"""Export one representative point per merged cadastral parcel as GeoJSON.

The point file is a compact input for boundary parcel counts. The source
GeoPackage remains the polygon archive for any later parcel mapping.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio


def export_points(source: Path, output: Path, batch_size: int = 50_000) -> dict:
    """Read parcel polygons in batches and write their interior points in WGS 84."""
    if not source.is_file():
        raise FileNotFoundError(source)
    if output.exists():
        raise FileExistsError(output)
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    info = pyogrio.read_info(source, layer="parcels")
    if info["features"] < 1 or info["geometry_type"] != "Polygon":
        raise ValueError("Expected a nonempty parcel-polygon layer")
    pieces = []
    for start in range(0, info["features"], batch_size):
        batch = pyogrio.read_dataframe(
            source, layer="parcels",
            columns=["parcel_id", "district_code", "district_name",
                     "source_geometry_valid"],
            skip_features=start, max_features=batch_size,
        )
        if batch.crs is None or batch.geometry.isna().any() or batch.geometry.is_empty.any():
            raise ValueError("Parcels need a CRS and nonempty geometry")
        if not batch.geometry.geom_type.eq("Polygon").all():
            raise ValueError("Expected one Polygon per parcel")
        # Representative points lie inside valid parcels. Preserve the source
        # validity flag so questionable polygons remain identifiable.
        batch["geometry"] = batch.geometry.representative_point()
        pieces.append(batch.to_crs(4326))
    points = gpd.GeoDataFrame(pd.concat(pieces, ignore_index=True),
                              geometry="geometry", crs="EPSG:4326")
    if len(points) != info["features"] or points.parcel_id.isna().any():
        raise AssertionError("Some parcel records were lost")
    if points.parcel_id.duplicated().any():
        raise AssertionError("Parcel IDs are duplicated")
    output.parent.mkdir(parents=True, exist_ok=True)
    pyogrio.write_dataframe(points, output, driver="GeoJSON")
    written = pyogrio.read_info(output)
    if written["features"] != len(points) or written["geometry_type"] != "Point":
        raise AssertionError("GeoJSON write failed count or geometry check")
    manifest = {
        "source": source.name,
        "output": output.name,
        "geometry": "one representative point per parcel polygon",
        "crs": "EPSG:4326",
        "parcel_count": len(points),
        "invalid_source_polygons_retained": int((~points.source_geometry_valid.astype(bool)).sum()),
        "district_counts": points.district_code.value_counts().sort_index().to_dict(),
        "output_bytes": output.stat().st_size,
    }
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Exported {len(points):,} parcel points to {output} ({output.stat().st_size:,} bytes)")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=Path("data/processed/cadastre2021_six_district_parcels.gpkg"))
    parser.add_argument("--output", type=Path,
                        default=Path("data/processed/cadastre2021_six_district_count_points.geojson"))
    arguments = parser.parse_args()
    export_points(arguments.source, arguments.output)
