"""Build the standalone Colab notebook for incremental parcel sampling."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CELLS = []


def md(source):
    CELLS.append({'cell_type':'markdown','metadata':{},'source':source.splitlines(True)})


def code(source):
    CELLS.append({'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
                  'source':source.splitlines(True)})


md('''# Parcel and household sampling

Draw parcels near each listed risk boundary. At a selected parcel, list its eligible households and randomly choose one. New clusters can be added later without changing earlier draws.
''')

code('''# Run this cell in a fresh Colab runtime.
%pip -q install geopandas pyogrio shapely folium

from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, math
import numpy as np
import pandas as pd
import geopandas as gpd
import folium
from IPython.display import display

try:
    from google.colab import drive
    drive.mount('/content/drive', force_remount=False)
    PROJECT_ROOT = Path('/content/drive/MyDrive/Dissertation')
except ImportError:
    PROJECT_ROOT = Path.cwd()
print('Project root:', PROJECT_ROOT)
''')

md('''## Inputs

Put the latest Parcel Review GeoPackage in `MyDrive/Dissertation/data/review/`. The saved 12-cluster draw CSV is useful for first-stage probabilities, but the five listed clusters can be sampled before that file is available.
''')

code('''REVIEW_GPKG = PROJECT_ROOT / 'data/review/cdmx_parcel_review.gpkg'
CLUSTER_DRAW_CSV = PROJECT_ROOT / 'data/output/citywide_population_cluster_draw_frame.csv'
RUN_LABEL = 'study_2026'  # keep this unchanged when adding clusters
OUTPUT_BASE = PROJECT_ROOT / 'data/output/parcel_household_sample' / RUN_LABEL
DRAW_STAGE = 1  # use 2 only for the optional later expansion
RUN_DRAW = True
STAGE1_RELEASED_RESERVES_CSV = OUTPUT_BASE / 'stage1/released_reserves.csv'

EXPECTED_PRIMARY_CLUSTERS = 12
BOUNDARY_BAND_M = 20.0
STAGE1_COMPLETED_TARGET = 200
STAGE2_ADDITIONAL_COMPLETED_TARGET = 200
PLANNING_RESPONSE_RATE = 0.50
RANDOM_SEED = 20261120

if not REVIEW_GPKG.exists():
    raise FileNotFoundError(f'Copy the current review GeoPackage to {REVIEW_GPKG}')
if DRAW_STAGE not in (1,2) or not 0 < PLANNING_RESPONSE_RATE <= 1:
    raise ValueError('Check DRAW_STAGE and PLANNING_RESPONSE_RATE.')
''')

code((ROOT/'scripts/parcel_incremental_sampling.py').read_text(encoding='utf-8'))

code('''review, clusters, frame = load_parcel_frame(REVIEW_GPKG, BOUNDARY_BAND_M)
primary_ids, primary_probabilities = read_primary_clusters(
    CLUSTER_DRAW_CSV, EXPECTED_PRIMARY_CLUSTERS)
listed_ids = set(frame.cluster_id)
if primary_ids is None:
    print('Cluster draw CSV absent: sampling listed clusters; first-stage probabilities are unavailable.')
else:
    outside_primary = sorted(listed_ids - primary_ids)
    if outside_primary:
        print('Listed clusters absent from the 12 primary draw:', outside_primary)
    print('Primary clusters listed so far:', len(listed_ids & primary_ids), 'of', EXPECTED_PRIMARY_CLUSTERS)
target = STAGE1_COMPLETED_TARGET if DRAW_STAGE == 1 else STAGE2_ADDITIONAL_COMPLETED_TARGET
planned_contacts = math.ceil(target / PLANNING_RESPONSE_RATE)
quota_per_side = math.ceil(planned_contacts / (2 * EXPECTED_PRIMARY_CLUSTERS))
print('Per cluster and side:', quota_per_side, 'parcel contacts; all 12 clusters would plan',
      quota_per_side * 2 * EXPECTED_PRIMARY_CLUSTERS, 'contacts.')
print('Unreviewed rows in listed clusters:',
      int(review.review_status.eq('unreviewed').sum()))
display(cluster_summary(review, frame, None, quota_per_side, primary_ids))
''')

md('''## Draw and fieldwork

The table shows every cluster in Parcel Review. The draw fixes each cluster's random order separately. If a selected parcel is a store or empty, log it and use the next reserve on the **same cluster and side**. At a residential parcel with `H` eligible households, interview number `floor(household_draw_u × H) + 1` from a fixed listing order.
''')

code('''if RUN_DRAW:
    draw, stage_dir, added, reused, migrated, rebalanced = incremental_draw(
        frame, clusters, OUTPUT_BASE, DRAW_STAGE, quota_per_side, RANDOM_SEED,
        primary_probabilities,
        STAGE1_RELEASED_RESERVES_CSV if DRAW_STAGE == 2 else None)
    if DRAW_STAGE == 1 and not STAGE1_RELEASED_RESERVES_CSV.exists():
        pd.DataFrame(columns=['parcel_id']).to_csv(STAGE1_RELEASED_RESERVES_CSV,index=False)
    released_ids = (load_released_reserves(STAGE1_RELEASED_RESERVES_CSV,draw)
                    if DRAW_STAGE == 1 else set())
    save_field_outputs(review, draw, stage_dir, released_ids)
    summary = cluster_summary(review, frame, draw, quota_per_side, primary_ids)
    summary.to_csv(stage_dir/'cluster_sampling_summary.csv',index=False)
    manifest = {'created_utc':datetime.now(timezone.utc).isoformat(),
                'run_label':RUN_LABEL,'stage':DRAW_STAGE,
                'listed_cluster_ids':sorted(listed_ids),
                'primary_cluster_draw_file':str(CLUSTER_DRAW_CSV) if primary_ids else None,
                'planned_completed_interviews':target,
                'planning_response_rate':PLANNING_RESPONSE_RATE,
                'planned_contacts_for_12':planned_contacts,
                'quota_per_cluster_side':quota_per_side,
                'random_seed':RANDOM_SEED,
                'added_clusters':added,'reused_clusters':reused,
                'migrated_prior_cluster_draws':migrated,
                'rebalanced_clusters':rebalanced}
    (stage_dir/'sampling_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('New cluster draws:', added, '| Preserved cluster draws:', reused)
    if migrated:
        print('Migrated older draw files, preserving their random order:', migrated)
    if rebalanced:
        print('Balanced inside/outside selections using saved random ranks:', rebalanced)
    print('Selected parcels:', int(draw.selected.sum()), '| Reserves:', int((~draw.selected).sum()))
    display(summary)
    print('Outputs:', stage_dir)
else:
    draw = None
    print('Set RUN_DRAW=True to save the random selection.')
''')

code('''if draw is not None:
    sample_map = show_sample_map(review, clusters, draw, stage_dir,
                                 released_ids if DRAW_STAGE == 1 else None)
    display(sample_map)
    print('Interactive map:', stage_dir / 'selected_parcels_map.html')
''')

notebook = {'cells':CELLS,
            'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
                        'language_info':{'name':'python'}},
            'nbformat':4,'nbformat_minor':5}
target = ROOT/'parcel_household_sampling_colab.ipynb'
target.write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
print(target)
