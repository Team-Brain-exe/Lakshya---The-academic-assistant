from pathlib import Path


def test_agent_state_tables_enable_row_level_security():
    migration = Path(__file__).resolve().parents[2] / "backend" / "migrations" / "005_agent_state.sql"
    sql = migration.read_text(encoding="utf-8").lower()

    assert "alter table agent_conversations enable row level security" in sql
    assert "alter table agent_proposals enable row level security" in sql
