# Dissertation risk-boundary project

## Purpose

This workspace supports a PhD dissertation design that examines households near officially classified urban-risk boundaries. The current Mexico City (CDMX) work is a feasibility and site-screening exercise: identify populated, geographically interpretable clusters of high-risk slope-instability polygons before fixing a household sampling design.

The wider comparative framing is a coherent family of rapid-onset geomorphological hazards:

- Bogotá: landslide / slope instability.
- Lima: huayco, debris-flow, or related geomorphological risk.
- CDMX: slope instability / landslide.

The current strategy is to retain the CDMX hazard family while allowing study geography to vary across alcaldías. Subsidence remains a possible fallback or supplemental analysis, not the present primary design.

## Current CDMX study frame

- Alcaldías: Álvaro Obregón (`aob`), Cuajimalpa (`cuj`), Gustavo A. Madero (`gam`), and Iztapalapa (`izp`).
- Risk layer: the national slope-instability / landslide risk layer, restricted to the highest selected risk category (`alta` by default).
- Household proxy: one representative point per cadastre parcel.
- Coordinate reference system for measurement: EPSG:32614, in metres.

## Notebooks

| Notebook | Role | Main outputs |
|---|---|---|
| `risk_polygon_household_counts_simple.ipynb` | Baseline counts for individual high-risk polygons. | Per-polygon GeoJSON, cadastre points, vulnerable-lot points, and an input manifest. |
| `risk_polygon_clustered_household_counts.ipynb` | Screens local clusters of nearby high-risk polygons as candidate boundary study areas. | One GeoJSON and one CSV with one row per cluster and clustering scenario. |
| `risk_zone_boundary_screening.ipynb` | Earlier boundary-screening work. | Inspect before relying on its outputs or assumptions. |
| `landslide_susceptibility_replication.ipynb` | Supporting landslide-susceptibility replication work. | See notebook cells for its specific outputs. |

## Cluster-screening method

The clustered notebook is intended to run a simple, transparent sensitivity analysis.

1. Select the high-risk slope-instability polygons in the study frame.
2. Form connected clusters using a selected distance definition:
   - `perimeter`: minimum edge-to-edge distance between polygons;
   - `centroid`: centroid-to-centroid distance.
3. Repeat for gap thresholds of 25 m, 50 m, 100 m, and 200 m.
4. Dissolve every cluster before creating zones. This prevents the same household-proxy point from being counted more than once within a cluster when constituent polygons or their boundary buffers overlap.
5. Count households in a 20 m outside boundary band and, by default, a 20 m inside boundary band. `all_inside` is available as an alternative inside-count rule.

Outside bands belonging to different clusters are intentionally not made mutually exclusive. A household in such an overlap may occur in both cluster rows; these rows represent competing local study-area candidates, not a citywide total.

## Important methodological status

The clustered notebook currently clips risk polygons **to each alcaldía individually** before clustering. That appropriately limits the analysis to the four-alcaldía study frame, but it can create artificial polygon edges at alcaldía borders.

The preferred pending revision is to dissolve the four alcaldía boundaries into one CDMX study-area geometry, clip risk polygons once to that combined extent, cluster across administrative borders, and then record every alcaldía touched by each cluster. Do not treat cross-alcaldía cluster results as final until this revision is made and checked.

## How to use the clustered output

Use the results as a go/no-go screening table, not as final causal evidence. Prioritize clusters with:

- enough household-proxy points on both sides of the boundary;
- reasonably balanced inside/outside counts;
- plausible physical comparability across the boundary;
- no obvious discontinuity dominated by cliffs, ravines, major roads, or other infrastructure; and
- a location suitable for fieldwork and qualitative investigation.

For each shortlisted cluster, inspect slope, elevation, drainage or ravines, roads, neighbourhood morphology, infrastructure, and the local meaning of the official risk classification. A useful target is several—roughly three to five—good CDMX boundary clusters rather than one unusually large polygon.

## Data and execution conventions

The current notebooks are written for Google Colab and expect:

```text
/content/drive/MyDrive/Dissertation/data_raw
/content/drive/MyDrive/Dissertation/data_output
```

Input-file matching is intentionally strict: the notebooks stop if they find zero or multiple plausible filenames. Review the filename tokens and district aliases whenever the raw data are reorganized.

## Dataset inventory

The notebooks do not bundle raw data. Keep the source files in `data_raw` and record source, version/date, licence, download URL, and any preprocessing in a separate data-provenance log before dissertation analysis.

| Dataset | Role in the current workflow | Key use and caution |
|---|---|---|
| National risk-zones layer (`inestabilidad`, `laderas`) | Hazard-classification source. | The notebook uses `INTENSIDAD`, normalized to `risk_category`, and selects `alta` by default. Confirm the official definition, date, scale, and intended use of this classification. |
| Alcaldía boundaries (`alcald...`) | Defines the four-alcaldía study frame and provides district names. | The `nomgeo` field is mapped to `aob`, `cuj`, `gam`, and `izp`. Boundary vintage must be compatible with the risk and cadastre datasets. |
| 2021 cadastre files (`catastro2021` + alcaldía token) | Household-proxy source. | Each parcel polygon becomes one representative point. Counts are therefore parcel counts, not verified household or population counts. |
| Vulnerable-lot layers (`lotes vulnerables`) | Used only in the simple baseline notebook when supplied. | Available for AOB, CUJ, and IZP in the current design; GAM has no supplied vulnerable-lot input and consequently receives `NA` for that measure. |

All spatial layers are reprojected to EPSG:32614 before distance, area, buffer, and cluster operations. Exported GeoJSON files are transformed to EPSG:4326 (WGS 84) for interoperable mapping.

## Output inventory and field guide

| Output | Produced by | Contents |
|---|---|---|
| `risk_polygon_household_counts.geojson` | Baseline notebook | One feature per selected high-risk polygon, with polygon context and cadastre/vulnerable-lot counts. |
| `catastro_points.geojson` | Baseline notebook | Representative household-proxy point for every included cadastre parcel. |
| `lotes_vulnerables_points.geojson` | Baseline notebook | Representative point for each included vulnerable lot. |
| `inputs_used_manifest.csv` | Baseline notebook | Input role-to-filename manifest for reproducibility. |
| `clustered_risk_household_counts_perimeter.geojson` or `clustered_risk_household_counts_centroid.geojson` | Clustered notebook | One dissolved risk cluster per gap scenario, including the cluster geometry and screening counts. |
| `clustered_risk_household_counts_perimeter.csv` or `clustered_risk_household_counts_centroid.csv` | Clustered notebook | Same cluster screening table without geometry, suitable for ranking and review. |

The clustered output contains these main fields:

| Field | Meaning |
|---|---|
| `cluster_id` | Reproducible label containing the distance method, gap scenario, and sequential cluster number. It is not a stable geographic identifier across parameter changes. |
| `cluster_gap_m` | Gap threshold used to connect polygons: 25, 50, 100, or 200 metres. |
| `cluster_distance_method` | `perimeter` for edge-to-edge distance or `centroid` for centroid-to-centroid distance. |
| `districts` | Comma-separated alcaldía codes represented in the cluster input. |
| `risk_polygon_count` | Number of source high-risk polygon pieces joined into the dissolved cluster. |
| `inside_mode`, `inside_band_m` | Whether the inside count uses the near-boundary strip or the entire cluster; the band is `NA` for `all_inside`. |
| `outside_band_m` | Width of the outward boundary band used for the outside count. |
| `cadastre_households_inside` | Cadastre representative-point count in the selected inside zone. This is a household proxy. |
| `cadastre_households_outside` | Cadastre representative-point count in the outward band. Separate cluster rows may count the same point where outside bands overlap. |
| `inside_outside_balance_ratio` | Inside count divided by outside count; `NA` where the outside count is zero. It is a screening indicator, not a causal estimate. |
| `cluster_area_m2` | Area of the dissolved cluster in square metres. |

## Decision log

| Decision | Current position |
|---|---|
| CDMX primary hazard | Slope instability / landslide. |
| Geographic scope | Flexible within CDMX; currently four alcaldías. |
| Polygon gap sensitivity | 25 m, 50 m, 100 m, 200 m. |
| Cluster distance metric | Parameterized: perimeter or centroid. |
| Outside household band | 20 m default parameter. |
| Inside household rule | 20 m boundary strip by default; `all_inside` available. |
| Household duplication within cluster | Prevented through dissolved cluster geometries. |
| Household duplication across clusters | Allowed deliberately. |
| Sampling design | Still under evaluation; do not freeze it before site-level physical checks. |

## Next steps

1. Revise the clustered notebook to avoid artificial splitting at alcaldía borders.
2. Run all four gap scenarios under both distance definitions.
3. Map and inspect promising clusters.
4. Select the best 3–5 physically interpretable boundary clusters.
5. Decide whether the CDMX slope-instability design is viable before considering subsidence as a fallback.
