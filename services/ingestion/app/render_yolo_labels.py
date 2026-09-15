import argparse
import json
import random
from pathlib import Path

import cv2
import yaml


COLORS = [
    (255, 99, 71),
    (60, 179, 113),
    (30, 144, 255),
    (255, 215, 0),
    (186, 85, 211),
    (0, 206, 209),
    (255, 140, 0),
    (220, 20, 60),
    (154, 205, 50),
    (72, 61, 139),
    (255, 105, 180),
]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_dataset_config(dataset_path: Path) -> tuple[dict[int, str], dict]:
    config_path = dataset_path / "data.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(f"Dataset config does not exist: {config_path}")

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    raw_names = config.get("names")
    if isinstance(raw_names, list):
        names = {index: name for index, name in enumerate(raw_names)}
    elif isinstance(raw_names, dict):
        names = {int(class_id): str(name) for class_id, name in raw_names.items()}
    else:
        raise ValueError("data.yaml must define class names as a list or mapping")
    return names, config


def parse_labels(label_path: Path, names: dict[int, str]) -> list[dict]:
    labels = []
    for line_number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        values = line.split()
        if len(values) != 5:
            raise ValueError(f"Expected 5 values at {label_path}:{line_number}")
        class_id = int(values[0])
        if class_id not in names:
            raise ValueError(f"Unknown class {class_id} at {label_path}:{line_number}")
        center_x, center_y, width, height = map(float, values[1:])
        labels.append(
            {
                "class_id": class_id,
                "class_name": names[class_id],
                "center_x": center_x,
                "center_y": center_y,
                "width": width,
                "height": height,
            }
        )
    return labels


def collect_candidates(
    dataset_path: Path,
    split: str,
    names: dict[int, str],
    required_class_ids: set[int],
) -> list[tuple[Path, Path, list[dict]]]:
    image_directory = dataset_path / "images" / split
    label_directory = dataset_path / "labels" / split
    if not image_directory.is_dir() or not label_directory.is_dir():
        raise FileNotFoundError(f"Missing images/{split} or labels/{split} directory")

    candidates = []
    for image_path in sorted(image_directory.iterdir()):
        if image_path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        label_path = label_directory / f"{image_path.stem}.txt"
        if not label_path.is_file():
            continue
        labels = parse_labels(label_path, names)
        present_class_ids = {label["class_id"] for label in labels}
        if required_class_ids.issubset(present_class_ids):
            candidates.append((image_path, label_path, labels))
    return candidates


def draw_labels(image, labels: list[dict]) -> list[dict]:
    image_height, image_width = image.shape[:2]
    rendered_labels = []
    for label in labels:
        center_x = label["center_x"] * image_width
        center_y = label["center_y"] * image_height
        box_width = label["width"] * image_width
        box_height = label["height"] * image_height
        x1 = max(0, round(center_x - box_width / 2))
        y1 = max(0, round(center_y - box_height / 2))
        x2 = min(image_width - 1, round(center_x + box_width / 2))
        y2 = min(image_height - 1, round(center_y + box_height / 2))
        color = COLORS[label["class_id"] % len(COLORS)]
        title = f'{label["class_name"]} [{label["class_id"]}]'
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)
        (text_width, text_height), baseline = cv2.getTextSize(
            title, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
        )
        text_y = max(text_height + baseline, y1)
        cv2.rectangle(
            image,
            (x1, text_y - text_height - baseline),
            (min(image_width - 1, x1 + text_width), text_y + baseline),
            color,
            -1,
        )
        cv2.putText(
            image,
            title,
            (x1, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )
        rendered_labels.append(
            {
                "class_id": label["class_id"],
                "class_name": label["class_name"],
                "box_xyxy": [x1, y1, x2, y2],
            }
        )
    return rendered_labels


def create_contact_sheet(images: list[tuple[str, object]], columns: int = 3):
    tile_width, tile_height = 480, 360
    rows = (len(images) + columns - 1) // columns
    sheet = 255 * cv2.UMat(rows * tile_height, columns * tile_width, cv2.CV_8UC3).get()
    for index, (name, image) in enumerate(images):
        scale = min(tile_width / image.shape[1], (tile_height - 35) / image.shape[0])
        resized_width = max(1, round(image.shape[1] * scale))
        resized_height = max(1, round(image.shape[0] * scale))
        resized = cv2.resize(image, (resized_width, resized_height))
        column = index % columns
        row = index // columns
        x = column * tile_width + (tile_width - resized_width) // 2
        y = row * tile_height + 35 + (tile_height - 35 - resized_height) // 2
        sheet[y : y + resized_height, x : x + resized_width] = resized
        cv2.putText(
            sheet,
            name,
            (column * tile_width + 10, row * tile_height + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (20, 20, 20),
            2,
            cv2.LINE_AA,
        )
    return sheet


def render_samples(
    dataset_path: Path,
    split: str,
    output_directory: Path,
    sample_count: int,
    seed: int,
    required_class_ids: set[int],
) -> dict:
    if sample_count <= 0:
        raise ValueError("sample_count must be greater than zero")
    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_directory}")

    names, _ = load_dataset_config(dataset_path)
    unknown_ids = required_class_ids - names.keys()
    if unknown_ids:
        raise ValueError(f"Unknown required class IDs: {sorted(unknown_ids)}")
    candidates = collect_candidates(dataset_path, split, names, required_class_ids)
    if len(candidates) < sample_count:
        raise ValueError(f"Requested {sample_count} samples but only found {len(candidates)}")

    selected = random.Random(seed).sample(candidates, sample_count)
    selected.sort(key=lambda candidate: candidate[0].name)
    output_directory.mkdir(parents=True, exist_ok=True)
    records = []
    sheet_images = []
    for image_path, label_path, labels in selected:
        image = cv2.imread(str(image_path))
        if image is None:
            raise RuntimeError(f"Could not read image: {image_path}")
        rendered_labels = draw_labels(image, labels)
        output_path = output_directory / f"{image_path.stem}-labels.jpg"
        if not cv2.imwrite(str(output_path), image):
            raise RuntimeError(f"Could not write annotated image: {output_path}")
        sheet_images.append((image_path.name, image))
        records.append(
            {
                "source_image": str(image_path),
                "source_label": str(label_path),
                "annotated_image": str(output_path),
                "label_count": len(rendered_labels),
                "labels": rendered_labels,
            }
        )

    contact_sheet_path = output_directory / "contact-sheet.jpg"
    if not cv2.imwrite(str(contact_sheet_path), create_contact_sheet(sheet_images)):
        raise RuntimeError(f"Could not write contact sheet: {contact_sheet_path}")
    index = {
        "dataset": str(dataset_path),
        "split": split,
        "seed": seed,
        "sample_count": sample_count,
        "required_class_ids": sorted(required_class_ids),
        "required_class_names": [names[class_id] for class_id in sorted(required_class_ids)],
        "candidate_count": len(candidates),
        "contact_sheet": str(contact_sheet_path),
        "samples": records,
    }
    (output_directory / "index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    return index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render YOLO ground-truth labels for review.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "val", "test"), default="train")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--required-class-id", type=int, action="append", default=[])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = render_samples(
        dataset_path=args.dataset,
        split=args.split,
        output_directory=args.output_dir,
        sample_count=args.samples,
        seed=args.seed,
        required_class_ids=set(args.required_class_id),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
