from __future__ import annotations

import json
from decimal import Decimal

from evaluation.project_1.common import (
    assert_failure,
    assert_success,
    coerce_decimal,
    load_json_output,
)


def test_stage_02_regression_summary_still_works(project) -> None:
    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-01-01",
            "--amount",
            "100.00",
            "--category",
            "salary",
            "--description",
            "income",
        )
    )
    payload = load_json_output(project.run_cli("summary", "--format", "json"))
    assert payload[0]["month"] == "2024-01"


def test_custom_json_path_persists_across_processes(project) -> None:
    custom_path = project.root / "nested" / "ledger.json"
    custom_path.parent.mkdir(parents=True, exist_ok=True)

    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-03-01",
            "--amount",
            "42.00",
            "--category",
            "test",
            "--description",
            "Persistence check",
            "--data",
            "nested/ledger.json",
        )
    )

    payload = load_json_output(
        project.run_cli("list", "--format", "json", "--data", "nested/ledger.json")
    )
    assert len(payload) == 1
    assert payload[0]["description"] == "Persistence check"


def test_summary_reads_from_custom_data_path(project) -> None:
    custom_path = project.root / "summary.json"
    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-03-01",
            "--amount",
            "42.00",
            "--category",
            "test",
            "--description",
            "custom summary",
            "--data",
            str(custom_path),
        )
    )

    payload = load_json_output(
        project.run_cli("summary", "--format", "json", "--data", str(custom_path))
    )
    assert len(payload) == 1
    summary = payload[0]
    assert summary["month"] == "2024-03"
    assert coerce_decimal(summary["income_total"]) == Decimal("42.00")
    assert coerce_decimal(summary["expense_total"]) == Decimal("0")
    assert coerce_decimal(summary["net_total"]) == Decimal("42.00")
    assert summary["transaction_count"] == 1


def test_distinct_data_paths_are_isolated(project) -> None:
    first = project.root / "a.json"
    second = project.root / "b.json"

    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-03-01",
            "--amount",
            "10.00",
            "--category",
            "alpha",
            "--description",
            "first",
            "--data",
            str(first),
        )
    )
    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-03-02",
            "--amount",
            "20.00",
            "--category",
            "beta",
            "--description",
            "second",
            "--data",
            str(second),
        )
    )

    first_payload = load_json_output(
        project.run_cli("list", "--format", "json", "--data", str(first))
    )
    second_payload = load_json_output(
        project.run_cli("list", "--format", "json", "--data", str(second))
    )

    assert [item["description"] for item in first_payload] == ["first"]
    assert [item["description"] for item in second_payload] == ["second"]


def test_missing_custom_path_is_initialized_automatically(project) -> None:
    missing_path = project.root / "new_data.json"
    payload = load_json_output(
        project.run_cli("list", "--format", "json", "--data", str(missing_path))
    )
    assert payload == []
    assert missing_path.exists()


def test_created_json_file_uses_expected_contract(project) -> None:
    data_path = project.root / "contract.json"
    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-03-03",
            "--amount",
            "-9.50",
            "--category",
            "snacks",
            "--description",
            "chips",
            "--data",
            str(data_path),
        )
    )

    document = json.loads(data_path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    assert "transactions" in document
    assert isinstance(document["transactions"], list)


def test_default_data_path_still_works_without_data_flag(project) -> None:
    assert_success(
        project.run_cli(
            "add",
            "--date",
            "2024-03-04",
            "--amount",
            "15.00",
            "--category",
            "misc",
            "--description",
            "default path",
        )
    )
    default_path = project.root / "finance_data.json"
    assert default_path.exists()

    payload = load_json_output(project.run_cli("list", "--format", "json"))
    assert [item["description"] for item in payload] == ["default path"]


def test_empty_dataset_file_is_accepted(project) -> None:
    data_path = project.root / "empty.json"
    data_path.write_text('{"transactions": []}', encoding="utf-8")

    payload = load_json_output(
        project.run_cli("list", "--format", "json", "--data", str(data_path))
    )
    assert payload == []


def test_malformed_json_file_is_rejected(project) -> None:
    bad_path = project.root / "broken.json"
    bad_path.write_text("{not-valid-json", encoding="utf-8")

    result = project.run_cli("list", "--format", "json", "--data", str(bad_path))
    assert_failure(result)


def test_malformed_json_file_is_rejected_for_summary(project) -> None:
    bad_path = project.root / "broken-summary.json"
    bad_path.write_text("{not-valid-json", encoding="utf-8")

    result = project.run_cli("summary", "--format", "json", "--data", str(bad_path))
    assert_failure(result)
