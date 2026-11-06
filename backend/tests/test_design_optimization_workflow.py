from tests.test_design_optimization_api import setup


def test_layout_preview_edit_apply_get_round_trip_is_non_mutating_and_stale_safe():
    client, headers, project_id, room = setup()
    bed = {'item_id':'bed-1','catalog_type':'bed_double','name':'Double bed','x_mm':1800,'y_mm':1800,'width_mm':1400,'depth_mm':2000,'rotation_deg':0}
    saved = client.put(f'/api/v1/projects/{project_id}/layout', headers=headers, json={'floor_number':0,'rooms':[{**room,'furniture':[bed]}]})
    assert saved.status_code == 200
    before = client.get(f'/api/v1/projects/{project_id}/layout/0').json()
    preview_response = client.post(f'/api/v1/projects/{project_id}/design-optimization/preview', json={'floor_number':0,'operation':'full_review'})
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert len(preview['candidates']['Bedroom']['candidates']) >= 1
    assert client.get(f'/api/v1/projects/{project_id}/layout/0').json() == before
    candidate = preview['candidates']['Bedroom']['candidates'][0]
    edited = {**room, 'furniture': candidate['placements']}
    applied = client.post(f'/api/v1/projects/{project_id}/design-optimization/apply', headers=headers, json={'floor_number':0,'source_layout_fingerprint':preview['source_layout_fingerprint'],'rooms':[edited]})
    assert applied.status_code == 200
    after = client.get(f'/api/v1/projects/{project_id}/layout/0').json()
    assert after['rooms'][0]['furniture'] == candidate['placements']
    stale = client.post(f'/api/v1/projects/{project_id}/design-optimization/apply', headers=headers, json={'floor_number':0,'source_layout_fingerprint':preview['source_layout_fingerprint'],'rooms':[edited]})
    assert stale.status_code == 409
