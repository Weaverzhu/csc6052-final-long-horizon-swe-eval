from __future__ import annotations

from evaluation.project_5.common import assert_success, load_json_output, seed_valid_v1_profile, set_override


def test_resolve_explain_reports_effective_config_and_sources(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    set_override(project, profile="alpha", target="prod", section="service", key="debug", value="true")
    set_override(project, profile="alpha", target="prod", section="service", key="replicas", value="3")
    assert_success(project.run_cli("profile", "migrate", "--name", "alpha", "--to-version", "2"))

    payload = load_json_output(
        project.run_cli(
            "profile",
            "resolve",
            "--name",
            "alpha",
            "--target",
            "prod",
            "--explain",
            "--format",
            "json",
        )
    )
    assert payload == {
        "config": {
            "database": {"port": "5432"},
            "service": {
                "debug": "true",
                "replicas": "3",
                "request_timeout": "30",
                "retries": "3",
            },
        },
        "sources": {
            "database.port": "base",
            "service.debug": "target:prod",
            "service.replicas": "target:prod",
            "service.request_timeout": "base",
            "service.retries": "base",
        },
        "schema_version": 2,
        "target": "prod",
        "name": "alpha",
    }


def test_plain_resolve_contract_is_preserved_without_explain(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    set_override(project, profile="alpha", target="prod", section="service", key="debug", value="true")
    set_override(project, profile="alpha", target="prod", section="service", key="replicas", value="3")
    assert_success(project.run_cli("profile", "migrate", "--name", "alpha", "--to-version", "2"))

    payload = load_json_output(
        project.run_cli("profile", "resolve", "--name", "alpha", "--target", "prod", "--format", "json")
    )
    assert payload == {
        "name": "alpha",
        "target": "prod",
        "schema_version": 2,
        "sections": {
            "database": {"port": "5432"},
            "service": {
                "debug": "true",
                "replicas": "3",
                "request_timeout": "30",
                "retries": "3",
            },
        },
    }


def test_migrated_validation_still_uses_request_timeout_in_stage_six(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    set_override(project, profile="alpha", target="dev", section="service", key="timeout", value="0")
    assert_success(project.run_cli("profile", "migrate", "--name", "alpha", "--to-version", "2"))

    payload = load_json_output(
        project.run_cli("profile", "validate", "--name", "alpha", "--target", "dev", "--format", "json")
    )
    assert payload == {
        "valid": False,
        "issues": [
            {
                "path": "service.request_timeout",
                "code": "invalid_positive_integer",
                "value": "0",
            }
        ],
    }
