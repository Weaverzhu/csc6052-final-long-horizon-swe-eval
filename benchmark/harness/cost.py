from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


KNOWN_COST_FILES = ("trajectory.traj.json", "usage.json", "cost.json")
FLOAT_KEYS = ("total_cost_usd", "cost_usd", "total_cost", "cost")
INPUT_TOKEN_KEYS = (
    "input_tokens",
    "prompt_tokens",
    "prompt_token_count",
    "input_token_count",
)
OUTPUT_TOKEN_KEYS = (
    "output_tokens",
    "completion_tokens",
    "completion_token_count",
    "output_token_count",
)
TOTAL_TOKEN_KEYS = ("total_tokens", "token_count")
MODEL_KEYS = ("model", "model_name")
PROVIDER_KEYS = ("provider", "backend", "model_backend")


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _extract_first_scalar(mapping: dict[str, Any], keys: Iterable[str], coercer) -> Any:
    for key in keys:
        if key in mapping:
            value = coercer(mapping[key])
            if value is not None:
                return value
    return None


def _mapping_candidate(mapping: dict[str, Any], path: str) -> dict[str, Any]:
    cost = _extract_first_scalar(mapping, FLOAT_KEYS, _coerce_float)
    input_tokens = _extract_first_scalar(mapping, INPUT_TOKEN_KEYS, _coerce_int)
    output_tokens = _extract_first_scalar(mapping, OUTPUT_TOKEN_KEYS, _coerce_int)
    total_tokens = _extract_first_scalar(mapping, TOTAL_TOKEN_KEYS, _coerce_int)
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    provider = None
    for key in PROVIDER_KEYS:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            provider = value.strip()
            break

    model = None
    for key in MODEL_KEYS:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            model = value.strip()
            break

    currency = mapping.get("currency")
    if isinstance(currency, str) and currency.strip():
        currency = currency.strip().upper()
    elif cost is not None:
        currency = "USD"
    else:
        currency = None

    signal_count = sum(
        value is not None for value in (cost, input_tokens, output_tokens, total_tokens)
    )
    if signal_count == 0:
        return {}

    depth = path.count(".") + path.count("[")
    score = signal_count * 10 - depth
    if cost is not None:
        score += 20

    return {
        "path": path,
        "total_cost_usd": cost,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "provider": provider,
        "model": model,
        "currency": currency,
        "score": score,
    }


def _walk_json_candidates(value: Any, path: str = "$") -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(value, dict):
        candidate = _mapping_candidate(value, path)
        if candidate:
            candidates.append(candidate)
        for key, child in value.items():
            candidates.extend(_walk_json_candidates(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            candidates.extend(_walk_json_candidates(child, f"{path}[{index}]"))
    return candidates


def summarize_cost_json(source_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "source_path": str(source_path),
            "total_cost_usd": 0.0,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "provider": None,
            "model": None,
            "currency": None,
            "is_complete": False,
            "missing_reason": f"failed to parse JSON artifact: {exc.__class__.__name__}",
        }

    candidates = _walk_json_candidates(payload)
    if not candidates:
        return {
            "source_path": str(source_path),
            "total_cost_usd": 0.0,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "provider": None,
            "model": None,
            "currency": None,
            "is_complete": False,
            "missing_reason": "no cost or token metadata found in artifact",
        }

    cost_candidates = [candidate for candidate in candidates if candidate["total_cost_usd"] is not None]
    if cost_candidates:
        best = max(
            cost_candidates,
            key=lambda item: (item["score"], -len(item["path"])),
        )
        return {
            "source_path": str(source_path),
            "selected_path": best["path"],
            "total_cost_usd": best["total_cost_usd"],
            "input_tokens": best["input_tokens"],
            "output_tokens": best["output_tokens"],
            "total_tokens": best["total_tokens"],
            "provider": best["provider"],
            "model": best["model"],
            "currency": best["currency"],
            "is_complete": True,
            "missing_reason": None,
        }

    best = max(candidates, key=lambda item: (item["score"], -len(item["path"])))
    return {
        "source_path": str(source_path),
        "selected_path": best["path"],
        "total_cost_usd": 0.0,
        "input_tokens": best["input_tokens"],
        "output_tokens": best["output_tokens"],
        "total_tokens": best["total_tokens"],
        "provider": best["provider"],
        "model": best["model"],
        "currency": best["currency"],
        "is_complete": False,
        "missing_reason": "artifact reports token usage but no total cost",
    }


def _choose_cost_source(artifact_dir: Path) -> Path | None:
    for name in KNOWN_COST_FILES:
        candidate = artifact_dir / name
        if candidate.exists():
            return candidate
    json_candidates = sorted(artifact_dir.glob("*.json"))
    if json_candidates:
        return json_candidates[0]
    return None


def summarize_artifact_dir(artifact_dir: Path) -> dict[str, Any]:
    source_path = _choose_cost_source(artifact_dir)
    backend = artifact_dir.parent.name
    run_id = artifact_dir.name
    if source_path is None:
        return {
            "backend": backend,
            "run_id": run_id,
            "artifact_dir": str(artifact_dir),
            "source_path": None,
            "total_cost_usd": 0.0,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "provider": None,
            "model": None,
            "currency": None,
            "is_complete": False,
            "missing_reason": "no JSON cost artifact found",
        }

    summary = summarize_cost_json(source_path)
    summary["backend"] = backend
    summary["run_id"] = run_id
    summary["artifact_dir"] = str(artifact_dir)
    return summary


def discover_artifact_dirs(workspace_dir: Path) -> list[Path]:
    results_root = workspace_dir / ".agent-results"
    if not results_root.exists():
        return []
    return sorted(
        path
        for path in results_root.glob("*/*")
        if path.is_dir()
    )


def summarize_workspace_cost(workspace_dir: Path) -> dict[str, Any]:
    artifact_dirs = discover_artifact_dirs(workspace_dir)
    if not artifact_dirs:
        return {
            "artifacts": [],
            "artifact_count": 0,
            "observed_cost_artifact_count": 0,
            "missing_cost_artifact_count": 0,
            "total_cost_usd": 0.0,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "is_complete": False,
            "missing_reason": "no agent artifact directory found",
        }

    artifacts = [summarize_artifact_dir(path) for path in artifact_dirs]
    observed_cost_artifact_count = sum(
        1 for artifact in artifacts if artifact["is_complete"]
    )
    missing_cost_artifact_count = len(artifacts) - observed_cost_artifact_count

    def maybe_sum(key: str) -> int | None:
        values = [artifact[key] for artifact in artifacts]
        if any(value is None for value in values):
            return None
        return sum(values)

    total_cost_usd = sum(float(artifact["total_cost_usd"]) for artifact in artifacts)
    input_tokens = maybe_sum("input_tokens")
    output_tokens = maybe_sum("output_tokens")
    total_tokens = maybe_sum("total_tokens")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    missing_reasons = [
        str(artifact["missing_reason"])
        for artifact in artifacts
        if artifact.get("missing_reason")
    ]
    return {
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "observed_cost_artifact_count": observed_cost_artifact_count,
        "missing_cost_artifact_count": missing_cost_artifact_count,
        "total_cost_usd": total_cost_usd,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "is_complete": missing_cost_artifact_count == 0,
        "missing_reason": "; ".join(missing_reasons) if missing_reasons else None,
    }


def aggregate_trajectory_costs(stage_results: list[dict[str, Any]]) -> dict[str, Any]:
    total_cost_usd = 0.0
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    have_input = True
    have_output = True
    have_total_tokens = True
    cost_stage_count = 0
    missing_cost_stage_count = 0

    for stage in stage_results:
        agent_cost = stage.get("agent_cost") or {}
        if not isinstance(agent_cost, dict):
            missing_cost_stage_count += 1
            have_input = False
            have_output = False
            have_total_tokens = False
            continue

        total_cost_usd += float(agent_cost.get("total_cost_usd") or 0.0)
        if agent_cost.get("observed_cost_artifact_count", 0):
            cost_stage_count += 1
        if not agent_cost.get("is_complete", False):
            missing_cost_stage_count += 1

        stage_input = agent_cost.get("input_tokens")
        stage_output = agent_cost.get("output_tokens")
        stage_total_tokens = agent_cost.get("total_tokens")
        if stage_input is None:
            have_input = False
        else:
            input_tokens += int(stage_input)
        if stage_output is None:
            have_output = False
        else:
            output_tokens += int(stage_output)
        if stage_total_tokens is None:
            have_total_tokens = False
        else:
            total_tokens += int(stage_total_tokens)

    aggregated_input = input_tokens if have_input else None
    aggregated_output = output_tokens if have_output else None
    aggregated_total = total_tokens if have_total_tokens else None
    if (
        aggregated_total is None
        and aggregated_input is not None
        and aggregated_output is not None
    ):
        aggregated_total = aggregated_input + aggregated_output

    return {
        "total_agent_cost_usd": total_cost_usd,
        "input_tokens": aggregated_input,
        "output_tokens": aggregated_output,
        "total_tokens": aggregated_total,
        "cost_stage_count": cost_stage_count,
        "missing_cost_stage_count": missing_cost_stage_count,
        "cost_complete": bool(stage_results) and missing_cost_stage_count == 0,
    }
