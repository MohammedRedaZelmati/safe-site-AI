import argparse
import json
from pathlib import Path

import cv2


def resolve_data_path(value: str, data_root: Path) -> Path:
    if value.startswith("/data/"):
        return data_root / value.removeprefix("/data/")
    return Path(value)


def count_labels(samples: list[dict], class_name: str) -> int:
    return sum(
        1
        for sample in samples
        for label in sample.get("labels", [])
        if label.get("class_name") == class_name
    )


def fit_on_canvas(image, width: int, height: int):
    canvas = 255 * cv2.UMat(height, width, cv2.CV_8UC3).get()
    scale = min(width / image.shape[1], (height - 70) / image.shape[0])
    resized_width = max(1, round(image.shape[1] * scale))
    resized_height = max(1, round(image.shape[0] * scale))
    resized = cv2.resize(image, (resized_width, resized_height))
    x = (width - resized_width) // 2
    y = 70 + (height - 70 - resized_height) // 2
    canvas[y : y + resized_height, x : x + resized_width] = resized
    return canvas


def write_title(image, title: str, subtitle: str) -> None:
    cv2.rectangle(image, (0, 0), (image.shape[1], 62), (20, 24, 33), -1)
    cv2.putText(
        image,
        title,
        (24, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        image,
        subtitle,
        (24, 54),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )


def build_review_reel(
    index_path: Path,
    output_dir: Path,
    data_root: Path,
    fps: int,
    seconds_per_sample: int,
    width: int,
    height: int,
    sample_stems: set[str],
) -> dict:
    if not index_path.is_file():
        raise FileNotFoundError(f"Missing index file: {index_path}")
    if fps <= 0:
        raise ValueError("fps must be greater than zero")
    if seconds_per_sample <= 0:
        raise ValueError("seconds_per_sample must be greater than zero")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be greater than zero")

    index = json.loads(index_path.read_text(encoding="utf-8"))
    samples = index.get("samples", [])
    if sample_stems:
        samples = [
            sample
            for sample in samples
            if Path(sample.get("source_image", "")).stem in sample_stems
        ]
    if not samples:
        raise ValueError("No samples found in index")

    output_dir.mkdir(parents=True, exist_ok=True)
    video_path = output_dir / "no-helmet-ground-truth-review.mp4"
    summary_path = output_dir / "summary.json"
    first_frame_path = output_dir / "first-frame.jpg"

    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not create video: {video_path}")

    frame_count = 0
    first_frame_written = False
    sample_records = []
    for sample_index, sample in enumerate(samples, start=1):
        annotated_path = resolve_data_path(sample["annotated_image"], data_root)
        image = cv2.imread(str(annotated_path))
        if image is None:
            raise RuntimeError(f"Could not read annotated image: {annotated_path}")
        frame = fit_on_canvas(image, width, height)
        no_helmet_count = sum(
            1 for label in sample.get("labels", []) if label.get("class_name") == "no_helmet"
        )
        write_title(
            frame,
            f"Ground truth no_helmet sample {sample_index}/{len(samples)}",
            f"{Path(sample['source_image']).name} - labelled no_helmet boxes: {no_helmet_count}",
        )
        for _ in range(fps * seconds_per_sample):
            writer.write(frame)
            frame_count += 1
        if not first_frame_written:
            if not cv2.imwrite(str(first_frame_path), frame):
                raise RuntimeError(f"Could not write first frame: {first_frame_path}")
            first_frame_written = True
        sample_records.append(
            {
                "source_image": sample["source_image"],
                "annotated_image": sample["annotated_image"],
                "label_count": sample.get("label_count", 0),
                "no_helmet_boxes": no_helmet_count,
            }
        )

    writer.release()
    contact_sheet = resolve_data_path(index["contact_sheet"], data_root)
    summary = {
        "source": "Ultralytics Construction-PPE labelled training images",
        "source_index": str(index_path),
        "selected_sample_stems": sorted(sample_stems),
        "review_video": str(video_path),
        "first_frame": str(first_frame_path),
        "contact_sheet": str(contact_sheet),
        "class_under_review": "no_helmet",
        "sample_count": len(samples),
        "candidate_count": index.get("candidate_count"),
        "labelled_no_helmet_boxes": count_labels(samples, "no_helmet"),
        "fps": fps,
        "seconds_per_sample": seconds_per_sample,
        "frame_count": frame_count,
        "duration_seconds": frame_count / fps,
        "samples": sample_records,
        "important_limitation": (
            "This is a review reel made from real labelled images, not a continuous camera video. "
            "It proves labelled violation examples exist and can be reviewed visually."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a labelled PPE violation review reel.")
    parser.add_argument(
        "--index",
        type=Path,
        default=Path("data/datasets/reports/construction-ppe-visual/no-helmet/index.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/evaluation/no-helmet-review"),
    )
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--fps", type=int, default=5)
    parser.add_argument("--seconds-per-sample", type=int, default=2)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--sample-stem", action="append", default=[])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build_review_reel(
        index_path=args.index,
        output_dir=args.output_dir,
        data_root=args.data_root,
        fps=args.fps,
        seconds_per_sample=args.seconds_per_sample,
        width=args.width,
        height=args.height,
        sample_stems=set(args.sample_stem),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
