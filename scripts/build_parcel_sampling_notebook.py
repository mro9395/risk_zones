"""Write the standalone CDMX parcel and household sampling notebook."""
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

Draw parcels within 20 m of each selected risk boundary, balanced by cluster and inside/outside side. Interview one randomly chosen household at each selected parcel.

A parcel can contain several households. List them at the parcel, then use the saved random number to pick one.
''')

code('''# Run this installation cell in a fresh Google Colab runtime.
%pip -q install geopandas pyogrio shapely

from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, math
import numpy as np
import pandas as pd
import geopandas as gpd
from IPython.display import display

try:
    from google.colab import drive
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

if IN_COLAB:
    drive.mount('/content/drive', force_remount=False)
    PROJECT_ROOT = Path('/content/drive/MyDrive/Dissertation')
else:
    PROJECT_ROOT = Path.cwd()
print('Project root:', PROJECT_ROOT)
''')

md('''## Set up

For Colab, copy the current review GeoPackage to `MyDrive/Dissertation/data/review/`. Put the earlier notebook's `citywide_population_cluster_draw_frame.csv` in `data/output/`.

The cluster list and its first-stage probabilities come from the **cluster-draw CSV** saved by the earlier notebook. The draw stops if that file is absent. Use the power table for the completed-interview target.
''')

code('''REVIEW_GPKG = PROJECT_ROOT / 'data/review/cdmx_parcel_review.gpkg'
POWER_CRITERIA_CSV = PROJECT_ROOT / 'data/output/citywide_survey_sample_size_criteria_comparison.csv'
CLUSTER_DRAW_CSV = PROJECT_ROOT / 'data/output/citywide_population_cluster_draw_frame.csv'
RUN_LABEL = 'study_2026'  # retain this for both waves; change for a new design
OUTPUT_BASE = PROJECT_ROOT / 'data/output/parcel_household_sample' / RUN_LABEL
DRAW_STAGE = 1  # 1 now; set 2 only after stage 1 is frozen and extension is chosen
OUTPUT_DIR = OUTPUT_BASE / f'stage{DRAW_STAGE}'
STAGE1_RELEASED_RESERVES_CSV = None  # for Stage 2: CSV with parcel_id of reserves actually released; empty header if none

EXPECTED_PRIMARY_CLUSTERS = 12
BOUNDARY_BAND_M = 20.0
STAGE1_COMPLETED_TARGET = 200
STAGE2_ADDITIONAL_COMPLETED_TARGET = 200
PLANNING_RESPONSE_RATE = 0.50  # assumes half of selected parcel contacts yield completed interviews
RANDOM_SEED = 20261120
RUN_DRAW = False  # set True once the 12-cluster frame and response rate are ready
FINAL_DRAW = True  # set False only for a labeled pilot/provisional test

if not REVIEW_GPKG.exists():
    raise FileNotFoundError(f'Copy the latest review GeoPackage to {REVIEW_GPKG}')
if DRAW_STAGE not in (1,2):
    raise ValueError('DRAW_STAGE must be 1 or 2')
''')

code('''# Load the selected primary sites from the earlier cluster notebook.
cluster_draw = None
cluster_selection_probabilities = {}
if CLUSTER_DRAW_CSV.exists():
    cluster_draw = pd.read_csv(CLUSTER_DRAW_CSV, dtype={'cluster_id':str})
    needed = {'cluster_id','selection_status','primary_inclusion_probability'}
    if not needed <= set(cluster_draw.columns) or cluster_draw.cluster_id.duplicated().any():
        raise ValueError('Cluster draw CSV has missing fields or duplicate cluster IDs.')
    primary = cluster_draw.loc[cluster_draw.selection_status.eq('primary')].copy()
    if len(primary) != EXPECTED_PRIMARY_CLUSTERS:
        raise ValueError(f'Expected {EXPECTED_PRIMARY_CLUSTERS} primary clusters, found {len(primary)}.')
    primary['primary_inclusion_probability'] = pd.to_numeric(
        primary.primary_inclusion_probability, errors='coerce')
    if primary.primary_inclusion_probability.isna().any() or not primary.primary_inclusion_probability.between(0,1,inclusive='right').all():
        raise ValueError('Invalid first-stage cluster probabilities.')
    ACTIVE_CLUSTER_IDS = sorted(primary.cluster_id.tolist())
    cluster_selection_probabilities = dict(zip(primary.cluster_id,primary.primary_inclusion_probability))
    print('Linked primary clusters from earlier draw:',len(ACTIVE_CLUSTER_IDS))
else:
    ACTIVE_CLUSTER_IDS = ['PER_100m_C00038','PER_100m_C00043']
    print('Cluster-draw CSV absent; showing the two pilot sites only. No final draw can run.')

# Validate the review layer, calculate representative-point distance to the cluster line.
review = gpd.read_file(REVIEW_GPKG, layer='parcel_review', fid_as_index=True)
clusters = gpd.read_file(REVIEW_GPKG, layer='study_clusters').set_index('cluster_id')
if review.crs != clusters.crs or review.crs.to_epsg() != 32614:
    raise ValueError('Review and cluster layers must both use EPSG:32614 (metres).')
if review.parcel_id.isna().any() or review.parcel_id.str.upper().duplicated().any():
    raise ValueError('Missing or duplicate parcel IDs in the review layer.')
if review.geometry.isna().any() or (~review.geometry.is_valid).any():
    raise ValueError('Repair missing or invalid review polygons before drawing.')
missing_cluster_frames = sorted(set(ACTIVE_CLUSTER_IDS) - set(clusters.index))
if missing_cluster_frames:
    print('Selected primary clusters without reviewed parcel geometry:',missing_cluster_frames)
if review.cluster_id.isna().any() or review.boundary_side.isna().any():
    raise ValueError('A parcel is missing cluster_id or boundary_side.')
if not set(review.boundary_side).issubset({'inside','outside'}):
    raise ValueError('Unexpected boundary_side value.')

review['boundary_distance_m'] = [row.geometry.representative_point().distance(
    clusters.loc[row.cluster_id].geometry.boundary) for _,row in review.iterrows()]
review['within_band'] = review.boundary_distance_m <= BOUNDARY_BAND_M
review['active_cluster'] = review.cluster_id.isin(ACTIVE_CLUSTER_IDS)
review['review_ready'] = ~review.review_status.isin(['unreviewed','deleted'])
frame = review.loc[review.within_band & review.active_cluster & review.review_status.ne('deleted')].copy()

print('All review parcels:',len(review),'within 20 m in active clusters:',len(frame))
print('Unreviewed candidate parcels:',int((~frame.review_ready).sum()))
display(pd.crosstab(frame.cluster_id,frame.boundary_side).reindex(columns=['inside','outside'],fill_value=0))
''')

md('''## Choose the sample size

Stage 1 targets **200 completed interviews**. If time permits, Stage 2 targets **200 more** from units not selected in Stage 1. Both waves use the same cluster × side frame. Set a response-rate assumption to determine how many locations to draw.

The earlier *considered-moving* power model still puts 400 completions below its 80% reference. Pilot C00038 has only 36 inside and 34 outside parcels in the 20 m band.
''')

code('''if POWER_CRITERIA_CSV.exists():
    power = pd.read_csv(POWER_CRITERIA_CSV)
    required={'outcome','baseline_source','primary_clusters','cluster_effect_sd',
              'criterion','first_tested_n','status'}
    if not required <= set(power.columns):
        raise ValueError(f'Power criteria file missing {required-set(power.columns)}')
    display(power.loc[power.primary_clusters.eq(EXPECTED_PRIMARY_CLUSTERS),
                      list(required)].sort_values(['outcome','criterion','baseline_source','cluster_effect_sd']))
else:
    print('Power criteria CSV not found:',POWER_CRITERIA_CSV)
print('For 12 clusters, completed interviews per side per cluster:')
display(pd.DataFrame({'completed_total':[200,300,400,600,800,1000],
                      'completed_per_cluster_side':[n/(2*EXPECTED_PRIMARY_CLUSTERS)
                                                    for n in [200,300,400,600,800,1000]]}))
''')

md('''## Draw

Run Stage 1 first. All reviewed parcels enter the draw; check residential eligibility during the visit. If a parcel has no eligible household, log it and release the next reserve on the same cluster and side. At a residential parcel, list all `H` eligible households in a fixed order and interview number `floor(household_draw_u × H) + 1`. For Stage 2, list released Stage 1 reserve IDs in `STAGE1_RELEASED_RESERVES_CSV` so they cannot be drawn again.
''')

code('''# Parcels are the frame; one household is chosen randomly inside each selected parcel.
units=frame.drop(columns='geometry').copy()
units['unit_id']=units.parcel_id

units['inclusion_probability']=units.cluster_id.map(cluster_selection_probabilities)
frame_signature=units[['unit_id','cluster_id','boundary_side']].sort_values('unit_id').to_csv(index=False)
frame_sha256=hashlib.sha256(frame_signature.encode()).hexdigest()
review_sha256=hashlib.sha256(REVIEW_GPKG.read_bytes()).hexdigest()
cluster_draw_sha256=(hashlib.sha256(CLUSTER_DRAW_CSV.read_bytes()).hexdigest()
                     if cluster_draw is not None else None)

if RUN_DRAW and FINAL_DRAW:
    if cluster_draw is None or missing_cluster_frames or len(ACTIVE_CLUSTER_IDS)!=EXPECTED_PRIMARY_CLUSTERS:
        raise ValueError('Run the earlier cluster notebook and supply reviewed parcels for all 12 primary clusters.')
    if not frame.review_ready.all():
        raise ValueError('Final draw requires reviewed parcel statuses.')

def stratum_seed(master,stage,cluster,side):
    digest=hashlib.sha256(f'{master}|stage{stage}|{cluster}|{side}'.encode()).digest()
    return int.from_bytes(digest[:8],'big')

draw=None
prior_selected=pd.DataFrame()
stage_contact_target=None
if RUN_DRAW:
    if PLANNING_RESPONSE_RATE is None or not 0 < PLANNING_RESPONSE_RATE <= 1:
        raise ValueError('Set a planning response rate in (0,1].')
    target=(STAGE1_COMPLETED_TARGET if DRAW_STAGE==1 else STAGE2_ADDITIONAL_COMPLETED_TARGET)
    if not isinstance(target,int) or target<1:
        raise ValueError('The stage completed-interview target must be a positive integer.')
    if units.unit_id.duplicated().any():
        raise ValueError('Sampling unit IDs must be unique.')
    strata=sorted(set(zip(units.cluster_id,units.boundary_side)))
    if FINAL_DRAW and len(strata)!=2*EXPECTED_PRIMARY_CLUSTERS:
        raise ValueError('Every selected primary cluster needs eligible units on both sides.')
    if not strata:
        raise ValueError('No eligible units in the selected frame.')
    if DRAW_STAGE==2:
        stage1_dir=OUTPUT_BASE/'stage1'
        old_manifest=json.loads((stage1_dir/'sampling_manifest.json').read_text(encoding='utf-8'))
        for key,value in {'frame_sha256':frame_sha256,'review_sha256':review_sha256,
                          'cluster_draw_sha256':cluster_draw_sha256,'sample_unit':'one_household_per_parcel',
                          'active_clusters':ACTIVE_CLUSTER_IDS,'boundary_band_m':BOUNDARY_BAND_M,
                          'random_seed':RANDOM_SEED}.items():
            if old_manifest.get(key)!=value:
                raise ValueError(f'Stage 1 frame/design changed: {key}. Audit before extension.')
        prior=pd.read_csv(stage1_dir/'random_order_and_selection.csv',dtype={'unit_id':str})
        prior_selected=prior.loc[prior.selected.astype(str).str.lower().eq('true')].copy()
        if STAGE1_RELEASED_RESERVES_CSV is None:
            raise ValueError('For Stage 2, provide a CSV listing Stage 1 released reserve parcel_id values (header only if none).')
        released=pd.read_csv(STAGE1_RELEASED_RESERVES_CSV,dtype={'parcel_id':str})
        if 'parcel_id' not in released or released.parcel_id.isna().any() or released.parcel_id.duplicated().any():
            raise ValueError('Released-reserve CSV needs unique, nonempty parcel_id values.')
        reserve_rows=prior.loc[~prior.selected.astype(str).str.lower().eq('true')].copy()
        if not set(released.parcel_id).issubset(set(reserve_rows.parcel_id)):
            raise ValueError('Released-reserve CSV names a parcel outside the Stage 1 reserve order.')
        prior_released=reserve_rows.loc[reserve_rows.parcel_id.isin(released.parcel_id)].copy()
        prior_released['selected']=True
        prior_selected=pd.concat([prior_selected,prior_released],ignore_index=True)
        if not set(prior_selected.unit_id).issubset(set(units.unit_id)):
            raise ValueError('A stage 1 selected unit is absent from the current frame.')
        available=units.loc[~units.unit_id.isin(prior_selected.unit_id)].copy()
    else:
        available=units.copy()
    stage_contact_target=math.ceil(target/PLANNING_RESPONSE_RATE)
    base,extra=divmod(stage_contact_target,len(strata))
    rotation=0 if DRAW_STAGE==1 else math.ceil(STAGE1_COMPLETED_TARGET/PLANNING_RESPONSE_RATE)%len(strata)
    quotas={key:base for key in strata}
    for j in range(extra):
        quotas[strata[(rotation+j)%len(strata)]]+=1
    parts=[]
    for cluster,side in strata:
        group=available.loc[available.cluster_id.eq(cluster)&available.boundary_side.eq(side)].sort_values('unit_id').copy()
        full_count=int((units.cluster_id.eq(cluster)&units.boundary_side.eq(side)).sum())
        prior_count=int((prior_selected.cluster_id.eq(cluster)&prior_selected.boundary_side.eq(side)).sum()) if DRAW_STAGE==2 else 0
        quota=quotas[(cluster,side)]
        if len(group)<quota:
            raise ValueError(f'{cluster} {side}: {len(group)} remain; need {quota}. Review feasibility.')
        rng=np.random.default_rng(stratum_seed(RANDOM_SEED,DRAW_STAGE,cluster,side))
        group['random_order']=rng.permutation(len(group))+1
        group['household_draw_u']=rng.random(len(group))
        group['selected']=group.random_order.le(quota)
        group['stage_contact_quota']=quota
        group['stage_conditional_probability']=quota/len(group)
        group['within_cluster_side_probability']=(prior_count+quota)/full_count
        group['overall_inclusion_probability']=(group.inclusion_probability *
                                                group.within_cluster_side_probability)
        parts.append(group)
    draw=pd.concat(parts,ignore_index=True)
    if DRAW_STAGE==2 and len(prior_released):
        draw['overall_inclusion_probability']=np.nan  # adaptive reserve releases need outcome-based weights
    draw['draw_stage']=DRAW_STAGE
    draw['draw_scope']='final' if FINAL_DRAW else 'provisional_partial'
    print(f'Stage {DRAW_STAGE}: {target} planned completions; {stage_contact_target} contacts at the assumed response rate.')
    display(draw.groupby(['cluster_id','boundary_side']).agg(remaining_frame=('unit_id','size'),
             selected=('selected','sum')))
else:
    print('No draw yet. Set response rate, resolve frame gaps, then set RUN_DRAW=True.')
''')

code('''# Save IDs, field instructions, random order, and provenance.
export_dir=OUTPUT_DIR if draw is not None else OUTPUT_BASE/'preview'
if draw is not None and (export_dir/'sampling_manifest.json').exists():
    raise FileExistsError('Final draw already exists; choose a new RUN_LABEL or retain the frozen draw.')
export_dir.mkdir(parents=True,exist_ok=True)
frame.drop(columns='geometry').to_csv(export_dir/'candidate_parcel_frame.csv',index=False)
if draw is not None:
    draw.to_csv(export_dir/'random_order_and_selection.csv',index=False)
    reserves=draw.loc[~draw.selected].sort_values(['cluster_id','boundary_side','random_order']).copy()
    reserves['reserve_rank']=reserves.random_order-reserves.stage_contact_quota
    reserves.to_csv(export_dir/'reserve_parcel_order.csv',index=False)
    contact=draw.loc[draw.selected,['unit_id','parcel_id','cluster_id','boundary_side',
                                    'random_order','within_cluster_side_probability',
                                    'overall_inclusion_probability']].copy()
    contact['household_draw_u']=draw.loc[draw.selected,'household_draw_u'].to_numpy()
    contact['eligible_households_count']=''
    contact['chosen_household_number']=''
    contact['chosen_household_id']=''
    contact['eligibility']=''
    contact['contact_attempts']=''
    contact['contact_outcome']=''
    contact['survey_id']=''
    contact.to_csv(export_dir/'field_contact_log_template.csv',index=False)
    selected_ids=set(draw.loc[draw.selected,'parcel_id'])
    selected_geo=review.loc[review.parcel_id.isin(selected_ids)].copy()
    selected_geo.to_file(export_dir/'selected_parcels.gpkg',layer='selected_parcels',driver='GPKG')
    if DRAW_STAGE==2:
        combined=pd.concat([prior_selected,draw.loc[draw.selected]],ignore_index=True)
        for (cluster,side),indices in combined.groupby(['cluster_id','boundary_side']).groups.items():
            frame_n=int((units.cluster_id.eq(cluster)&units.boundary_side.eq(side)).sum())
            conditional=len(indices)/frame_n
            combined.loc[indices,'within_cluster_side_probability']=conditional
            combined.loc[indices,'overall_inclusion_probability']=(
                cluster_selection_probabilities.get(cluster,np.nan)*conditional)
        if len(prior_released):
            combined['overall_inclusion_probability']=np.nan
            print('Stage 1 reserves were released; final household weights need the field outcomes.')
        combined.to_csv(export_dir/'combined_selected_stage1_stage2.csv',index=False)
manifest={'created_utc':datetime.now(timezone.utc).isoformat(),
          'run_label':RUN_LABEL,
          'draw_stage':DRAW_STAGE,'frame_sha256':frame_sha256,
          'review_gpkg':str(REVIEW_GPKG),'review_sha256':review_sha256,
          'cluster_draw_csv':str(CLUSTER_DRAW_CSV),
          'cluster_draw_sha256':cluster_draw_sha256,
          'sample_unit':'one_household_per_parcel','active_clusters':ACTIVE_CLUSTER_IDS,
          'expected_primary_clusters':EXPECTED_PRIMARY_CLUSTERS,'boundary_band_m':BOUNDARY_BAND_M,
          'stage1_completed_target':STAGE1_COMPLETED_TARGET,
          'stage2_additional_completed_target':STAGE2_ADDITIONAL_COMPLETED_TARGET,
          'stage_contact_target':stage_contact_target,
          'planning_response_rate':PLANNING_RESPONSE_RATE,'random_seed':RANDOM_SEED,
          'final_draw':FINAL_DRAW,'run_draw':RUN_DRAW,
          'household_selection_rule':'floor(household_draw_u * eligible_households_count) + 1'}
(export_dir/'sampling_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Outputs:',export_dir)
''')

notebook={'cells':CELLS,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
                                   'language_info':{'name':'python'}},'nbformat':4,'nbformat_minor':5}
target=ROOT/'parcel_household_sampling_colab.ipynb'
target.write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
print(target)
