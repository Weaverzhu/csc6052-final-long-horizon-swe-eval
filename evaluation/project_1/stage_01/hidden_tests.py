from __future__ import annotations

from decimal import Decimal

from evaluation.project_1.common import (
    assert_failure,
    assert_success,
    coerce_decimal,
    load_json_output,
)


def test_submission_uses_uv_managed_package_layout(project) -> None:
    project.assert_submission_contract()


def test_submission_contains_non_cli_implementation_modules(project) -> None:
    package_files = project.package_python_files()
    implementation_modules = [
        path
        for path in package_files
        if path.name not in {"__init__.py", "__main__.py"}
    ]
    assert implementation_modules, (
        "expected at least one non-entry-point module inside the finance_tracker package"
    )


def test_list_empty_returns_empty_json(project) -> None:
    payload = load_json_output(project.run_cli("list", "--format", "json"))
    assert payload == []


def test_add_income_transaction_and_trim_text_fields(project) -> None:
    result = project.run_cli(
        "add",
        "--date",
        "2024-01-05",
        "--amount",
        "1200.50",
        "--category",
        " salary ",
        "--description",
        " January paycheck ",
    )
    assert_success(result)

    payload = load_json_output(project.run_cli("list", "--format", "json"))
    assert len(payload) == 1
    assert payload[0]["date"] == "2024-01-05"
    assert coerce_decimal(payload[0]["amount"]) == Decimal("1200.50")
    assert payload[0]["category"] == "salary"
    assert payload[0]["description"] == "January paycheck"


def test_add_negative_expense_with_punctuation_in_description(project) -> None:
    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-01-06",
            "--amount",
            "-45.25",
            "--category",
            "food",
            "--description",
            "milk, eggs, and bread",
        )
    )

    payload = load_json_output(project.run_cli("list", "--format", "json"))
    assert len(payload) == 1
    assert coerce_decimal(payload[0]["amount"]) == Decimal("-45.25")
    assert payload[0]["description"] == "milk, eggs, and bread"


def test_multiple_subprocess_adds_are_sorted_and_preserve_same_day_order(project) -> None:
    for args in (
        ("2024-01-10", "-15.00", "food", "Second"),
        ("2024-01-09", "100.00", "salary", "First"),
        ("2024-01-10", "-20.00", "food", "Third"),
    ):
        assert_success(
            project.run_cli(
                "add",
                "--date",
                args[0],
                "--amount",
                args[1],
                "--category",
                args[2],
                "--description",
                args[3],
            )
        )

    payload = load_json_output(project.run_cli("list", "--format", "json"))
    descriptions = [item["description"] for item in payload]
    assert descriptions == ["First", "Second", "Third"]


def test_reject_malformed_date(project) -> None:
    result = project.run_cli(
        "add",
        "--date",
        "2024-13-01",
        "--amount",
        "10.00",
        "--category",
        "misc",
        "--description",
        "bad date",
    )
    assert_failure(result)


def test_reject_zero_amount(project) -> None:
    result = project.run_cli(
        "add",
        "--date",
        "2024-01-05",
        "--amount",
        "0",
        "--category",
        "misc",
        "--description",
        "zero",
    )
    assert_failure(result)


def test_reject_non_numeric_amount(project) -> None:
    result = project.run_cli(
        "add",
        "--date",
        "2024-01-05",
        "--amount",
        "twelve",
        "--category",
        "misc",
        "--description",
        "bad amount",
    )
    assert_failure(result)


def test_reject_non_finite_decimal_amount(project) -> None:
    for amount in ("NaN", "Infinity", "-Infinity"):
        result = project.run_cli(
            "add",
            "--date",
            "2024-01-05",
            "--amount",
            amount,
            "--category",
            "misc",
            "--description",
            "bad amount",
        )
        assert_failure(result)


def test_reject_blank_category_after_trimming(project) -> None:
    result = project.run_cli(
        "add",
        "--date",
        "2024-01-05",
        "--amount",
        "12.00",
        "--category",
        "   ",
        "--description",
        "blank category",
    )
    assert_failure(result)
