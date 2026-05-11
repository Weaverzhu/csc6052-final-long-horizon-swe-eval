from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from evaluation.project_1.common import (
    assert_success,
    coerce_decimal,
    load_csv_rows,
    load_json_output,
)


def seed_sqlite_dataset(project, data_path: Path) -> None:
    for date, amount, category, description in (
        ("2024-03-01", "2000.00", "salary", "March salary"),
        ("2024-03-02", "-40.00", "food", "Groceries"),
        ("2024-03-03", "-15.00", "food", "Coffee, beans"),
        ("2024-03-04", "-900.00", "rent", "March rent"),
        ("2024-04-01", "2000.00", "salary", "April salary"),
    ):
        assert_success(
            project.run_cli(
                "add",
                "--date",
                date,
                "--amount",
                amount,
                "--category",
                category,
                "--description",
                description,
                "--data",
                str(data_path),
            )
        )


def test_export_writes_filtered_subset_with_expected_header(project, tmp_path) -> None:
    db_path = tmp_path / "finance.db"
    output_path = tmp_path / "export.csv"
    seed_sqlite_dataset(project, db_path)

    assert_success(
        project.run_cli(
            "export",
            "--output",
            str(output_path),
            "--category",
            "food",
            "--from",
            "2024-03-01",
            "--to",
            "2024-03-31",
            "--data",
            str(db_path),
        )
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "date,amount,category,description"
    rows = load_csv_rows(output_path)
    assert len(rows) == 2
    assert {row["description"] for row in rows} == {"Groceries", "Coffee, beans"}


def test_export_escapes_commas_in_description(project, tmp_path) -> None:
    db_path = tmp_path / "commas.db"
    output_path = tmp_path / "commas.csv"
    seed_sqlite_dataset(project, db_path)

    assert_success(
        project.run_cli(
            "export",
            "--output",
            str(output_path),
            "--category",
            "food",
            "--data",
            str(db_path),
        )
    )

    csv_text = output_path.read_text(encoding="utf-8")
    assert '"Coffee, beans"' in csv_text


def test_monthly_category_report_returns_correct_totals(project, tmp_path) -> None:
    db_path = tmp_path / "report.db"
    seed_sqlite_dataset(project, db_path)

    payload = load_json_output(
        project.run_cli("report", "--month", "2024-03", "--format", "json", "--data", str(db_path))
    )
    by_category = {item["category"]: item for item in payload}

    assert set(by_category) == {"salary", "food", "rent"}
    assert coerce_decimal(by_category["salary"]["income_total"]) == Decimal("2000.00")
    assert coerce_decimal(by_category["salary"]["expense_total"]) == Decimal("0")
    assert by_category["salary"]["transaction_count"] == 1

    assert coerce_decimal(by_category["food"]["income_total"]) == Decimal("0")
    assert coerce_decimal(by_category["food"]["expense_total"]) == Decimal("55.00")
    assert coerce_decimal(by_category["food"]["net_total"]) == Decimal("-55.00")
    assert by_category["food"]["transaction_count"] == 2


def test_report_for_empty_month_returns_empty_list(project, tmp_path) -> None:
    db_path = tmp_path / "empty_report.db"
    seed_sqlite_dataset(project, db_path)
    payload = load_json_output(
        project.run_cli("report", "--month", "2024-05", "--format", "json", "--data", str(db_path))
    )
    assert payload == []


def test_export_with_no_matches_creates_header_only_and_does_not_modify_data(project, tmp_path) -> None:
    db_path = tmp_path / "stable.db"
    output_path = tmp_path / "empty_export.csv"
    seed_sqlite_dataset(project, db_path)

    before = load_json_output(project.run_cli("list", "--format", "json", "--data", str(db_path)))

    assert_success(
        project.run_cli(
            "export",
            "--output",
            str(output_path),
            "--category",
            "travel",
            "--data",
            str(db_path),
        )
    )

    assert output_path.read_text(encoding="utf-8").splitlines() == [
        "date,amount,category,description"
    ]
    after = load_json_output(project.run_cli("list", "--format", "json", "--data", str(db_path)))
    assert before == after


def test_representative_stage_01_to_stage_05_regressions_still_pass(project, tmp_path) -> None:
    db_path = tmp_path / "regression.db"
    seed_sqlite_dataset(project, db_path)

    assert_success(
        project.run_cli(
            "budget",
            "set",
            "--month",
            "2024-03",
            "--category",
            "food",
            "--limit",
            "60.00",
            "--data",
            str(db_path),
        )
    )

    list_payload = load_json_output(
        project.run_cli("list", "--category", "food", "--format", "json", "--data", str(db_path))
    )
    assert [item["description"] for item in list_payload] == ["Groceries", "Coffee, beans"]

    summary_payload = load_json_output(
        project.run_cli("summary", "--format", "json", "--data", str(db_path))
    )
    by_month = {item["month"]: item for item in summary_payload}
    assert coerce_decimal(by_month["2024-03"]["expense_total"]) == Decimal("955.00")

    budget_payload = load_json_output(
        project.run_cli(
            "budget",
            "check",
            "--month",
            "2024-03",
            "--format",
            "json",
            "--data",
            str(db_path),
        )
    )
    assert budget_payload[0]["status"] == "warning"


def test_default_sqlite_backend_still_works_without_data_flag(project) -> None:
    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-05-01",
            "--amount",
            "15.00",
            "--category",
            "misc",
            "--description",
            "default db",
        )
    )

    default_path = project.root / "finance_data.db"
    assert default_path.exists()
    payload = load_json_output(project.run_cli("list", "--format", "json"))
    assert [item["description"] for item in payload] == ["default db"]
