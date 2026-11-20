"""Helpers embedded in the standalone parcel-to-household sampling notebook."""

def load_parcel_frame(review_path, boundary_band_m):
    review = gpd.read_file(review_path, layer='parcel_review', fid_as_index=True)
    clusters = gpd.read_file(review_path, layer='study_clusters').set_index('cluster_id')
    if review.crs != clusters.crs or review.crs.to_epsg() != 32614:
        raise ValueError('Parcel and cluster layers must use EPSG:32614.')
    if review.parcel_id.isna().any() or review.parcel_id.str.upper().duplicated().any():
        raise ValueError('Parcel IDs must be present and unique, ignoring letter case.')
    if review.geometry.isna().any() or not review.geometry.is_valid.all():
        raise ValueError('Parcel geometries must be present and valid.')
    if review.cluster_id.isna().any() or not set(review.cluster_id).issubset(clusters.index):
        raise ValueError('A parcel has no matching study cluster.')
    if review.boundary_side.isna().any() or not set(review.boundary_side).issubset({'inside','outside'}):
        raise ValueError('Every parcel needs an inside/outside side.')
    review['boundary_distance_m'] = [row.geometry.representative_point().distance(
        clusters.loc[row.cluster_id].geometry.boundary) for _,row in review.iterrows()]
    frame = review.loc[review.boundary_distance_m.le(boundary_band_m) &
                       review.review_status.ne('deleted')].copy()
    if frame.empty:
        raise ValueError('No parcels are within the boundary band.')
    return review, clusters, frame


def read_primary_clusters(path, expected):
    if not path.exists():
        return None, {}
    table = pd.read_csv(path, dtype={'cluster_id':str})
    required = {'cluster_id','selection_status','primary_inclusion_probability'}
    if not required <= set(table) or table.cluster_id.duplicated().any():
        raise ValueError('Cluster draw CSV is missing fields or has duplicate IDs.')
    primary = table.loc[table.selection_status.eq('primary')].copy()
    if len(primary) < 1 or len(primary) > expected:
        raise ValueError(f'Expected 1–{expected} primary clusters; found {len(primary)}.')
    if len(primary) != expected:
        print(f'Cluster draw CSV currently lists {len(primary)} of {expected} primary clusters.')
    primary['primary_inclusion_probability'] = pd.to_numeric(
        primary.primary_inclusion_probability, errors='coerce')
    if not primary.primary_inclusion_probability.dropna().between(0,1,inclusive='right').all():
        raise ValueError('Invalid primary cluster inclusion probability.')
    known = primary.dropna(subset=['primary_inclusion_probability'])
    return set(primary.cluster_id), dict(zip(known.cluster_id,
                                             known.primary_inclusion_probability))


def stratum_seed(master, stage, cluster_id, side):
    raw = f'{master}|{stage}|{cluster_id}|{side}'.encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], 'big')


def cluster_frame_hash(cluster_frame, cluster_geometry):
    rows = [(str(r.parcel_id).upper(), r.boundary_side, r.geometry.wkb_hex)
            for r in cluster_frame.sort_values('parcel_id').itertuples()]
    payload = json.dumps({'cluster_geometry':cluster_geometry.wkb_hex,'parcels':rows},
                         separators=(',',':'))
    return hashlib.sha256(payload.encode()).hexdigest()


def load_released_reserves(path, prior):
    if path is None:
        raise ValueError('For Stage 2, supply released Stage 1 reserve IDs; a header-only CSV means none.')
    released = pd.read_csv(path, dtype=str)
    if 'parcel_id' not in released or released.parcel_id.isna().any() or released.parcel_id.duplicated().any():
        raise ValueError('Released reserve CSV needs unique, nonempty parcel_id values.')
    released_ids = set(released.parcel_id.str.upper())
    prior_selected = prior.selected.astype(str).str.lower().eq('true')
    reserve_ids = set(prior.loc[~prior_selected,'parcel_id'].str.upper())
    if not released_ids <= reserve_ids:
        raise ValueError('A released reserve is absent from the frozen Stage 1 reserve list.')
    return released_ids


def draw_one_cluster(cluster_frame, cluster_id, stage, quota_per_side, seed,
                     full_counts, primary_probability):
    rows = []
    balanced_quota = min(quota_per_side,
                         int(cluster_frame.boundary_side.eq('inside').sum()),
                         int(cluster_frame.boundary_side.eq('outside').sum()))
    for side in ('inside','outside'):
        group = cluster_frame.loc[cluster_frame.boundary_side.eq(side)].sort_values('parcel_id').copy()
        if group.empty:
            continue
        rng = np.random.default_rng(stratum_seed(seed, stage, cluster_id, side))
        quota = balanced_quota
        group['random_order'] = rng.permutation(len(group)) + 1
        group['household_draw_u'] = rng.random(len(group))
        group['selected'] = group.random_order.le(quota)
        group['planned_quota'] = quota_per_side
        group['selected_quota'] = quota
        group['capacity_shortfall'] = quota_per_side - quota
        group['within_stage_probability'] = quota / len(group)
        group['primary_cluster_probability'] = primary_probability
        if stage == 1:
            group['overall_inclusion_probability'] = primary_probability * quota / full_counts[side]
        else:
            group['overall_inclusion_probability'] = np.nan
        group['draw_stage'] = stage
        rows.append(group.drop(columns='geometry'))
    return pd.concat(rows, ignore_index=True)


def migrate_existing_draw(frame, clusters, stage_dir, frozen_dir, stage,
                          quota_per_side, seed):
    legacy_path = stage_dir / 'random_order_and_selection.csv'
    if not legacy_path.exists() or list(frozen_dir.glob('*.json')):
        return []
    old = pd.read_csv(legacy_path, dtype={'parcel_id':str,'cluster_id':str})
    required = {'parcel_id','cluster_id','boundary_side','random_order',
                'household_draw_u','selected'}
    if not required <= set(old) or old.parcel_id.duplicated().any():
        raise ValueError('Existing draw cannot be migrated safely; review its columns and IDs.')
    migrated = []
    for cluster_id in sorted(old.cluster_id.unique()):
        full = frame.loc[frame.cluster_id.eq(cluster_id)]
        part = old.loc[old.cluster_id.eq(cluster_id)].copy()
        if full.empty or set(part.parcel_id.str.upper()) != set(full.parcel_id.str.upper()):
            raise ValueError(f'{cluster_id} differs from the existing draw; no old selection was replaced.')
        if part.household_draw_u.isna().any():
            raise ValueError(f'{cluster_id} has no saved household random values.')
        balanced_quota = min(quota_per_side,
                             int(full.boundary_side.eq('inside').sum()),
                             int(full.boundary_side.eq('outside').sum()))
        part['selected'] = pd.to_numeric(part.random_order).le(balanced_quota)
        part['planned_quota'] = quota_per_side
        part['selected_quota'] = 0
        part['capacity_shortfall'] = 0
        part['within_stage_probability'] = np.nan
        for side in ('inside','outside'):
            mask = part.boundary_side.eq(side)
            selected_n = int(part.loc[mask,'selected'].sum())
            part.loc[mask,'selected_quota'] = selected_n
            part.loc[mask,'capacity_shortfall'] = max(0,quota_per_side-selected_n)
            part.loc[mask,'within_stage_probability'] = selected_n / max(1,int(mask.sum()))
        part['primary_cluster_probability'] = np.nan
        part['overall_inclusion_probability'] = np.nan
        part['draw_stage'] = stage
        safe_id = cluster_id.replace('/','_').replace('\\','_')
        part.to_csv(frozen_dir/f'{safe_id}.csv',index=False)
        meta = {'cluster_id':cluster_id,'stage':stage,
                'frame_hash':cluster_frame_hash(full,clusters.loc[cluster_id].geometry),
                'quota_per_side':quota_per_side,'random_seed':seed,
                'released_stage1_reserves':[],
                'allocation_rule':'equal_inside_outside_within_cluster',
                'migrated_from_prior_draw':True}
        (frozen_dir/f'{safe_id}.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
        migrated.append(cluster_id)
    manifest_path = stage_dir/'sampling_manifest.json'
    if manifest_path.exists():
        manifest_path.rename(stage_dir/'sampling_manifest_before_incremental_migration.json')
    return migrated


def incremental_draw(frame, clusters, output_base, stage, quota_per_side, seed,
                     primary_probabilities, released_file=None):
    stage_dir = output_base / f'stage{stage}'
    frozen_dir = stage_dir / 'frozen_clusters'
    frozen_dir.mkdir(parents=True, exist_ok=True)
    migrated = migrate_existing_draw(frame,clusters,stage_dir,frozen_dir,stage,
                                     quota_per_side,seed)
    prior = None
    released_ids = set()
    if stage == 2:
        prior_path = output_base / 'stage1' / 'random_order_and_selection.csv'
        if not prior_path.exists():
            raise ValueError('Stage 1 must be saved before Stage 2.')
        prior = pd.read_csv(prior_path, dtype={'parcel_id':str,'cluster_id':str})
        released_ids = load_released_reserves(released_file, prior)
    all_parts = []
    added = []
    reused = []
    rebalanced = []
    for cluster_id in sorted(frame.cluster_id.unique()):
        full = frame.loc[frame.cluster_id.eq(cluster_id)].copy()
        frame_hash = cluster_frame_hash(full, clusters.loc[cluster_id].geometry)
        full_counts = {side:int(full.boundary_side.eq(side).sum()) for side in ('inside','outside')}
        available = full.copy()
        if stage == 2:
            old = prior.loc[prior.cluster_id.eq(cluster_id)]
            if old.empty:
                raise ValueError(f'Complete Stage 1 for {cluster_id} before Stage 2.')
            used = set(old.loc[old.selected.astype(str).str.lower().eq('true'),'parcel_id'].str.upper())
            used |= released_ids
            available = available.loc[~available.parcel_id.str.upper().isin(used)].copy()
        safe_id = cluster_id.replace('/','_').replace('\\','_')
        csv_path = frozen_dir / f'{safe_id}.csv'
        meta_path = frozen_dir / f'{safe_id}.json'
        released_here = sorted(set(full.parcel_id.str.upper()) & released_ids)
        expected = {'cluster_id':cluster_id,'stage':stage,'frame_hash':frame_hash,
                    'quota_per_side':quota_per_side,'random_seed':seed,
                    'released_stage1_reserves':released_here,
                    'allocation_rule':'equal_inside_outside_within_cluster'}
        if csv_path.exists() != meta_path.exists():
            raise ValueError(f'Incomplete frozen draw for {cluster_id}.')
        if csv_path.exists():
            saved = json.loads(meta_path.read_text(encoding='utf-8'))
            if any(saved.get(key) != value for key,value in expected.items()
                   if key != 'allocation_rule'):
                raise ValueError(f'{cluster_id} changed after its draw; prior selections were kept. Review the frame.')
            part = pd.read_csv(csv_path, dtype={'parcel_id':str,'cluster_id':str})
            if set(part.parcel_id.str.upper()) != set(available.parcel_id.str.upper()):
                raise ValueError(f'{cluster_id} frozen draw does not match its available frame.')
            if saved.get('allocation_rule') != expected['allocation_rule']:
                balanced_quota = min(quota_per_side,
                                     int(available.boundary_side.eq('inside').sum()),
                                     int(available.boundary_side.eq('outside').sum()))
                old_selected = part.selected.astype(str).str.lower().eq('true')
                new_selected = pd.to_numeric(part.random_order).le(balanced_quota)
                if not old_selected.equals(new_selected):
                    backup_dir = stage_dir/'previous_draws'
                    backup_dir.mkdir(exist_ok=True)
                    backup_csv = backup_dir/f'{safe_id}_before_balance.csv'
                    backup_meta = backup_dir/f'{safe_id}_before_balance.json'
                    if not backup_csv.exists():
                        backup_csv.write_bytes(csv_path.read_bytes())
                        backup_meta.write_bytes(meta_path.read_bytes())
                    rebalanced.append(cluster_id)
                part['selected'] = new_selected
                part['planned_quota'] = quota_per_side
                part['selected_quota'] = balanced_quota
                part['capacity_shortfall'] = quota_per_side-balanced_quota
                for side in ('inside','outside'):
                    mask = part.boundary_side.eq(side)
                    if mask.any():
                        part.loc[mask,'within_stage_probability'] = balanced_quota/int(mask.sum())
                part.to_csv(csv_path,index=False)
                saved.update(expected)
                meta_path.write_text(json.dumps(saved,indent=2),encoding='utf-8')
            reused.append(cluster_id)
        else:
            part = draw_one_cluster(available, cluster_id, stage, quota_per_side, seed,
                                    full_counts, primary_probabilities.get(cluster_id, np.nan))
            part.to_csv(csv_path, index=False)
            meta_path.write_text(json.dumps(expected,indent=2),encoding='utf-8')
            added.append(cluster_id)
        part['primary_cluster_probability'] = primary_probabilities.get(cluster_id,np.nan)
        if stage == 1:
            for side in ('inside','outside'):
                mask = part.boundary_side.eq(side)
                if mask.any():
                    selected = int(part.loc[mask,'selected'].astype(str).str.lower().eq('true').sum())
                    part.loc[mask,'overall_inclusion_probability'] = (
                        primary_probabilities.get(cluster_id,np.nan) * selected / full_counts[side])
        all_parts.append(part)
    draw = pd.concat(all_parts, ignore_index=True)
    draw['selected'] = draw.selected.astype(str).str.lower().eq('true')
    draw.to_csv(stage_dir / 'random_order_and_selection.csv', index=False)
    reserves = draw.loc[~draw.selected].sort_values(['cluster_id','boundary_side','random_order']).copy()
    reserves['reserve_rank'] = reserves.random_order - reserves.selected_quota
    reserves.to_csv(stage_dir / 'reserve_parcel_order.csv', index=False)
    return draw, stage_dir, added, reused, migrated, rebalanced


def cluster_summary(review, frame, draw, quota_per_side, primary_ids):
    rows = []
    for cluster_id in sorted(review.cluster_id.unique()):
        subset = frame.loc[frame.cluster_id.eq(cluster_id)]
        drawn = draw.loc[draw.cluster_id.eq(cluster_id)] if draw is not None else pd.DataFrame()
        row = {'cluster_id':cluster_id,
               'listed_parcels':int(review.cluster_id.eq(cluster_id).sum()),
               'within_20m':len(subset),
               'primary_draw':('unknown' if primary_ids is None else
                               'yes' if cluster_id in primary_ids else 'no')}
        for side in ('inside','outside'):
            n = int(subset.boundary_side.eq(side).sum())
            selected = (int((drawn.boundary_side.eq(side) & drawn.selected).sum())
                        if len(drawn) else 0)
            row[f'{side}_frame'] = n
            row[f'{side}_selected'] = selected
            row[f'{side}_reserves'] = max(0,n-selected)
            row[f'{side}_shortfall'] = max(0,quota_per_side-selected)
        rows.append(row)
    return pd.DataFrame(rows)


def save_field_outputs(review, draw, stage_dir, released_ids=None):
    released_ids = set(released_ids or [])
    contact_path = stage_dir / 'field_contact_log_template.csv'
    fielded = draw.loc[draw.selected | draw.parcel_id.str.upper().isin(released_ids)].copy()
    fielded['release_type'] = np.where(fielded.selected,'initial','reserve')
    columns = ['parcel_id','cluster_id','boundary_side','random_order','household_draw_u','release_type',
               'eligible_households_count','chosen_household_number','chosen_household_id',
               'eligibility','contact_attempts','contact_outcome','survey_id']
    contact = fielded[columns[:6]].copy()
    for name in columns[6:]:
        contact[name] = ''
    if contact_path.exists():
        previous = pd.read_csv(contact_path,dtype=str)
        removed = previous.loc[~previous.parcel_id.isin(contact.parcel_id)].copy()
        if len(removed):
            retired_path = stage_dir/'field_contact_log_removed_after_balance.csv'
            if retired_path.exists():
                removed = pd.concat([pd.read_csv(retired_path,dtype=str),removed],ignore_index=True)
                removed = removed.drop_duplicates('parcel_id',keep='first')
            removed.to_csv(retired_path,index=False)
        previous = previous.loc[previous.parcel_id.isin(contact.parcel_id)].copy()
        editable = columns[6:]
        contact = contact.set_index('parcel_id')
        previous = previous.set_index('parcel_id')
        for name in editable:
            if name in previous:
                contact.loc[previous.index,name] = previous[name].fillna('')
        contact = contact.reset_index()
    contact.to_csv(contact_path,index=False)
    fielded_ids = set(fielded.parcel_id)
    selected_geo = review.loc[review.parcel_id.isin(fielded_ids)].copy()
    selected_geo.to_file(stage_dir / 'selected_parcels.gpkg',layer='selected_parcels',driver='GPKG')
    selected_geo.to_crs(4326).to_file(stage_dir / 'selected_parcels.geojson',driver='GeoJSON')


def show_sample_map(review, clusters, draw, stage_dir, released_ids=None):
    selected_ids = set(draw.loc[draw.selected,'parcel_id'])
    released_ids = set(released_ids or [])
    shown = review.loc[review.parcel_id.isin(set(draw.parcel_id))].copy().to_crs(4326)
    if shown.empty:
        return None
    centre = shown.unary_union.centroid
    sample_map = folium.Map(location=[centre.y,centre.x],zoom_start=12,tiles=None)
    folium.TileLayer('OpenStreetMap',name='OpenStreetMap',show=True).add_to(sample_map)
    outlines = shown[['parcel_id','cluster_id','boundary_side','geometry']]
    folium.GeoJson(outlines.to_json(),name='Parcel frame',show=False,
                   style_function=lambda _: {'color':'#777777','weight':1,'fillOpacity':0},
                   tooltip=folium.GeoJsonTooltip(fields=['parcel_id','cluster_id','boundary_side'])).add_to(sample_map)
    for side,color in [('inside','#c62828'),('outside','#1565c0')]:
        polygons = shown.loc[shown.parcel_id.isin(selected_ids) & shown.boundary_side.eq(side),
                             ['parcel_id','cluster_id','boundary_side','geometry']]
        if len(polygons):
            folium.GeoJson(polygons.to_json(),name=f'Selected {side}',
                           style_function=lambda _,color=color: {'color':color,'weight':2,'fillOpacity':0.25},
                           tooltip=folium.GeoJsonTooltip(fields=['parcel_id','cluster_id'])).add_to(sample_map)
    released = shown.loc[shown.parcel_id.str.upper().isin(released_ids),
                         ['parcel_id','cluster_id','boundary_side','geometry']]
    if len(released):
        folium.GeoJson(released.to_json(),name='Released reserves',
                       style_function=lambda _: {'color':'#ef6c00','weight':2,'fillOpacity':0.3},
                       tooltip=folium.GeoJsonTooltip(fields=['parcel_id','cluster_id'])).add_to(sample_map)
    cluster_shapes = clusters.loc[clusters.index.isin(set(shown.cluster_id))].reset_index().to_crs(4326)
    folium.GeoJson(cluster_shapes[['cluster_id','geometry']].to_json(),name='Risk clusters',
                   style_function=lambda _: {'color':'#2e7d32','weight':2,'fillOpacity':0},
                   tooltip=folium.GeoJsonTooltip(fields=['cluster_id'])).add_to(sample_map)
    folium.LayerControl(collapsed=False).add_to(sample_map)
    sample_map.save(str(stage_dir / 'selected_parcels_map.html'))
    return sample_map
