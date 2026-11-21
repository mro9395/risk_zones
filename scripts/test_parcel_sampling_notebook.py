"""Check compact sampling outputs, incremental draws, and reserve exclusions."""
from pathlib import Path
from tempfile import TemporaryDirectory
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
assert 'released_reserves.csv' not in json.dumps(notebook)

namespace = {'Path':Path,'pd':pd,'np':np,'gpd':gpd,'hashlib':hashlib,'json':json}
exec(compile(''.join(notebook['cells'][4]['source']),'helpers','exec'),namespace)
review, clusters, frame = namespace['load_parcel_frame'](
    root/'data/review/cdmx_parcel_review.gpkg',20)
draw_fn = namespace['incremental_draw']

with TemporaryDirectory() as folder:
    base = Path(folder)
    first, stage_dir, added, reused, _, _ = draw_fn(
        frame,clusters,base,1,8,20261120,{})
    assert len(added) == 5 and not reused and first.selected.sum() == 78
    assert len(json.loads((stage_dir/'frozen_draw_metadata.json').read_text())) == 5
    assert not (stage_dir/'frozen_clusters').exists()
    assert not (stage_dir/'previous_draws').exists()
    reserves_path = stage_dir/'reserve_parcel_order.csv'
    reserves = pd.read_csv(reserves_path,dtype=str)
    assert set(reserves.released) == {'false'}
    reserve_id = reserves.loc[0,'parcel_id']
    reserves.loc[0,'released'] = 'true'
    reserves.to_csv(reserves_path,index=False)

    again, _, added, reused, _, _ = draw_fn(frame,clusters,base,1,8,20261120,{})
    assert not added and len(reused) == 5
    assert set(first.loc[first.selected,'parcel_id']) == set(again.loc[again.selected,'parcel_id'])
    assert namespace['load_released_reserves'](reserves_path,again) == {reserve_id.upper()}
    namespace['save_field_outputs'](review,again,stage_dir,{reserve_id.upper()})
    assert (stage_dir/'selected_parcels.geojson').exists()
    assert not (stage_dir/'selected_parcels.gpkg').exists()
    assert not (stage_dir/'field_contact_log_removed_after_balance.csv').exists()
    assert not (stage_dir/'selected_parcels_map.html').exists()

    extra_parts, extra_clusters = [], []
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
    expanded, _, added, reused, _, _ = draw_fn(
        expanded_frame,expanded_clusters,base,1,8,20261120,{})
    assert len(added) == 2 and len(reused) == 5
    old = expanded.loc[expanded.cluster_id.isin(set(frame.cluster_id))]
    assert set(old.loc[old.selected,'parcel_id']) == set(first.loc[first.selected,'parcel_id'])
    assert namespace['load_released_reserves'](reserves_path,expanded) == {reserve_id.upper()}

    second, _, _, _, _, _ = draw_fn(
        expanded_frame,expanded_clusters,base,2,8,20261120,{},reserves_path)
    assert reserve_id not in set(second.parcel_id)
    assert set(expanded.loc[expanded.selected,'parcel_id']).isdisjoint(set(second.parcel_id))

    run = {'Path':Path,'pd':pd,'np':np,'gpd':gpd,'hashlib':hashlib,'json':json,
           'math':math,'PROJECT_ROOT':root,'display':lambda *_:None}
    exec(compile(''.join(notebook['cells'][3]['source']),'settings','exec'),run)
    run.update(OUTPUT_BASE=base/'notebook_run',
               CLUSTER_DRAW_CSV=base/'missing_cluster_draw.csv',
               STAGE1_RESERVES_CSV=base/'notebook_run/stage1/reserve_parcel_order.csv')
    for index in (4,5,7):
        exec(compile(''.join(notebook['cells'][index]['source']),f'cell {index}','exec'),run)
    assert run['draw'].selected.sum() == 78
    assert (run['stage_dir']/'reserve_parcel_order.csv').exists()
    assert not (run['stage_dir']/'sampling_manifest.json').exists()
    print('Compact incremental sampling passed')
