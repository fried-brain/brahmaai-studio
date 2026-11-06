import sqlite3
from alembic import command
from alembic.config import Config


def test_room_furniture_migration_backfills_existing_rows_and_downgrades(tmp_path):
    db_path = tmp_path / 'migration.sqlite'
    config = Config('alembic.ini')
    config.set_main_option('sqlalchemy.url', f'sqlite:///{db_path}')
    command.upgrade(config, '0007_assistant_proposals')
    connection = sqlite3.connect(db_path)
    connection.execute("INSERT INTO users (id,email,password_hash,created_at,is_active) VALUES ('u1','migration@example.com','hash','2026-01-01',1)")
    connection.execute("INSERT INTO projects (id,owner_id,name,created_at,updated_at) VALUES ('p1','u1','Migration','2026-01-01','2026-01-01')")
    connection.execute("INSERT INTO rooms (id,project_id,floor_number,name,room_type,geometry_json,wall_thickness_mm,openings_json) VALUES ('r1','p1',0,'Bedroom','bedroom','[]',150,'[]')")
    connection.commit(); connection.close()
    command.upgrade(config, 'head')
    connection = sqlite3.connect(db_path)
    assert connection.execute("SELECT furniture_json FROM rooms WHERE id='r1'").fetchone()[0] == '[]'
    connection.close()
    command.downgrade(config, '0007_assistant_proposals')
    connection = sqlite3.connect(db_path)
    columns = {row[1] for row in connection.execute('PRAGMA table_info(rooms)')}
    assert 'furniture_json' not in columns
    assert connection.execute("SELECT name FROM rooms WHERE id='r1'").fetchone()[0] == 'Bedroom'
    connection.close()
