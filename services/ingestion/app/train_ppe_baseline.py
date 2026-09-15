import argparse
import json
import tempfile
from pathlib import Path

import torch
import yaml
from ultralytics import YOLO


def load_dataset_config(dataset_path: Path) -> dict:
    config_path = dataset_path / "data.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(f"Dataset config does not exist: {config_path}")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    for key in ("train", "val", "names"):
        if key not in config:
            raise ValueError(f"Dataset config is missing '{key}'")
    return config


def create_absolute_dataset_config(dataset_path: Path, config: dict) -> Path:
    runtime_config = {
        "path": str(dataset_path.resolve()),
        "train": config["train"],
        "val": config["val"],
        "names": config["names"],
    }
    if "test" in config:
        runtime_config["test"] = config["test"]

    temporary_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        prefix="safesite-ppe-",
        encoding="utf-8",
        delete=False,
    )
    with temporary_file:
        yaml.safe_dump(runtime_config, temporary_file, sort_keys=False)
    return Path(temporary_file.name)


def serializable_metrics(metrics) -> dict[str, float]:
    values = {}
    for name, value in metrics.results_dict.items():
        try:
            values[name] = round(float(value), 6)
        except (TypeError, ValueError):
            continue
    return values


def train_baseline(
    dataset_path: Path,
    model_path: Path,
    output_root: Path,
    run_name: str,
    epochs: int,
    image_size: int,
    batch_size: int,
    device: str,
    workers: int,
    seed: int,
    fraction: float,
) -> dict:
    if not model_path.is_file():
        raise FileNotFoundError(f"Model does not exist: {model_path}")
    if epochs <= 0 or image_size <= 0 or batch_size <= 0 or workers < 0:
        raise ValueError("epochs, image_size, and batch_size must be positive; workers cannot be negative")
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be greater than zero and at most one")

    run_directory = output_root / run_name
    if run_directory.exists():
        raise FileExistsError(f"Training run already exists: {run_directory}")

    dataset_config = load_dataset_config(dataset_path)
    runtime_config_path = create_absolute_dataset_config(dataset_path, dataset_config)
    try:
        model = YOLO(str(model_path))
        metrics = model.train(
            data=str(runtime_config_path),
            project=str(output_root),
            name=run_name,
            epochs=epochs,
            imgsz=image_size,
            batch=batch_size,
            device=device,
            workers=workers,
            seed=seed,
            fraction=fraction,
            deterministic=True,
            plots=True,
            val=True,
            save=True,
            exist_ok=False,
            verbose=True,
        )
    finally:
        runtime_config_path.unlink(missing_ok=True)

    summary = {
        "dataset": str(dataset_path),
        "model": str(model_path),
        "output_directory": str(run_directory),
        "epochs": epochs,
        "image_size": image_size,
        "batch_size": batch_size,
        "device": device,
        "workers": workers,
        "seed": seed,
        "fraction": fraction,
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "metrics": serializable_metrics(metrics),
    }
    (run_directory / "safesite-run.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a reproducible SafeSite PPE baseline.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("/data/models/yolo26n.pt"))
    parser.add_argument("--output-root", type=Path, default=Path("/data/training"))
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--image-size", type=int, default=320)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fraction", type=float, default=0.1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = train_baseline(
        dataset_path=args.dataset,
        model_path=args.model,
        output_root=args.output_root,
        run_name=args.run_name,
        epochs=args.epochs,
        image_size=args.image_size,
        batch_size=args.batch_size,
        device=args.device,
        workers=args.workers,
        seed=args.seed,
        fraction=args.fraction,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
