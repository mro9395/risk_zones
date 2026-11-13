# Dissertation risk-boundary project

## Purpose

This workspace supports a PhD dissertation design that examines households near officially classified urban-risk boundaries. The current Mexico City (CDMX) work is a feasibility and site-screening exercise: identify populated, geographically interpretable clusters of high-risk slope-instability polygons before fixing a household sampling design. A new citywide population-screening notebook complements the earlier four-alcaldía cadastre work.

The wider comparative framing is a coherent family of rapid-onset geomorphological hazards:

- Bogotá: landslide / slope instability.
- Lima: huayco, debris-flow, or related geomorphological risk.
- CDMX: slope instability / landslide.

The current strategy is to retain the CDMX hazard family while allowing study geography to vary across alcaldías. Subsidence remains a possible fallback or supplemental analysis, not the present primary design. The current citywide rules are recorded in [SAMPLING_PROTOCOL.md](SAMPLING_PROTOCOL.md).

## Earlier four-alcaldía cadastre study frame

- Alcaldías: Álvaro Obregón (`aob`), Cuajimalpa (`cuj`), Gustavo A. Madero (`gam`), and Iztapalapa (`izp`).
- Risk layer: the national slope-instability / landslide risk layer, restricted to the highest selected risk category (`alta` by default).
- Household proxy: one representative point per cadastre parcel.
- Coordinate reference system for measurement: EPSG:32614, in metres.

The citywide population-and-cluster notebook uses a different, all-CDMX frame with no current alcaldía exclusions. Its sources, screens, 100 m draw gap, and manual exclusion status are documented in [SAMPLING_PROTOCOL.md](SAMPLING_PROTOCOL.md).

## Notebooks

| Notebook | Role | Main outputs |
|---|---|---|
| `risk_polygon_household_counts_simple.ipynb` | Baseline counts for individual high-risk polygons. | Per-polygon GeoJSON, cadastre points, vulnerable-lot points, and an input manifest. |
| `risk_polygon_clustered_household_counts.ipynb` | Screens local clusters of nearby high-risk polygons as candidate boundary study areas. | One GeoJSON and one CSV with one row per cluster and clustering scenario. |
| `risk_polygon_boundary_household_sample.ipynb` | Randomly samples cadastre parcels near individual risk-polygon boundaries using representative points. | Eligible-parcel and selected-parcel polygon GeoJSONs, sample CSV, and candidate-count audit CSV. |
| `risk_polygon_population_cluster_sample.ipynb` | Screens all-CDMX high-risk polygons with a WorldPop population raster, clusters populated polygons, and orders candidate clusters across four broad geographic groups. | Polygon and cluster screening tables and GeoJSONs, selected site polygons, membership CSV, manifest, and cluster maps. |
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
/content/drive/MyDrive/Dissertation/data/raw
/content/drive/MyDrive/Dissertation/data/output
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
| `susceptibilidad_laderas_all.geojson` | High-risk slope-instability polygon source for the new citywide workflow. | Supplied as already restricted to high-risk polygons across all CDMX, with `NOM_MUN` district names. The new notebook excludes listed districts by this field before analysis and does not clip to four alcaldías. Preserve the source file and its feature order if generated polygon IDs are used. |
| `mex_pop_2026_CN_100m_R2025A_v1.tif` | 2026 WorldPop constrained population-count raster for Mexico. | Values represent estimated people per 100 m cell, not density. The new notebook sums values weighted by the fraction of each cell inside a polygon; a positive result is a screening signal rather than a verified resident count. [WorldPop product metadata](https://stac.worldpop.org/collections/MEX/items/mex_pop_2026_CN_100m_R2025A_v1). |
| `IMUC_2020_CDMX.geojson` | Colonia-level 2020 socioeconomic classification for the citywide notebook. | `GM_2020` categories are concatenated when a boundary spans colonias with different values. `IM_2020` is the arithmetic mean across nonmissing numeric values from overlapping colonias, counting each colonia once. `GM_2020` is used to exclude boundaries whose known overlapping colonia categories are all `Bajo` or `Muy bajo`; `IM_2020` values above 150 are excluded by default; missing values are kept. The bounds remain editable. |
| `asentamientos_humanos_irregulares_(2022).geojson` | Irregular-settlement record locations in the citywide notebook. | The inspected file has five Point features, all in Álvaro Obregón, in EPSG:6369. These are settlement records, not cadastre parcels or households. The notebook counts distinct points inside each boundary and dissolved cluster; its default minimum of zero does not exclude boundaries without a record. |
| `pilot_results.xlsx` | Survey and DCE pilot snapshot for citywide sampling plans. | Export the live `pilot_results` Google Sheet as an Excel workbook and save this copy in the mounted Drive `Dissertation/data/raw` folder. Keep both `survey` and `DCE` tabs. The notebook reads the copy through `drive.mount()` and does not request separate Google Sheets authentication. Re-export after changes to the live Sheet; the copy does not synchronize automatically. |

For planning runs without pilot data, set `PILOT_WORKBOOK_FILE_NAME = None` in the citywide notebook. Survey power is reported separately for assumed outside response rates and the pilot rate, at cluster-effect standard deviations of 0, 5, and 10 percentage points. DCE power shows the earlier verified choice-level results and new approximate Monte Carlo sensitivities for assumed and pilot-fitted baselines, at cluster-effect log-odds standard deviations of 0, 0.25, and 0.50. These variation assumptions are editable and are not estimated from the two pilot boundaries.

All spatial layers are reprojected to EPSG:32614 before distance, area, buffer, and cluster operations. Exported GeoJSON files are transformed to EPSG:4326 (WGS 84) for interoperable mapping.

## Output inventory and field guide

| Output | Produced by | Contents |
|---|---|---|
| `risk_polygon_household_counts.geojson` | Baseline notebook | One feature per selected high-risk polygon, with polygon context and cadastre/vulnerable-lot counts. |
| `catastro_points.geojson` | Baseline notebook | Representative household-proxy point for every included cadastre parcel. |
| `catastro_parcels_4326.geojson` | Baseline notebook | Original cadastre parcel polygons in WGS 84; includes a few non-polygon records that the point export omits. |
| `lotes_vulnerables_points.geojson` | Baseline notebook | Representative point for each included vulnerable lot. |
| `inputs_used_manifest.csv` | Baseline notebook | Input role-to-filename manifest for reproducibility. |
| `clustered_risk_household_counts_perimeter.geojson` or `clustered_risk_household_counts_centroid.geojson` | Clustered notebook | One dissolved risk cluster per gap scenario, including the cluster geometry and screening counts. |
| `clustered_risk_household_counts_perimeter.csv` or `clustered_risk_household_counts_centroid.csv` | Clustered notebook | Same cluster screening table without geometry, suitable for ranking and review. |
| `risk_polygon_boundary_household_sample.geojson` | Boundary-sampling notebook | Randomly selected cadastre parcel polygons with risk-polygon ID, inside/outside side, point-to-boundary distance, and reproducible point ID. |
| `risk_polygon_boundary_eligible_parcels.geojson` | Boundary-sampling notebook | Every eligible parcel polygon once. `boundary_side` is `inside` if its representative point is inside any qualifying selected risk polygon, otherwise `outside`; fields also list qualifying polygon IDs, closest boundary distance, and whether the parcel was selected. |
| `risk_polygon_full_boundary_universe_counts.csv` | Boundary-sampling notebook | Three unique parcel counts using every high-risk polygon in the four-alcaldía file: all inside, inside within the boundary band, and outside every polygon within the boundary band. |
| `risk_polygon_parcel_counts_by_boundary.csv` | Boundary-sampling notebook | One row per high-risk polygon, with cadastre parcel counts anywhere inside, inside the boundary band, and outside every high-risk polygon within the boundary band; band widths are recorded in metres (20 m by default). |
| `risk_polygon_boundary_household_sample.csv` | Boundary-sampling notebook | The same sample attributes with representative-point longitude and latitude instead of geometry. |
| `risk_polygon_boundary_sample_audit.csv` | Boundary-sampling notebook | Requested and eligible counts, realized inside/outside counts, and sampling status for every selected polygon. |
| `citywide_risk_source_district_audit.csv` | Citywide population notebook | Every original source feature, its `NOM_MUN` name, and whether the editable district exclusion list removed it. |
| `citywide_risk_polygon_population_screen.csv/.geojson` | Citywide population notebook | Every single-part high-risk polygon, its source feature ID and part number, `GM_2020` values, mean `IM_2020`, and contributing-colonia counts, population estimate, people/km² density, 2022 settlement-point count, valid raster coverage, screening status, and separate socioeconomic exclusion flags. |
| `citywide_population_eligible_polygons.geojson` | Citywide population notebook | Polygons passing population, density, settlement-point, `GM_2020`, and `IM_2020` screens (above 150 excluded by default; missing kept). |
| `citywide_population_risk_clusters.csv/.geojson` | Citywide population notebook | Dissolved clusters retained after district and boundary screening at 5, 25, 50, 100, and 200 m gaps, with population, area, density, settlement-point count, distinct overlapping-colonia `GM_2020` values, mean `IM_2020`, district names, and span. |
| `citywide_population_cluster_membership.csv` | Citywide population notebook | Polygon-to-cluster links for the retained district and boundary frame. |
| `citywide_cluster_map_{gap}m.html` | Citywide population notebook | Interactive map of selected-gap clusters retained after district and boundary screening, with hover details for polygon count, population, dissolved area, density, settlement-point count, `GM_2020`, mean `IM_2020`, and span. Yellow markers show 2022 records inside shown clusters. The layer control switches between OpenTopoMap streets and terrain and Esri satellite imagery; the saved HTML needs internet access for basemap tiles. |
| `citywide_population_cluster_exclusion_audit.csv/.geojson` | Citywide population notebook | Every cluster at the chosen draw gap, its geographic group, district names, manual exclusion flag, and whether it entered the draw frame. |
| `citywide_population_cluster_draw_frame.csv/.geojson` | Citywide population notebook | Clusters remaining after manual exclusions, with geographic group, random order, and selection status. |
| `citywide_population_selection_totals.csv` | Citywide population notebook | Dissolved-union estimated population before district exclusion, after district exclusion, after boundary filters, after manual cluster exclusions, and after selection. |
| `citywide_sampling_allocation_power_sensitivity.csv` | Citywide population notebook | Combined survey sensitivity results, labeled by assumed or pilot baseline, completed-interview total, cluster count, and cluster-effect variation. |
| `citywide_survey_power_without_pilot.csv` / `citywide_survey_power_with_pilot.csv` | Citywide population notebook | Separate survey simulations using assumed outside response rates or the pilot's observed outside rate. Each includes zero and assumed between-cluster variation. |
| `citywide_dce_power_without_pilot.csv` / `citywide_dce_power_with_pilot.csv` | Citywide population notebook | Separate approximate DCE Monte Carlo sensitivities using assumed choice baselines or the pilot-fitted baseline, at cluster-effect log-odds SDs of 0, 0.25, and 0.50. The notebook also displays the earlier verified choice-level results for comparison. |
| `citywide_survey_pilot_summary.csv` | Citywide population notebook | From the `pilot_results.xlsx` `survey` tab in mounted Drive: moving-answer counts, unknown answers, and observed yes rates by boundary and side. |
| `citywide_dce_pilot_inclusion_audit.csv` | Citywide population notebook | From the `pilot_results.xlsx` `DCE` tab in mounted Drive: respondent-level four-card completeness and model inclusion. Unknown `?` card codes and `NONE` choices remain auditable. |
| `citywide_dce_pilot_choice_shares.csv` | Citywide population notebook | DCE pilot choice counts and shares by boundary and side; known answers on rows with unknown card IDs remain in this descriptive output. |
| `citywide_dce_pilot_baseline_coefficients.csv` | Citywide population notebook | Pooled eight-coefficient DCE baseline from complete identified four-card respondents, with ridge shrinkage. These two-boundary estimates are planning inputs. |
| `citywide_dce_pilot_calibrated_power.csv` | Citywide population notebook | Tentative DCE power by completed-interview total for the prespecified inside versus outside Relocate odds ratio of 1.5, compared with earlier empirical scenarios. The approximation omits cluster variation. |
| `citywide_sampling_reserve_sensitivity.csv` | Citywide population notebook | Ordered reserve counts under assumed site-usability probabilities. |
| `citywide_population_selected_clusters.csv/.geojson` | Citywide population notebook | Primary and reserve candidate polygons once both draw counts are explicitly chosen. |
| `citywide_population_selected_boundary_polygons.geojson` | Citywide population notebook | Individual high-risk polygon parts belonging to selected clusters, with original source IDs, `GM_2020` values, and mean `IM_2020`. |
| `citywide_population_cluster_manifest.json` | Citywide population notebook | Source filenames, `GM_2020` and `IM_2020` assignment and screening rules, population, density, and settlement-point thresholds, five dissolved-union population totals, district and manual cluster exclusion settings, random seed, and geographic splits by gap. |
| `citywide_cluster_size_diagnostics.png` | Citywide population notebook | Cluster counts by gap, member polygon counts, and estimated population at the chosen gap. |
| `citywide_cluster_map_before_draw.png` | Citywide population notebook | Population raster with selected-gap cluster boundaries retained after district and boundary screening and people/km² labels for up to 20 populous clusters, produced before the draw. |
| `citywide_cluster_gap_comparison.png` | Citywide population notebook | Small maps comparing 5, 25, 50, 100, and 200 m cluster geometry, with median cluster density in each title. |

The current citywide population-and-cluster rules are specified in [SAMPLING_PROTOCOL.md](SAMPLING_PROTOCOL.md). In particular, no alcaldía is currently excluded, the population cutoff is strictly above 30 estimated people, the density cutoff is strictly above 0 people/km², the draw gap is 100 m, and the 100 m draw cell has 47 manual cluster exclusions. The notebook source and manifest govern any later run-specific changes. The site draw remains a screening step; it does not establish household eligibility or the final survey sampling frame.

The boundary-sampling notebook reads the baseline outputs `risk_polygon_household_counts.geojson`, `catastro_points.geojson`, and `catastro_parcels_4326.geojson`. Its default configuration samples 15 parcels each from `P01311` and `P01427` within 20 m of their boundaries, using a fixed seed. The polygon selection can be changed to all polygons. The eligible-parcel GeoJSON and its candidate count follow that current sampling selection; with the default settings they cover only `P01311` and `P01427`. An overlapping parcel appears once with all qualifying risk-polygon IDs and a `selected_for_sample` flag. For a parcel eligible on different sides of different risk polygons, `boundary_side` uses inside precedence. The **full universe** table and CSV instead count unique parcels across **every** high-risk polygon in the four-alcaldía file, regardless of sampling selection: (1) anywhere inside, (2) inside within the configured boundary band, and (3) outside every high-risk polygon within the configured boundary band. The per-boundary CSV reports the same three measures for each individual polygon; a parcel can appear in several rows, so row totals are not unique citywide totals. These measures use only cadastre representative points, not the vulnerable-lot layers. The inside-band count is a subset of the all-inside count. A bar chart and parcel maps preview these results in Colab before download. Each saved cadastre parcel is selected at most once in a run; the audit reports shortages instead of silently reducing the requested sample. The export verifies that each representative point matches its parcel polygon. The `P` IDs and cadastre point IDs are generated by the saved baseline outputs, so keep those files from the same run when reproducing a sample.

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
| Geographic scope | Citywide risk-polygon screening; no current alcaldía exclusion. Earlier cadastre analyses cover four alcaldías only. |
| Polygon gap sensitivity | 25 m, 50 m, 100 m, 200 m. |
| Cluster distance metric | Parameterized: perimeter or centroid. |
| Outside household band | 20 m default parameter. |
| Inside household rule | 20 m boundary strip by default; `all_inside` available. |
| Household duplication within cluster | Prevented through dissolved cluster geometries. |
| Household duplication across clusters | Allowed deliberately. |
| Sampling design | Still under evaluation; do not freeze it before site-level physical checks. |

## Next steps

1. Reconcile the 47 manual cluster exclusions with their reasons in the companion spreadsheet before freezing a draw.
2. Check residential-location availability and inside/outside feasibility for the eligible citywide clusters.
3. Select the final number of clusters and household-location allocation using field capacity and cluster-sensitive power scenarios.
4. Freeze the final cluster draw, its input versions, random seed, and exclusion audit before fieldwork.
