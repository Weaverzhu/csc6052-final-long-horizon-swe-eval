from __future__ import annotations

from evaluation.project_5.common import (
    assert_success,
    load_json_output,
    profile_record,
    set_base,
)


def test_submission_uses_uv_managed_package_layout(project) -> None:
    project.assert_submission_contract()


def test_profile_show_returns_nested_sections_and_schema_version(project) -> None:
    set_base(project, profile="beta", section="service", key="debug", value="false")
    set_base(project, profile="beta", section="database", key="port", value="5432")

    payload = load_json_output(project.run_cli("profile", "show", "--name", "beta", "--format", "json"))
    assert payload == profile_record(
        name="beta",
        schema_version=1,
        sections={
            "database": {"port": "5432"},
            "service": {"debug": "false"},
        },
    )


def test_profile_list_returns_sorted_names(project) -> None:
    set_base(project, profile="zeta", section="service", key="debug", value="false")
    set_base(project, profile="alpha", section="service", key="debug", value="true")

    payload = load_json_output(project.run_cli("profile", "list", "--format", "json"))
    assert payload == ["alpha", "zeta"]
