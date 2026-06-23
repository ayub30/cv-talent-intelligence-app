"""
Fine-tune the talent-search LoRA adapter using the generated dataset.

Training config (agreed values):
    LoRA rank:    8
    Alpha:        16.0
    Learning rate: 1e-4
    Iterations:   1000
    Save every:   100 steps
    LoRA layers:  8  (last 8 of 28)
    Adapter out:  adapters_talent_search/

Usage (Apple Silicon Mac with mlx-lm installed):
    python train_talent_search_lora.py
    python train_talent_search_lora.py --dry-run   # data prep only, no API calls
    python train_talent_search_lora.py --dataset data/talent_search_dataset.jsonl

Requires:
    pip install mlx-lm
    Dataset at data/talent_search_dataset.jsonl  (run generate_talent_search_dataset.py first)
"""

import argparse
import json
import os
import random
import subprocess
import sys

MODEL_PATH = os.path.join(os.path.dirname(__file__), "llama-3.2-3B-fused-800")
ADAPTER_PATH = os.path.join(os.path.dirname(__file__), "adapters_talent_search")
DATASET_PATH = "data/talent_search_dataset.jsonl"
MLX_DATA_DIR = "data/mlx_talent_search"

SYSTEM_PROMPT = (
    "You are a talent intelligence assistant helping programme managers find the right consultants. "
    "When a PM asks a question, use the available tools to search for matching candidates, "
    "then give a concise 2-3 sentence answer summarising the best options found."
)

TOOL_DESCRIPTIONS = (
    "Available tools:\n"
    "- search_cvs(query: str, n_results: int = 10): Semantic search across employee CVs. "
    "Use for open-ended talent discovery.\n"
    "- query_candidates(filters: dict): Structured query by skill, seniority, availability, "
    "company, or location. Use when the PM specifies concrete filter criteria.\n"
    "- get_profile_cv(employee_id: str): Fetch full CV for a specific employee ID."
)

ADAPTER_CONFIG = {
    "lora_parameters": {
        "rank": 8,
        "alpha": 16.0,
        "dropout": 0.0,
        "scale": 10.0,
    },
    "num_layers": 8,
    "type": "lora",
    "fine_tune_type": "lora",
}


def _format_tool_call(tc: dict) -> str:
    return json.dumps({"name": tc["name"], "parameters": tc.get("args", {})})


def format_example(instruction: str, response: dict) -> str:
    """Render one training example as a Llama 3.2 tool-use conversation."""
    tool_calls: list[dict] = response.get("tool_calls", [])
    answer: str = response.get("answer", "")

    text = (
        "<|begin_of_text|>"
        "<|start_header_id|>system<|end_header_id|>\n\n"
        f"{SYSTEM_PROMPT}\n\n{TOOL_DESCRIPTIONS}"
        "<|eot_id|>"
        "<|start_header_id|>user<|end_header_id|>\n\n"
        f"{instruction}"
        "<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n\n"
    )

    if tool_calls:
        text += _format_tool_call(tool_calls[0]) + "<|eot_id|>"
        # Stub tool result so the model sees a complete turn
        text += (
            "<|start_header_id|>ipython<|end_header_id|>\n\n"
            '[{"employee_id": "emp_0001", "name": "Alice Chen", "score": 88, '
            '"cv_text": "Alice Chen: Python, Machine Learning, AWS."}]'
            "<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n\n"
            f"{answer}"
            "<|eot_id|>"
        )
    else:
        text += f"{answer}<|eot_id|>"

    return text


def prepare_mlx_data(dataset_path: str, output_dir: str, seed: int = 42) -> tuple[int, int]:
    """Convert JSONL dataset → MLX train.jsonl / valid.jsonl. Returns (n_train, n_valid)."""
    with open(dataset_path) as fh:
        examples = [json.loads(line) for line in fh if line.strip()]

    rng = random.Random(seed)
    rng.shuffle(examples)

    split = int(len(examples) * 0.9)
    splits = {"train": examples[:split], "valid": examples[split:]}

    os.makedirs(output_dir, exist_ok=True)
    for name, data in splits.items():
        with open(os.path.join(output_dir, f"{name}.jsonl"), "w") as fh:
            for ex in data:
                text = format_example(ex["instruction"], ex["response"])
                fh.write(json.dumps({"text": text}) + "\n")

    return len(splits["train"]), len(splits["valid"])


def write_adapter_config(adapter_path: str) -> None:
    os.makedirs(adapter_path, exist_ok=True)
    config_path = os.path.join(adapter_path, "adapter_config.json")
    with open(config_path, "w") as fh:
        json.dump(ADAPTER_CONFIG, fh, indent=2)
    print(f"  Wrote {config_path}")


def run_training(model_path: str, adapter_path: str, data_dir: str) -> None:
    cmd = [
        sys.executable, "-m", "mlx_lm.lora",
        "--model", model_path,
        "--train",
        "--data", data_dir,
        "--iters", "1000",
        "--steps-per-eval", "100",
        "--save-every", "100",
        "--adapter-path", adapter_path,
        "--learning-rate", "1e-4",
        "--lora-rank", "8",
        "--lora-layers", "8",
        "--batch-size", "4",
        "--grad-checkpoint",
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train talent-search LoRA adapter with MLX")
    parser.add_argument("--dataset", default=DATASET_PATH)
    parser.add_argument("--model", default=MODEL_PATH)
    parser.add_argument("--adapter", default=ADAPTER_PATH)
    parser.add_argument("--mlx-data", default=MLX_DATA_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Prepare data only, skip training")
    args = parser.parse_args()

    print(f"Dataset:  {args.dataset}")
    print(f"Model:    {args.model}")
    print(f"Adapter:  {args.adapter}")

    if not os.path.exists(args.dataset):
        print(f"\nERROR: dataset not found: {args.dataset}")
        print("Run first: python generate_talent_search_dataset.py")
        sys.exit(1)

    if not os.path.isdir(args.model):
        print(f"\nERROR: model not found: {args.model}")
        sys.exit(1)

    print("\n[1/3] Writing adapter config...")
    write_adapter_config(args.adapter)

    print("\n[2/3] Preparing MLX training data...")
    n_train, n_valid = prepare_mlx_data(args.dataset, args.mlx_data)
    print(f"  train={n_train}  valid={n_valid}  → {args.mlx_data}/")

    if args.dry_run:
        print("\n[3/3] DRY-RUN: skipping mlx-lm training")
        print("Data prepared. Run without --dry-run on Apple Silicon to train.")
        return

    print("\n[3/3] Starting MLX LoRA fine-tune (1000 iters, save every 100)...")
    run_training(args.model, args.adapter, args.mlx_data)

    print(f"\nDone. Adapter saved to {args.adapter}/")
    print("Evaluate: python eval_talent_search.py")


if __name__ == "__main__":
    main()
