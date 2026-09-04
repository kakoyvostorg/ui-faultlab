#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and verify the cached ShowUI Python environment")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    import torch
    import torchvision
    import transformers
    import accelerate
    import PIL
    import qwen_vl_utils

    result = {
        "torch": torch.__version__,
        "torch_cuda_build": torch.version.cuda,
        "torchvision": torchvision.__version__,
        "transformers": transformers.__version__,
        "accelerate": accelerate.__version__,
        "Pillow": PIL.__version__,
        "qwen_vl_utils": importlib.metadata.version("qwen-vl-utils"),
        "cuda_available_on_cpu_warmup": torch.cuda.is_available(),
        "status": "environment_ready",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
