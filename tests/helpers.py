from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path

from ui_faultlab.runner import load_config, run_episode


@contextmanager
def temporary_episode(task="create_event", seed=0, condition="clean"):
    with tempfile.TemporaryDirectory() as directory:
        result = run_episode(
            config=load_config("configs/experiment.yaml"),
            artifacts_root=directory,
            split="dev",
            task_id=task,
            seed=seed,
            condition=condition,
            force=True,
        )
        yield Path(directory), result

