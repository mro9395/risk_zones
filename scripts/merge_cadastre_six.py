"""Merge the six official SIGCDMX catastro2021 parcel polygon ZIPs.

The merged GeoPackage preserves source geometries, including invalid ones,
and marks their validity. It does not infer households or generate points.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pyogrio


DISTRICTS = {
    "ALVARO_OBREGON": ("aob", "Álvaro Obregón"),
    "CUAJIMALPA": ("cuj", "Cuajimalpa de Morelos"),
    "GUSTAVO_A_MADERO": ("gam", "Gustavo A. Madero"),
    "IZTAPALAPA": ("izp", "Iztapalapa"),
    "MAGDALENA_CONTRERAS": ("mct", "La Magdalena Contreras"),
    "XOCHIMILCO": ("xoc", "Xochimilco"),
}
EXPECTED_CRS = "EPSG:32614"


def sha256(path: Path) -> str:
    """Hash a source archive without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def merge(source_dir: Path, output: Path) -> dict:
    """Append one district at a time and verify the resulting parcel layer."""
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    building = output.with_name(output.stem + ".building.gpkg")
    if building.exists():
        raise FileExistsError(f"Incomplete earlier build exists: {building}")

    audit = []
    for index, (token, (code, district)) in enumerate(DISTRICTS.items()):
        archive = source_dir / f"catastro2021_{token}.zip"
        if not archive.is_file():
            raise FileNotFoundError(archive)
        info = pyogrio.read_info(str(archive))
        if info["crs"] != EXPECTED_CRS or info["geometry_type"] != "Polygon":
            raise ValueError(f"Unexpected CRS or geometry type in {archive.name}: {info}")
        if list(info["fields"]) != ["fid"]:
            raise ValueError(f"Unexpected fields in {archive.name}: {info['fields']}")
        parcels = pyogrio.read_dataframe(str(archive))
        if len(parcels) != info["features"]:
            raise AssertionError(f"Feature count changed while reading {archive.name}")
        if parcels.fid.isna().any() or parcels.fid.duplicated().any():
            raise ValueError(f"Missing or repeated source fid in {archive.name}")
        if parcels.geometry.isna().any() or parcels.geometry.is_empty.any():
            raise ValueError(f"Null or empty geometry in {archive.name}")
        if not parcels.geometry.geom_type.eq("Polygon").all():
            raise ValueError(f"Non-polygon geometry in {archive.name}")

        valid = parcels.geometry.is_valid
        parcels = parcels.rename(columns={"fid": "source_fid"})
        parcels["parcel_id"] = code + ":" + parcels.source_fid.astype(str)
        parcels["district_code"] = code
        parcels["district_name"] = district
        parcels["source_zip"] = archive.name
        parcels["source_geometry_valid"] = valid.astype(bool)
        parcels = parcels[["parcel_id", "source_fid", "district_code",
                           "district_name", "source_zip", "source_geometry_valid",
                           "geometry"]]
        pyogrio.write_dataframe(parcels, str(building), layer="parcels",
                                driver="GPKG", append=index > 0)
        audit.append({"district_code": code, "district_name": district,
                      "source_zip": archive.name, "source_bytes": archive.stat().st_size,
                      "source_sha256": sha256(archive), "source_crs": info["crs"],
                      "parcel_count": len(parcels),
                      "invalid_geometry_count": int((~valid).sum())})
        print(f"{district}: {len(parcels):,} parcels; {(~valid).sum():,} invalid geometries", flush=True)

    merged = pyogrio.read_info(str(building), layer="parcels")
    expected = sum(row["parcel_count"] for row in audit)
    if merged["features"] != expected or merged["crs"] != EXPECTED_CRS:
        raise AssertionError(f"Merged layer failed count/CRS check: {merged}")
    os.replace(building, output)
    manifest = {"source": "https://sig.cdmx.gob.mx/datos/descarga",
                "downloaded_and_merged_utc": datetime.now(timezone.utc).isoformat(),
                "output": output.name, "layer": "parcels",
                "total_parcels": expected,
                "total_invalid_geometries": sum(row["invalid_geometry_count"] for row in audit),
                "districts": audit}
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Merged {expected:,} parcels into {output}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path("data/raw/cadastre2021"))
    parser.add_argument("--output", type=Path,
                        default=Path("data/processed/cadastre2021_six_district_parcels.gpkg"))
    arguments = parser.parse_args()
    merge(arguments.source_dir, arguments.output)
