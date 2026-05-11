from __future__ import annotations

from evaluation.project_5.common import (
    assert_failure,
    assert_success,
    issue_record,
    load_json_output,
    profile_record,
    seed_valid_v1_profile,
    set_override,
)


def test_migrate_updates_base_and_override_timeout_keys(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    set_override(project, profile="alpha", target="prod", section="service", key="timeout", value="45")

    assert_success(project.run_cli("profile", "migrate", "--name", "alpha", "--to-version", "2"))

    show_payload = load_json_output(project.run_cli("profile", "show", "--name", "alpha", "--format", "json"))
    assert show_payload == profile_record(
        name="alpha",
        schema_version=2,
        sections={
            "database": {"port": "5432"},
            "service": {
                "debug": "false",
                "request_timeout": "30",
                "retries": "3",
            },
        },
    )

    resolved_payload = load_json_output(
        project.run_cli("profile", "resolve", "--name", "alpha", "--target", "prod", "--format", "json")
    )
    assert resolved_payload == {
        "name": "alpha",
        "target": "prod",
        "schema_version": 2,
        "sections": {
            "database": {"port": "5432"},
            "service": {
                "debug": "false",
                "request_timeout": "45",
                "retries": "3",
            },
        },
    }


def test_repeat_migration_fails_cleanly_without_changing_profile(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    assert_success(project.run_cli("profile", "migrate", "--name", "alpha", "--to-version", "2"))
    first = load_json_output(project.run_cli("profile", "show", "--name", "alpha", "--format", "json"))

    assert_failure(project.run_cli("profile", "migrate", "--name", "alpha", "--to-version", "2"))
    second = load_json_output(project.run_cli("profile", "show", "--name", "alpha", "--format", "json"))

    assert first == second


def test_migrate_updates_all_target_overrides(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    set_override(project, profile="alpha", target="prod", section="service", key="timeout", value="45")
    set_override(project, profile="alpha", target="dev", section="service", key="timeout", value="15")

    assert_success(project.run_cli("profile", "migrate", "--name", "alpha", "--to-version", "2"))

    prod_payload = load_json_output(
        project.run_cli("profile", "resolve", "--name", "alpha", "--target", "prod", "--format", "json")
    )
    dev_payload = load_json_output(
        project.run_cli("profile", "resolve", "--name", "alpha", "--target", "dev", "--format", "json")
    )
    assert prod_payload["sections"]["service"]["request_timeout"] == "45"
    assert dev_payload["sections"]["service"]["request_timeout"] == "15"
    assert "timeout" not in prod_payload["sections"]["service"]
    assert "timeout" not in dev_payload["sections"]["service"]


def test_migration_preserves_existing_retries_value(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    set_override(project, profile="alpha", target="prod", section="service", key="retries", value="5")

    assert_success(project.run_cli("profile", "migrate", "--name", "alpha", "--to-version", "2"))

    prod_payload = load_json_output(
        project.run_cli("profile", "resolve", "--name", "alpha", "--target", "prod", "--format", "json")
    )
    assert prod_payload["sections"]["service"]["retries"] == "5"


def test_validate_uses_request_timeout_after_migration(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    set_override(project, profile="alpha", target="dev", section="service", key="timeout", value="0")

    assert_success(project.run_cli("profile", "migrate", "--name", "alpha", "--to-version", "2"))

    payload = load_json_output(
        project.run_cli("profile", "validate", "--name", "alpha", "--target", "dev", "--format", "json")
    )
    assert payload == {
        "valid": False,
        "issues": [
            issue_record(path="service.request_timeout", code="invalid_positive_integer", value="0"),
        ],
    }
