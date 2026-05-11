from __future__ import annotations

from evaluation.project_5.common import (
    issue_record,
    load_json_output,
    seed_valid_v1_profile,
    set_base,
    set_override,
)


def test_validate_reports_missing_required_fields(project) -> None:
    set_base(project, profile="alpha", section="service", key="debug", value="false")

    payload = load_json_output(
        project.run_cli("profile", "validate", "--name", "alpha", "--target", "dev", "--format", "json")
    )
    assert payload == {
        "valid": False,
        "issues": [
            issue_record(path="database.port", code="missing_required", value=None),
            issue_record(path="service.timeout", code="missing_required", value=None),
        ],
    }


def test_validate_reports_exact_type_and_range_codes(project) -> None:
    set_base(project, profile="alpha", section="database", key="port", value="70000")
    set_base(project, profile="alpha", section="service", key="debug", value="maybe")
    set_base(project, profile="alpha", section="service", key="timeout", value="0")

    payload = load_json_output(
        project.run_cli("profile", "validate", "--name", "alpha", "--target", "dev", "--format", "json")
    )
    assert payload == {
        "valid": False,
        "issues": [
            issue_record(path="database.port", code="invalid_integer_range", value="70000"),
            issue_record(path="service.debug", code="invalid_boolean", value="maybe"),
            issue_record(path="service.timeout", code="invalid_positive_integer", value="0"),
        ],
    }


def test_validate_accepts_valid_v1_profile(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    payload = load_json_output(
        project.run_cli("profile", "validate", "--name", "alpha", "--target", "dev", "--format", "json")
    )
    assert payload == {"valid": True, "issues": []}


def test_validate_uses_target_overrides_in_resolved_config(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    set_override(project, profile="alpha", target="dev", section="service", key="timeout", value="0")

    payload = load_json_output(
        project.run_cli("profile", "validate", "--name", "alpha", "--target", "dev", "--format", "json")
    )
    assert payload == {
        "valid": False,
        "issues": [
            issue_record(path="service.timeout", code="invalid_positive_integer", value="0"),
        ],
    }
