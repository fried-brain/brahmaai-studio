from fastapi.testclient import TestClient
from app.main import create_app


def setup():
    client=TestClient(create_app(database_url="sqlite://",create_tables=True))
    client.post('/api/v1/auth/register',json={'email':'furn@example.com','password':'StrongPass123!'})
    login=client.post('/api/v1/auth/login',json={'email':'furn@example.com','password':'StrongPass123!'})
    headers={'X-CSRF-Token':login.json()['csrf_token']}
    project=client.post('/api/v1/projects',headers=headers,json={'name':'Furniture test','plot':{'shape':'rectangle','width':30,'length':30,'unit':'ft'}}).json()
    return client,headers,project['id']


def room(name='Bedroom', furniture=None, include=True):
    data={'name':name,'room_type':'bedroom','vertices_mm':[{'x':0,'y':0},{'x':4000,'y':0},{'x':4000,'y':4000},{'x':0,'y':4000}]}
    if include: data['furniture']=furniture or []
    return data


def test_layout_persists_explicit_furniture_and_empty_array_clears():
    client,headers,pid=setup()
    item={'item_id':'bed-1','catalog_type':'bed_double','name':'Double bed','x_mm':2000,'y_mm':2000,'width_mm':1400,'depth_mm':2000,'rotation_deg':0}
    saved=client.put(f'/api/v1/projects/{pid}/layout',headers=headers,json={'floor_number':0,'rooms':[room(furniture=[item])]})
    assert saved.status_code==200 and saved.json()['rooms'][0]['furniture'][0]['item_id']=='bed-1'
    cleared=client.put(f'/api/v1/projects/{pid}/layout',headers=headers,json={'floor_number':0,'rooms':[room()]})
    assert cleared.status_code==200 and cleared.json()['rooms'][0]['furniture']==[]


def test_legacy_omitted_furniture_is_preserved_on_same_name_room():
    client,headers,pid=setup()
    item={'item_id':'bed-1','catalog_type':'bed_double','name':'Double bed','x_mm':2000,'y_mm':2000,'width_mm':1400,'depth_mm':2000,'rotation_deg':0}
    client.put(f'/api/v1/projects/{pid}/layout',headers=headers,json={'floor_number':0,'rooms':[room(furniture=[item])]})
    legacy=client.put(f'/api/v1/projects/{pid}/layout',headers=headers,json={'floor_number':0,'rooms':[room(include=False)]})
    assert legacy.status_code==200
    assert legacy.json()['rooms'][0]['furniture'][0]['item_id']=='bed-1'


def test_legacy_renamed_room_cannot_silently_discard_furniture():
    client,headers,pid=setup()
    item={'item_id':'bed-1','catalog_type':'bed_double','name':'Double bed','x_mm':2000,'y_mm':2000,'width_mm':1400,'depth_mm':2000,'rotation_deg':0}
    client.put(f'/api/v1/projects/{pid}/layout',headers=headers,json={'floor_number':0,'rooms':[room(furniture=[item])]})
    response=client.put(f'/api/v1/projects/{pid}/layout',headers=headers,json={'floor_number':0,'rooms':[room(name='Main bedroom',include=False)]})
    assert response.status_code==409
