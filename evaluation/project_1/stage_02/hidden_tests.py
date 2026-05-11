from __future__ import annotations

from decimal import Decimal

from evaluation.project_1.common import (
    assert_failure,
    assert_success,
    coerce_decimal,
    load_json_output,
)


def seed_transactions(project) -> None:
    transactions = [
        ("2024-01-01", "1000.00", "salary", "Jan paycheck"),
        ("2024-01-10", "-30.00", "food", "Groceries"),
        ("2024-01-31", "-20.00", "food", "Snack run"),
        ("2024-02-01", "1200.00", "Salary", "Feb paycheck"),
        ("2024-02-15", "-50.00", "rent", "February rent"),
        ("2024-02-29", "-15.00", "Food", "Late dinner"),
        ("2024-03-05", "200.00", "bonus", "Quarterly bonus"),
    ]
    for date, amount, category, description in transactions:
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
            )
        )


def test_stage_01_regression_add_and_list(project) -> None:
    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-01-05",
            "--amount",
            "-10.00",
            "--category",
            "misc",
            "--description",
            "carry-over",
        )
    )
    payload = load_json_output(project.run_cli("list", "--format", "json"))
    assert len(payload) == 1
    assert payload[0]["description"] == "carry-over"


def test_filter_by_category_is_case_insensitive(project) -> None:
    seed_transactions(project)
    payload = load_json_output(
        project.run_cli("list", "--category", "food", "--format", "json")
    )

    descriptions = {item["description"] for item in payload}
    assert descriptions == {"Groceries", "Snack run", "Late dinner"}
    assert all(item["category"].lower() == "food" for item in payload)


def test_filter_by_inclusive_date_range(project) -> None:
    seed_transactions(project)
    payload = load_json_output(
        project.run_cli(
            "list",
            "--from",
            "2024-02-01",
            "--to",
            "2024-02-29",
            "--format",
            "json",
        )
    )

    dates = [item["date"] for item in payload]
    assert dates == ["2024-02-01", "2024-02-15", "2024-02-29"]


def test_combined_filters_use_intersection_semantics(project) -> None:
    seed_transactions(project)
    payload = load_json_output(
        project.run_cli(
            "list",
            "--from",
            "2024-02-01",
            "--to",
            "2024-03-31",
            "--category",
            "food",
            "--format",
            "json",
        )
    )

    assert [item["description"] for item in payload] == ["Late dinner"]


def test_monthly_summary_aggregates_multiple_months(project) -> None:
    seed_transactions(project)
    payload = load_json_output(project.run_cli("summary", "--format", "json"))
    by_month = {item["month"]: item for item in payload}

    assert set(by_month) == {"2024-01", "2024-02", "2024-03"}
    assert coerce_decimal(by_month["2024-01"]["income_total"]) == Decimal("1000.00")
    assert coerce_decimal(by_month["2024-01"]["expense_total"]) == Decimal("50.00")
    assert coerce_decimal(by_month["2024-01"]["net_total"]) == Decimal("950.00")
    assert by_month["2024-01"]["transaction_count"] == 3

    assert coerce_decimal(by_month["2024-02"]["income_total"]) == Decimal("1200.00")
    assert coerce_decimal(by_month["2024-02"]["expense_total"]) == Decimal("65.00")
    assert coerce_decimal(by_month["2024-02"]["net_total"]) == Decimal("1135.00")
    assert by_month["2024-02"]["transaction_count"] == 3

    assert coerce_decimal(by_month["2024-03"]["income_total"]) == Decimal("200.00")
    assert coerce_decimal(by_month["2024-03"]["expense_total"]) == Decimal("0")


def test_filters_with_no_matches_return_empty_list(project) -> None:
    seed_transactions(project)
    payload = load_json_output(
        project.run_cli(
            "list",
            "--category",
            "transport",
            "--from",
            "2024-02-01",
            "--to",
            "2024-02-28",
            "--format",
            "json",
        )
    )
    assert payload == []


def test_invalid_filter_dates_are_rejected(project) -> None:
    seed_transactions(project)
    result = project.run_cli(
        "list",
        "--from",
        "2024-02-30",
        "--format",
        "json",
    )
    assert_failure(result)
