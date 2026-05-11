from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from evaluation.project_1.common import assert_success, coerce_decimal, load_json_output


def seed_budget_dataset(project, data_path: Path) -> None:
    for date, amount, category, description in (
        ("2024-02-05", "-30.00", "food", "Groceries"),
        ("2024-02-11", "-20.00", "food", "Takeout"),
        ("2024-02-18", "150.00", "food", "Reimbursement"),
        ("2024-02-20", "-70.00", "rent", "Rent top-up"),
        ("2024-03-01", "-10.00", "food", "March snack"),
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


def test_stage_03_regression_custom_data_path_still_works(project, tmp_path) -> None:
    data_path = tmp_path / "ledger.json"
    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-03-02",
            "--amount",
            "25.00",
            "--category",
            "gift",
            "--description",
            "refund",
            "--data",
            str(data_path),
        )
    )
    payload = load_json_output(
        project.run_cli("list", "--format", "json", "--data", str(data_path))
    )
    assert [item["description"] for item in payload] == ["refund"]


def test_budget_set_and_list_returns_saved_budget(project, tmp_path) -> None:
    data_path = tmp_path / "budget_data.json"
    assert_success(
        project.run_cli(
            "budget",
            "set",
            "--month",
            "2024-02",
            "--category",
            "food",
            "--limit",
            "100.00",
            "--data",
            str(data_path),
        )
    )

    payload = load_json_output(
        project.run_cli(
            "budget",
            "list",
            "--month",
            "2024-02",
            "--format",
            "json",
            "--data",
            str(data_path),
        )
    )

    assert len(payload) == 1
    assert payload[0]["month"] == "2024-02"
    assert payload[0]["category"] == "food"
    assert coerce_decimal(payload[0]["limit"]) == Decimal("100.00")


def test_budget_check_counts_only_expenses(project, tmp_path) -> None:
    data_path = tmp_path / "budget_usage.json"
    seed_budget_dataset(project, data_path)
    assert_success(
        project.run_cli(
            "budget",
            "set",
            "--month",
            "2024-02",
            "--category",
            "food",
            "--limit",
            "100.00",
            "--data",
            str(data_path),
        )
    )

    payload = load_json_output(
        project.run_cli(
            "budget",
            "check",
            "--month",
            "2024-02",
            "--format",
            "json",
            "--data",
            str(data_path),
        )
    )
    check = payload[0]
    assert set(check) == {
        "month",
        "category",
        "limit",
        "spent",
        "usage_ratio",
        "status",
    }
    assert check["month"] == "2024-02"
    assert check["limit"] == "100.00"
    assert coerce_decimal(check["spent"]) == Decimal("50.00")
    assert coerce_decimal(check["usage_ratio"]) == Decimal("0.5")
    assert check["status"] == "ok"


def test_warning_threshold_triggers_at_exactly_eighty_percent(project, tmp_path) -> None:
    data_path = tmp_path / "warning.json"
    assert_success(
        project.run_cli(
            "budget",
            "set",
            "--month",
            "2024-02",
            "--category",
            "food",
            "--limit",
            "100.00",
            "--data",
            str(data_path),
        )
    )
    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-02-10",
            "--amount",
            "-80.00",
            "--category",
            "food",
            "--description",
            "threshold",
            "--data",
            str(data_path),
        )
    )

    payload = load_json_output(
        project.run_cli(
            "budget",
            "check",
            "--month",
            "2024-02",
            "--format",
            "json",
            "--data",
            str(data_path),
        )
    )
    assert payload[0]["status"] == "warning"


def test_exceeded_threshold_triggers_at_exactly_one_hundred_percent(project, tmp_path) -> None:
    data_path = tmp_path / "exceeded.json"
    assert_success(
        project.run_cli(
            "budget",
            "set",
            "--month",
            "2024-02",
            "--category",
            "rent",
            "--limit",
            "70.00",
            "--data",
            str(data_path),
        )
    )
    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-02-20",
            "--amount",
            "-70.00",
            "--category",
            "rent",
            "--description",
            "cap",
            "--data",
            str(data_path),
        )
    )

    payload = load_json_output(
        project.run_cli(
            "budget",
            "check",
            "--month",
            "2024-02",
            "--format",
            "json",
            "--data",
            str(data_path),
        )
    )
    assert payload[0]["status"] == "exceeded"


def test_budget_check_omits_categories_without_budgets(project, tmp_path) -> None:
    data_path = tmp_path / "missing_budget.json"
    seed_budget_dataset(project, data_path)
    assert_success(
        project.run_cli(
            "budget",
            "set",
            "--month",
            "2024-02",
            "--category",
            "food",
            "--limit",
            "60.00",
            "--data",
            str(data_path),
        )
    )

    payload = load_json_output(
        project.run_cli(
            "budget",
            "check",
            "--month",
            "2024-02",
            "--format",
            "json",
            "--data",
            str(data_path),
        )
    )
    assert {item["category"] for item in payload} == {"food"}


def test_budgets_are_scoped_by_month_and_allow_zero_spend(project, tmp_path) -> None:
    data_path = tmp_path / "month_scope.json"
    seed_budget_dataset(project, data_path)
    assert_success(
        project.run_cli(
            "budget",
            "set",
            "--month",
            "2024-03",
            "--category",
            "food",
            "--limit",
            "50.00",
            "--data",
            str(data_path),
        )
    )

    payload = load_json_output(
        project.run_cli(
            "budget",
            "check",
            "--month",
            "2024-03",
            "--format",
            "json",
            "--data",
            str(data_path),
        )
    )
    assert len(payload) == 1
    assert coerce_decimal(payload[0]["spent"]) == Decimal("10.00")

    data_path_two = tmp_path / "zero_spend.json"
    assert_success(
        project.run_cli(
            "budget",
            "set",
            "--month",
            "2024-04",
            "--category",
            "food",
            "--limit",
            "50.00",
            "--data",
            str(data_path_two),
        )
    )
    zero_payload = load_json_output(
        project.run_cli(
            "budget",
            "check",
            "--month",
            "2024-04",
            "--format",
            "json",
            "--data",
            str(data_path_two),
        )
    )
    assert coerce_decimal(zero_payload[0]["spent"]) == Decimal("0")
    assert zero_payload[0]["status"] == "ok"
