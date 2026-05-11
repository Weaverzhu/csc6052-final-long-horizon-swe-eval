from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from importlib.resources import as_file, files
from pathlib import Path

from evaluation.project_1.common import (
    assert_failure,
    assert_success,
    coerce_decimal,
    load_json_output,
)


@contextmanager
def legacy_fixture_path():
    fixture = files("evaluation.project_1.fixtures").joinpath("legacy_finance_data.json")
    with as_file(fixture) as path:
        yield path


def test_migrate_imports_fixture_into_sqlite(project, tmp_path) -> None:
    db_path = tmp_path / "finance.db"
    with legacy_fixture_path() as fixture_path:
        assert_success(
            project.run_cli(
                "migrate",
                "--from-json",
                str(fixture_path),
                "--data",
                str(db_path),
            )
        )

    payload = load_json_output(
        project.run_cli("list", "--format", "json", "--data", str(db_path))
    )
    assert len(payload) == 7
    assert db_path.exists()


def test_migrated_database_returns_expected_list_and_summary(project, tmp_path) -> None:
    db_path = tmp_path / "summary.db"
    with legacy_fixture_path() as fixture_path:
        assert_success(
            project.run_cli(
                "migrate",
                "--from-json",
                str(fixture_path),
                "--data",
                str(db_path),
            )
        )

    list_payload = load_json_output(
        project.run_cli("list", "--format", "json", "--data", str(db_path))
    )
    descriptions = [item["description"] for item in list_payload]
    assert descriptions[:4] == [
        "January salary",
        "Groceries",
        "Coffee beans",
        "January rent",
    ]

    summary_payload = load_json_output(
        project.run_cli("summary", "--format", "json", "--data", str(db_path))
    )
    by_month = {item["month"]: item for item in summary_payload}
    assert coerce_decimal(by_month["2024-01"]["income_total"]) == Decimal("2500.00")
    assert coerce_decimal(by_month["2024-01"]["expense_total"]) == Decimal("860.50")
    assert coerce_decimal(by_month["2024-02"]["expense_total"]) == Decimal("960.00")


def test_migrated_budgets_drive_budget_check(project, tmp_path) -> None:
    db_path = tmp_path / "budget.db"
    with legacy_fixture_path() as fixture_path:
        assert_success(
            project.run_cli(
                "migrate",
                "--from-json",
                str(fixture_path),
                "--data",
                str(db_path),
            )
        )

    payload = load_json_output(
        project.run_cli(
            "budget",
            "check",
            "--month",
            "2024-01",
            "--format",
            "json",
            "--data",
            str(db_path),
        )
    )
    by_category = {item["category"]: item for item in payload}
    assert by_category["food"]["status"] == "exceeded"
    assert coerce_decimal(by_category["rent"]["spent"]) == Decimal("800.00")
    assert coerce_decimal(by_category["rent"]["usage_ratio"]) == Decimal("800.00") / Decimal(
        "850.00"
    )
    assert by_category["rent"]["status"] == "warning"


def test_add_after_migration_persists_into_sqlite(project, tmp_path) -> None:
    db_path = tmp_path / "append.db"
    with legacy_fixture_path() as fixture_path:
        assert_success(
            project.run_cli(
                "migrate",
                "--from-json",
                str(fixture_path),
                "--data",
                str(db_path),
            )
        )
    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-02-20",
            "--amount",
            "-25.00",
            "--category",
            "food",
            "--description",
            "Post migration meal",
            "--data",
            str(db_path),
        )
    )

    payload = load_json_output(
        project.run_cli("list", "--category", "food", "--format", "json", "--data", str(db_path))
    )
    assert any(item["description"] == "Post migration meal" for item in payload)


def test_rerunning_migration_fails_cleanly_without_changing_records(project, tmp_path) -> None:
    db_path = tmp_path / "idempotent.db"
    with legacy_fixture_path() as fixture_path:
        assert_success(
            project.run_cli(
                "migrate",
                "--from-json",
                str(fixture_path),
                "--data",
                str(db_path),
            )
        )
    first_payload = load_json_output(
        project.run_cli("list", "--format", "json", "--data", str(db_path))
    )
    first_budgets = load_json_output(
        project.run_cli(
            "budget",
            "list",
            "--month",
            "2024-01",
            "--format",
            "json",
            "--data",
            str(db_path),
        )
    )

    with legacy_fixture_path() as fixture_path:
        rerun_result = project.run_cli(
            "migrate",
            "--from-json",
            str(fixture_path),
            "--data",
            str(db_path),
        )
    assert_failure(rerun_result)
    second_payload = load_json_output(
        project.run_cli("list", "--format", "json", "--data", str(db_path))
    )
    second_budgets = load_json_output(
        project.run_cli(
            "budget",
            "list",
            "--month",
            "2024-01",
            "--format",
            "json",
            "--data",
            str(db_path),
        )
    )

    assert first_payload == second_payload
    assert first_budgets == second_budgets
    assert len(first_payload) == 7


def test_resulting_database_is_a_valid_sqlite_file(project, tmp_path) -> None:
    db_path = tmp_path / "schema.db"
    with legacy_fixture_path() as fixture_path:
        assert_success(
            project.run_cli(
                "migrate",
                "--from-json",
                str(fixture_path),
                "--data",
                str(db_path),
            )
        )

    connection = sqlite3.connect(db_path)
    try:
        schema_version = connection.execute("PRAGMA schema_version").fetchone()
        user_tables = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()
    finally:
        connection.close()

    assert schema_version is not None
    assert isinstance(schema_version[0], int)
    assert user_tables is not None
    assert user_tables[0] >= 1


def test_missing_legacy_json_fails_cleanly(project, tmp_path) -> None:
    db_path = tmp_path / "missing.db"
    result = project.run_cli(
        "migrate",
        "--from-json",
        str(tmp_path / "does-not-exist.json"),
        "--data",
        str(db_path),
    )
    assert_failure(result)


def test_empty_legacy_dataset_migrates_successfully(project, tmp_path) -> None:
    empty_json = tmp_path / "empty.json"
    empty_json.write_text('{"transactions": [], "budgets": []}', encoding="utf-8")
    db_path = tmp_path / "empty.db"

    assert_success(
        project.run_cli("migrate", "--from-json", str(empty_json), "--data", str(db_path))
    )
    assert load_json_output(
        project.run_cli("list", "--format", "json", "--data", str(db_path))
    ) == []


def test_default_backend_path_uses_sqlite_after_stage_five(project) -> None:
    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-03-01",
            "--amount",
            "10.00",
            "--category",
            "misc",
            "--description",
            "default sqlite",
        )
    )

    default_path = project.root / "finance_data.db"
    assert default_path.exists()
    payload = load_json_output(project.run_cli("list", "--format", "json"))
    assert [item["description"] for item in payload] == ["default sqlite"]

    connection = sqlite3.connect(default_path)
    try:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'"
        ).fetchall()
    finally:
        connection.close()
    assert tables == [("transactions",)]


def test_same_day_order_is_preserved_after_migration(project, tmp_path) -> None:
    db_path = tmp_path / "ordering.db"
    with legacy_fixture_path() as fixture_path:
        assert_success(
            project.run_cli(
                "migrate",
                "--from-json",
                str(fixture_path),
                "--data",
                str(db_path),
            )
        )

    payload = load_json_output(
        project.run_cli("list", "--format", "json", "--data", str(db_path))
    )
    jan_tenth = [item["description"] for item in payload if item["date"] == "2024-01-10"]
    assert jan_tenth == ["Groceries", "Coffee beans"]
