from backend import app as auth_app
from backend.tests.conftest import register


def test_backup_and_restore_cli_round_trip(client, tmp_path, monkeypatch):
    register(client, "owner@example.test", "owner", "Home Owner")
    backup_path = tmp_path / "backup.sqlite3"
    runner = auth_app.app.test_cli_runner()

    result = runner.invoke(args=["backup", "--output", str(backup_path)])
    assert result.exit_code == 0, result.output
    assert backup_path.exists()

    with auth_app.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        db.execute("DELETE FROM users")

    result = runner.invoke(args=["restore", str(backup_path), "--yes"])
    assert result.exit_code == 0, result.output
    with auth_app.connect() as db:
        assert db.execute("SELECT name FROM users").fetchone()["name"] == "Home Owner"


def test_restore_rejects_a_file_that_is_not_sqlite(client, tmp_path):
    invalid = tmp_path / "not-a-database.sqlite3"
    invalid.write_text("this is not a SQLite database")
    result = auth_app.app.test_cli_runner().invoke(args=["restore", str(invalid), "--yes"])
    assert result.exit_code != 0
    assert "valid SQLite backup" in result.output
