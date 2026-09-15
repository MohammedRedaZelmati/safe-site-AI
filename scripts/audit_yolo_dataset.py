import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
SPLITS = ("train", "val", "test")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def label_directory(image_directory: Path) -> Path:
    parts = list(image_directory.parts)
    try:
        images_index = parts.index("images")
    except ValueError as error:
        raise ValueError(f"Split path must contain an images directory: {image_directory}") from error
    parts[images_index] = "labels"
    return Path(*parts)


def load_config(config_path: Path) -> tuple[dict[str, str], dict[int, str]]:
    split_paths = {}
    class_names = {}
    reading_names = False
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        content = raw_line.split("#", maxsplit=1)[0].rstrip()
        if not content:
            continue
        if content == "names:":
            reading_names = True
            continue
        if reading_names and content[:1].isspace():
            class_id_text, class_name = content.strip().split(":", maxsplit=1)
            class_names[int(class_id_text)] = class_name.strip().strip("'\"")
            continue
        reading_names = False
        key, separator, value = content.partition(":")
        if separator and key in SPLITS:
            split_paths[key] = value.strip().strip("'\"")

    missing_splits = set(SPLITS) - split_paths.keys()
    if missing_splits:
        raise ValueError(f"Dataset YAML is missing splits: {sorted(missing_splits)}")
    if not class_names:
        raise ValueError("Dataset YAML contains no block-style class names")
    return split_paths, class_names


def audit_labels(
    labels: list[Path], class_names: dict[int, str]
) -> tuple[dict, list[str], list[str]]:
    class_instances = Counter()
    images_per_class = Counter()
    malformed_labels = []
    invalid_boxes = []
    total_boxes = 0

    for label_path in labels:
        classes_in_image = set()
        for line_number, line in enumerate(
            label_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            fields = line.split()
            if len(fields) != 5:
                malformed_labels.append(f"{label_path}:{line_number}")
                continue
            try:
                class_id = int(fields[0])
                x_center, y_center, width, height = map(float, fields[1:])
            except ValueError:
                malformed_labels.append(f"{label_path}:{line_number}")
                continue

            coordinates = (x_center, y_center, width, height)
            valid_box = (
                class_id in class_names
                and all(math.isfinite(value) for value in coordinates)
                and 0 <= x_center <= 1
                and 0 <= y_center <= 1
                and 0 < width <= 1
                and 0 < height <= 1
            )
            if not valid_box:
                invalid_boxes.append(f"{label_path}:{line_number}")
            class_instances[class_id] += 1
            classes_in_image.add(class_id)
            total_boxes += 1
        images_per_class.update(classes_in_image)

    statistics = {
        "boxes": total_boxes,
        "class_instances": {
            class_names[class_id]: class_instances[class_id] for class_id in class_names
        },
        "images_per_class": {
            class_names[class_id]: images_per_class[class_id] for class_id in class_names
        },
    }
    return statistics, malformed_labels, invalid_boxes


def audit_dataset(dataset_dir: Path) -> dict:
    config_path = dataset_dir / "data.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(f"Dataset configuration does not exist: {config_path}")
    split_paths, class_names = load_config(config_path)
    image_hashes = defaultdict(list)
    split_reports = {}

    for split in SPLITS:
        image_directory = dataset_dir / split_paths[split]
        labels_directory = label_directory(image_directory)
        images = sorted(
            path
            for path in image_directory.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
        labels = sorted(labels_directory.glob("*.txt"))
        image_stems = {path.stem for path in images}
        label_stems = {path.stem for path in labels}
        statistics, malformed_labels, invalid_boxes = audit_labels(labels, class_names)

        for image_path in images:
            image_hashes[sha256(image_path)].append(
                {"split": split, "image": image_path.name}
            )

        split_reports[split] = {
            "images": len(images),
            "labels": len(labels),
            "missing_labels": sorted(image_stems - label_stems),
            "orphan_labels": sorted(label_stems - image_stems),
            "malformed_labels": malformed_labels,
            "invalid_boxes": invalid_boxes,
            **statistics,
        }

    duplicate_groups = [
        members
        for members in image_hashes.values()
        if len({member["split"] for member in members}) > 1
    ]
    return {
        "dataset": str(dataset_dir),
        "config": str(config_path),
        "class_names": class_names,
        "splits": split_reports,
        "exact_cross_split_duplicate_groups": duplicate_groups,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit YOLO image-label pairing, boxes, classes, and split duplicates."
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = audit_dataset(args.dataset)
    rendered_report = json.dumps(report, indent=2)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered_report + "\n", encoding="utf-8")
    print(rendered_report)


if __name__ == "__main__":
    main()
