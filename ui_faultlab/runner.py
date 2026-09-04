from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from app.tasks import TASKS
from ui_faultlab.actions import Action
from ui_faultlab.agents.scripted import ScriptedOracleAgent
from ui_faultlab.artifacts.registry import ArtifactRegistry
from ui_faultlab.artifacts.schema import utc_now, validate_manifest
from ui_faultlab.diagnosis.active_probe import diagnose_active
from ui_faultlab.diagnosis.oracle import diagnose_oracle
from ui_faultlab.diagnosis.terminal import diagnose_terminal
from ui_faultlab.diagnosis.trajectory import diagnose_trajectory, public_trajectory
from ui_faultlab.environment import BrowserEnvironment
from ui_faultlab.faults.agent_faults import AgentFaultInjector, select_agent_fault, select_application_fault
from ui_faultlab.instrumentation import append_jsonl, atomic_write_json, canonical_hash


def load_config(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def episode_identity(split: str, task_id: str, seed: int, condition: str, config_hash: str) -> str:
    opaque = canonical_hash({"split": split, "task": task_id, "seed": seed, "condition": condition, "config": config_hash})[:16]
    return f"ep_{opaque}"


def _write_prediction(root: Path, method: str, episode_id: str, prediction: dict) -> None:
    atomic_write_json(root / "predictions" / method / f"{episode_id}.json", prediction)


def run_episode(*, config: dict, artifacts_root: str | Path, split: str, task_id: str, seed: int, condition: str, force: bool = False) -> dict:
    root = Path(artifacts_root)
    config_hash = canonical_hash(config)
    episode_id = episode_identity(split, task_id, seed, condition, config_hash)
    episode_dir = root / "episodes" / episode_id
    registry = ArtifactRegistry(root / "registry.json")
    if not force and not registry.should_run(episode_id, config_hash):
        return json.loads((episode_dir / "evaluation.json").read_text())

    app_fault = select_application_fault(task_id) if condition == "application_fault" else None
    agent_fault = select_agent_fault(task_id, seed) if condition == "agent_fault" else None
    gold_label = "application_bug" if app_fault else "agent_error" if agent_fault else "ambiguous"
    agent = ScriptedOracleAgent()
    env = BrowserEnvironment(task_id, seed, episode_dir, app_fault, tuple(config.get("resolution", [960, 640])))
    started = utc_now()
    manifest = {
        "episode_id": episode_id, "task_id": task_id, "task_version": TASKS[task_id].version,
        "seed": seed, "split": split, "condition": condition, "model": agent.name,
        "model_revision": agent.revision, "prompt_hash": canonical_hash({"policy": agent.revision}),
        "config_hash": config_hash, "resolution": list(config.get("resolution", [960, 640])),
        "device_scale_factor": 1, "start_timestamp": started, "end_timestamp": None,
        "git_commit": git_commit(), "status": "started",
    }
    validate_manifest(manifest)
    atomic_write_json(episode_dir / "manifest.json", manifest)
    registry.update(episode_id, {"status": "started", "config_hash": config_hash, "path": str(episode_dir)})
    atomic_write_json(episode_dir / "gold.json", {"gold_label": gold_label, "fault_type": app_fault or agent_fault, "family": condition})

    initial_obs = env.reset()
    before_obs = initial_obs
    injector = AgentFaultInjector(agent_fault, task_id)
    snapshots: list[dict] = []
    steps: list[dict] = []
    total_latency_ms = 0.0
    for index, intended in enumerate(agent.actions(task_id, seed)):
        if index >= TASKS[task_id].max_steps + 2:
            break
        snapshots.append(env.snapshot())
        intercepted = injector.intercept(intended, index)
        start = time.perf_counter()
        after_obs, result = env.apply(intercepted.executed)
        latency_ms = (time.perf_counter() - start) * 1000
        total_latency_ms += latency_ms
        step = {
            "episode_id": episode_id, "step_id": f"{episode_id}_s{index:03d}", "index": index,
            "before_screenshot": before_obs["screenshot_path"], "after_screenshot": after_obs["screenshot_path"],
            "before_sha256": before_obs["screenshot_sha256"], "after_sha256": after_obs["screenshot_sha256"],
            "intended_action": intended.to_dict(), "executed_action": intercepted.executed.to_dict(),
            "fault_injected": intercepted.injected, "result": result, "latency_ms": latency_ms,
        }
        steps.append(step)
        append_jsonl(episode_dir / "steps.jsonl", step)
        before_obs = after_obs
        if intended.type == "finish":
            break

    task_success = env.succeeded()
    trajectory = public_trajectory(steps)
    terminal = diagnose_terminal(env.instruction, before_obs["screenshot_path"], not task_success)
    passive = diagnose_trajectory(env.instruction, trajectory, not task_success)
    probe_latency_ms = 0.0

    def probe(step_index: int) -> dict:
        nonlocal probe_latency_ms
        probe_env = BrowserEnvironment(task_id, seed, episode_dir / "probe", app_fault, tuple(config.get("resolution", [960, 640])))
        probe_env.state = snapshots[step_index]
        probe_env.step_index = step_index
        start = time.perf_counter()
        observation, _ = probe_env.apply(Action.from_dict(trajectory[step_index]["action"]))
        probe_latency_ms += (time.perf_counter() - start) * 1000
        return {"after_sha256": observation["screenshot_sha256"], "screenshot_path": observation["screenshot_path"]}

    active = diagnose_active(env.instruction, trajectory, not task_success, probe, int(config.get("max_probes", 1)))
    oracle = diagnose_oracle(gold_label)
    for name, prediction in (("terminal", terminal), ("trajectory", passive), ("active", active), ("oracle", oracle)):
        atomic_write_json(episode_dir / f"diagnosis_{name}.json", prediction)
        _write_prediction(root, name, episode_id, prediction)

    evaluation = {
        "episode_id": episode_id, "task_id": task_id, "seed": seed, "split": split,
        "condition": condition, "task_success": task_success, "gold_label": gold_label,
        "gold_fault_type": app_fault or agent_fault, "predictions": {"terminal": terminal, "trajectory": passive, "active": active, "oracle": oracle},
        "steps": len(steps), "invalid_actions": 0, "parse_failures": 0,
        "loop_repetitions": sum(a["executed_action"] == b["executed_action"] for a, b in zip(steps, steps[1:])),
        "latency_ms": {"execution": total_latency_ms, "active_probe": probe_latency_ms},
        "vlm_calls": 0, "visual_tokens": None, "estimated_cost_rub": 0.0,
    }
    atomic_write_json(episode_dir / "evaluation.json", evaluation)
    manifest.update({"end_timestamp": utc_now(), "status": "completed"})
    atomic_write_json(episode_dir / "manifest.json", manifest)
    registry.update(episode_id, {"status": "completed", "config_hash": config_hash, "path": str(episode_dir)})
    return evaluation

