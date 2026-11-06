from fastapi.testclient import TestClient
from app.main import create_app


def setup():
    client=TestClient(create_app(database_url='sqlite://',create_tables=True))
    client.post('/api/v1/auth/register',json={'email':'opt@example.com','password':'StrongPass123!'})
    login=client.post('/api/v1/auth/login',json={'email':'opt@example.com','password':'StrongPass123!'})
    headers={'X-CSRF-Token':login.json()['csrf_token']}
    project=client.post('/api/v1/projects',headers=headers,json={'name':'Optimization','plot':{'shape':'rectangle','width':30,'length':30,'unit':'ft'}}).json()
    pid=project['id']
    room={'name':'Bedroom','room_type':'bedroom','vertices_mm':[{'x':0,'y':0},{'x':4000,'y':0},{'x':4000,'y':4000},{'x':0,'y':4000}],'furniture':[]}
    assert client.put(f'/api/v1/projects/{pid}/layout',headers=headers,json={'floor_number':0,'rooms':[room]}).status_code==200
    return client,headers,pid,room


def test_preview_is_non_mutating_and_apply_requires_current_fingerprint():
    client,headers,pid,room=setup()
    preview=client.post(f'/api/v1/projects/{pid}/design-optimization/preview',json={'floor_number':0,'operation':'full_review'})
    assert preview.status_code==200
    fingerprint=preview.json()['source_layout_fingerprint']
    assert client.get(f'/api/v1/projects/{pid}/layout/0').json()['rooms'][0]['furniture']==[]
    edited={**room,'furniture':[{'item_id':'bed','catalog_type':'bed_double','name':'Bed','x_mm':2000,'y_mm':2000,'width_mm':1400,'depth_mm':2000,'rotation_deg':0}]}
    applied=client.post(f'/api/v1/projects/{pid}/design-optimization/apply',headers=headers,json={'floor_number':0,'source_layout_fingerprint':fingerprint,'rooms':[edited]})
    assert applied.status_code==200
    assert applied.json()['rooms'][0]['furniture'][0]['item_id']=='bed'


def test_preview_fingerprint_rejects_stale_apply_without_csrf_bypass():
    client,headers,pid,room=setup()
    preview=client.post(f'/api/v1/projects/{pid}/design-optimization/preview',json={'floor_number':0,'operation':'furniture_arrangement'}).json()
    client.put(f'/api/v1/projects/{pid}/layout',headers=headers,json={'floor_number':0,'rooms':[{**room,'name':'Intervening edit'}]})
    changed={**room,'name':'Bedroom'}
    response=client.post(f'/api/v1/projects/{pid}/design-optimization/apply',headers=headers,json={'floor_number':0,'source_layout_fingerprint':preview['source_layout_fingerprint'],'rooms':[changed]})
    assert response.status_code==409
    assert response.json()['detail']['code']=='optimization_preview_stale'


def test_apply_rejects_overlapping_furniture_and_missing_csrf():
    client,headers,pid,room=setup()
    preview=client.post(f'/api/v1/projects/{pid}/design-optimization/preview',json={'floor_number':0,'operation':'full_review'}).json()
    item={'item_id':'bed-a','catalog_type':'bed_double','name':'Bed A','x_mm':1800,'y_mm':1800,'width_mm':1400,'depth_mm':2000,'rotation_deg':0}
    duplicate={**item,'item_id':'bed-b','name':'Bed B'}
    bad={**room,'furniture':[item,duplicate]}
    response=client.post(f'/api/v1/projects/{pid}/design-optimization/apply',headers=headers,json={'floor_number':0,'source_layout_fingerprint':preview['source_layout_fingerprint'],'rooms':[bad]})
    assert response.status_code==422
    no_csrf=client.post(f'/api/v1/projects/{pid}/design-optimization/apply',json={'floor_number':0,'source_layout_fingerprint':preview['source_layout_fingerprint'],'rooms':[room]})
    assert no_csrf.status_code==403
