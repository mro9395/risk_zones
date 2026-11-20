"""Check five-cluster sampling, later cluster additions, and Stage 2 nonoverlap."""
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone
import hashlib
import json
import math

import geopandas as gpd
import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[1]
notebook = json.loads((root/'parcel_household_sampling_colab.ipynb').read_text(encoding='utf-8'))
assert len(notebook['cells']) == 9
assert 'PLANNING_RESPONSE_RATE = 0.50' in ''.join(notebook['cells'][3]['source'])
assert 'FIELD_ELIGIBILITY_FILE' not in json.dumps(notebook)

namespace = {'Path':Path,'pd':pd,'np':np,'gpd':gpd,'hashlib':hashlib,'json':json}
exec(compile(''.join(notebook['cells'][4]['source']),'helpers','exec'),namespace)
load = namespace['load_parcel_frame']
draw_fn = namespace['incremental_draw']
summary_fn = namespace['cluster_summary']
review,clusters,frame = load(root/'data/review/cdmx_parcel_review.gpkg',20)
assert len(set(frame.cluster_id)) == 5
assert not review.review_status.eq('unreviewed').any()

with TemporaryDirectory() as folder:
    base = Path(folder)
    first,stage_dir,added,reused,migrated,rebalanced = draw_fn(frame,clusters,base,1,17,20261120,{})
    assert len(added) == 5 and not reused
    summary = summary_fn(review,frame,first,17,None).set_index('cluster_id')
    assert len(summary) == 5
    assert summary.loc['PER_100m_C00044','inside_selected'] == 7
    assert summary.loc['PER_100m_C00044','outside_selected'] == 7
    assert summary.loc['PER_100m_C00044','inside_shortfall'] == 10
    assert first.selected.sum() == 150
    namespace['save_field_outputs'](review,first,stage_dir)
    assert (stage_dir/'selected_parcels.geojson').exists()
    contact_path = stage_dir/'field_contact_log_template.csv'
    contact = pd.read_csv(contact_path,dtype=str)
    contact.loc[0,'eligibility'] = 'store'
    contact.to_csv(contact_path,index=False)
    namespace['save_field_outputs'](review,first,stage_dir)
    assert pd.read_csv(contact_path,dtype=str).loc[0,'eligibility'] == 'store'
    first_reserve = first.loc[~first.selected,'parcel_id'].iloc[0]
    namespace['save_field_outputs'](review,first,stage_dir,{first_reserve.upper()})
    logged = pd.read_csv(contact_path,dtype=str)
    assert logged.loc[logged.parcel_id.eq(first_reserve),'release_type'].iloc[0] == 'reserve'
    assert logged.loc[0,'eligibility'] == 'store'
    frozen = {p.name:p.read_bytes() for p in (stage_dir/'frozen_clusters').glob('*.csv')}

    again,_,added,reused,migrated,rebalanced = draw_fn(frame,clusters,base,1,17,20261120,{})
    assert not added and len(reused) == 5
    assert {p.name:p.read_bytes() for p in (stage_dir/'frozen_clusters').glob('*.csv')} == frozen
    assert set(first.loc[first.selected,'parcel_id']) == set(again.loc[again.selected,'parcel_id'])

    old_base = base/'old_allocation'
    _,old_stage,_,_,_,_ = draw_fn(frame,clusters,old_base,1,17,20261120,{})
    c44_csv = old_stage/'frozen_clusters/PER_100m_C00044.csv'
    c44_meta = old_stage/'frozen_clusters/PER_100m_C00044.json'
    old_part = pd.read_csv(c44_csv)
    outside = old_part.boundary_side.eq('outside')
    old_part.loc[outside,'selected'] = old_part.loc[outside,'random_order'].le(17)
    old_part.to_csv(c44_csv,index=False)
    old_metadata = json.loads(c44_meta.read_text(encoding='utf-8'))
    old_metadata.pop('allocation_rule')
    c44_meta.write_text(json.dumps(old_metadata),encoding='utf-8')
    balanced,_,_,_,_,rebalanced = draw_fn(frame,clusters,old_base,1,17,20261120,{})
    assert rebalanced == ['PER_100m_C00044']
    assert balanced.selected.sum() == 150
    assert (old_stage/'previous_draws/PER_100m_C00044_before_balance.csv').exists()

    legacy_base = base/'legacy_run'
    (legacy_base/'stage1').mkdir(parents=True)
    first.to_csv(legacy_base/'stage1/random_order_and_selection.csv',index=False)
    migrated_draw,_,added,reused,migrated,rebalanced = draw_fn(frame,clusters,legacy_base,1,17,20261120,{})
    assert not added and len(reused) == len(migrated) == 5
    assert set(migrated_draw.loc[migrated_draw.selected,'parcel_id']) == set(
        first.loc[first.selected,'parcel_id'])

    extra_parts = []
    extra_clusters = []
    for old_id,new_id in [('PER_100m_C00037','PER_100m_C00991'),
                          ('PER_100m_C00038','PER_100m_C00992')]:
        part = frame.loc[frame.cluster_id.eq(old_id)].copy()
        part['cluster_id'] = new_id
        part['parcel_id'] = part.parcel_id + '_' + new_id
        extra_parts.append(part)
        row = clusters.loc[[old_id]].copy()
        row.index = [new_id]
        extra_clusters.append(row)
    expanded_frame = gpd.GeoDataFrame(pd.concat([frame,*extra_parts]),geometry='geometry',crs=frame.crs)
    expanded_clusters = gpd.GeoDataFrame(pd.concat([clusters,*extra_clusters]),geometry='geometry',crs=clusters.crs)
    expanded,_,added,reused,migrated,rebalanced = draw_fn(expanded_frame,expanded_clusters,base,1,17,20261120,{})
    assert len(added) == 2 and len(reused) == 5
    old = expanded.loc[expanded.cluster_id.isin(set(frame.cluster_id))]
    assert set(old.loc[old.selected,'parcel_id']) == set(first.loc[first.selected,'parcel_id'])
    assert {p.name:p.read_bytes() for p in (stage_dir/'frozen_clusters').glob('*.csv')
            if p.name in frozen} == frozen

    reserve_id = expanded.loc[~expanded.selected,'parcel_id'].iloc[0]
    released_path = base/'released.csv'
    pd.DataFrame({'parcel_id':[reserve_id]}).to_csv(released_path,index=False)
    second,_,_,_,_,_ = draw_fn(expanded_frame,expanded_clusters,base,2,17,20261120,{},released_path)
    assert reserve_id not in set(second.parcel_id)
    assert set(expanded.loc[expanded.selected,'parcel_id']).isdisjoint(
        set(second.loc[second.selected,'parcel_id']))
    assert second.overall_inclusion_probability.isna().all()

    cells = notebook['cells']
    run = {'Path':Path,'pd':pd,'np':np,'gpd':gpd,'hashlib':hashlib,'json':json,
           'math':math,'datetime':datetime,'timezone':timezone,'PROJECT_ROOT':root,
           'display':lambda *_:None}
    exec(compile(''.join(cells[3]['source']),'settings','exec'),run)
    run.update(OUTPUT_BASE=base/'notebook_run',
               CLUSTER_DRAW_CSV=base/'missing_cluster_draw.csv',
               STAGE1_RELEASED_RESERVES_CSV=base/'notebook_run/stage1/released_reserves.csv')
    for index in (4,5,7):
        exec(compile(''.join(cells[index]['source']),f'cell {index}','exec'),run)
    assert len(run['summary']) == 5
    assert (run['stage_dir']/'cluster_sampling_summary.csv').exists()
    assert (run['stage_dir']/'reserve_parcel_order.csv').exists()
    print('Incremental sampling and Stage 2 nonoverlap passed')
