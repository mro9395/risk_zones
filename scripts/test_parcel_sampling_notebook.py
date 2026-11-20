"""Exercise the notebook's parcel frame and staged household draw."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json

import geopandas as gpd
import numpy as np
import pandas as pd

root=Path(__file__).resolve().parents[1]
notebook=json.loads((root/'parcel_household_sampling_colab.ipynb').read_text(encoding='utf-8'))
namespace={'Path':Path,'pd':pd,'np':np,'gpd':gpd,'display':lambda *_:None,
           'hashlib':__import__('hashlib'),'json':json,'math':__import__('math'),
           'datetime':__import__('datetime').datetime,'timezone':__import__('datetime').timezone,
           'BytesIO':__import__('io').BytesIO,'IN_COLAB':False,'PROJECT_ROOT':root}
with TemporaryDirectory() as folder:
    folder=Path(folder)
    cluster_file=folder/'cluster_draw.csv'
    pd.DataFrame({'cluster_id':['PER_100m_C00038','PER_100m_C00043'],
                  'selection_status':['primary','primary'],
                  'primary_inclusion_probability':[1.0,0.5]}).to_csv(cluster_file,index=False)
    for number in (3,4,6,8,9):
        if number==4:
            namespace.update(CLUSTER_DRAW_CSV=cluster_file,
                             EXPECTED_PRIMARY_CLUSTERS=2,OUTPUT_BASE=folder/'parcel_run',
                             OUTPUT_DIR=folder/'parcel_run/stage1',STAGE1_COMPLETED_TARGET=4,
                             STAGE2_ADDITIONAL_COMPLETED_TARGET=4,
                             PLANNING_RESPONSE_RATE=1.0,RUN_DRAW=True,FINAL_DRAW=False)
        source=''.join(notebook['cells'][number]['source'])
        exec(compile(source,f'cell {number}','exec'),namespace)
    assert len(namespace['draw'].loc[namespace['draw'].selected])==4
    assert namespace['draw'].household_draw_u.between(0,1,inclusive='left').all()
    assert (folder/'parcel_run/stage1/random_order_and_selection.csv').exists()
    assert (folder/'parcel_run/stage1/sampling_manifest.json').exists()
    first=set(namespace['draw'].loc[namespace['draw'].selected,'unit_id'])
    namespace.update(DRAW_STAGE=2,OUTPUT_DIR=folder/'parcel_run/stage2')
    for number in (8,9):
        source=''.join(notebook['cells'][number]['source'])
        exec(compile(source,f'extension cell {number}','exec'),namespace)
    second=set(namespace['draw'].loc[namespace['draw'].selected,'unit_id'])
    assert len(first)==len(second)==4 and first.isdisjoint(second)
    combined=pd.read_csv(folder/'parcel_run/stage2/combined_selected_stage1_stage2.csv')
    assert len(combined)==8
    print('Notebook parcel draws and nonoverlapping extension passed')
