from __future__ import annotations

from evaluation.project_5.common import issue_record, load_json_output, seed_valid_v1_profile, set_base, set_override


def test_prod_validation_adds_policy_specific_issue_codes(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    set_base(project, profile="alpha", section="service", key="debug", value="true")
    set_base(project, profile="alpha", section="service", key="max_timeout", value="20")
    set_override(project, profile="alpha", target="prod", section="service", key="replicas", value="1")

    payload = load_json_output(
        project.run_cli("profile", "validate", "--name", "alpha", "--target", "prod", "--format", "json")
    )
    assert payload == {
        "valid": False,
        "issues": [
            issue_record(path="service.debug", code="prod_debug_forbidden", value="true"),
            issue_record(path="service.replicas", code="prod_replicas_too_low", value="1"),
            issue_record(path="service.timeout", code="timeout_exceeds_max", value="30"),
        ],
    }


def test_prod_timeout_policy_uses_resolved_override_value(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    set_base(project, profile="alpha", section="service", key="timeout", value="10")
    set_base(project, profile="alpha", section="service", key="max_timeout", value="20")
    set_override(project, profile="alpha", target="prod", section="service", key="timeout", value="30")

    payload = load_json_output(
        project.run_cli("profile", "validate", "--name", "alpha", "--target", "prod", "--format", "json")
    )
    assert issue_record(path="service.timeout", code="timeout_exceeds_max", value="30") in payload["issues"]
