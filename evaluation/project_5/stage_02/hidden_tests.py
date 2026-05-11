from __future__ import annotations

from evaluation.project_5.common import load_json_output, seed_valid_v1_profile, set_override


def test_profile_resolve_merges_base_and_target_override(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    set_override(project, profile="alpha", target="prod", section="service", key="debug", value="true")
    set_override(project, profile="alpha", target="prod", section="service", key="replicas", value="3")

    payload = load_json_output(
        project.run_cli("profile", "resolve", "--name", "alpha", "--target", "prod", "--format", "json")
    )
    assert payload == {
        "name": "alpha",
        "target": "prod",
        "schema_version": 1,
        "sections": {
            "database": {"port": "5432"},
            "service": {
                "debug": "true",
                "replicas": "3",
                "timeout": "30",
            },
        },
    }


def test_target_override_replaces_conflicting_base_value(project) -> None:
    seed_valid_v1_profile(project, profile="alpha")
    set_override(project, profile="alpha", target="prod", section="service", key="timeout", value="45")

    payload = load_json_output(
        project.run_cli("profile", "resolve", "--name", "alpha", "--target", "prod", "--format", "json")
    )
    assert payload["sections"]["service"]["timeout"] == "45"
