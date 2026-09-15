import argparse
import json
from pathlib import Path

import cv2


def generate_violation_fixture(
    source_image: Path,
    output_video: Path,
    duration_seconds: float,
    fps: float,
    width: int,
    height: int,
) -> dict:
    if not source_image.is_file():
        raise FileNotFoundError(f"Source image does not exist: {source_image}")
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be greater than zero")
    if fps <= 0:
        raise ValueError("fps must be greater than zero")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be greater than zero")
    if output_video.exists():
        raise FileExistsError(f"Output video already exists: {output_video}")

    source = cv2.imread(str(source_image))
    if source is None:
        raise ValueError(f"Could not decode source image: {source_image}")

    output_video.parent.mkdir(parents=True, exist_ok=True)
    total_frames = round(duration_seconds * fps)
    writer = cv2.VideoWriter(
        str(output_video),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not create video: {output_video}")

    source_height, source_width = source.shape[:2]
    target_ratio = width / height
    source_ratio = source_width / source_height
    if source_ratio > target_ratio:
        crop_height = source_height
        crop_width = round(crop_height * target_ratio)
    else:
        crop_width = source_width
        crop_height = round(crop_width / target_ratio)

    try:
        for frame_index in range(total_frames):
            progress = frame_index / max(1, total_frames - 1)
            zoom = 1.0 + 0.04 * progress
            current_width = max(1, round(crop_width / zoom))
            current_height = max(1, round(crop_height / zoom))
            maximum_x = source_width - current_width
            maximum_y = source_height - current_height
            center_x = maximum_x / 2 + maximum_x * 0.08 * (progress - 0.5)
            center_y = maximum_y / 2 + maximum_y * 0.04 * (0.5 - progress)
            x1 = min(max(0, round(center_x)), maximum_x)
            y1 = min(max(0, round(center_y)), maximum_y)
            crop = source[y1 : y1 + current_height, x1 : x1 + current_width]
            frame = cv2.resize(crop, (width, height), interpolation=cv2.INTER_LINEAR)
            writer.write(frame)
    finally:
        writer.release()

    metadata = {
        "fixture_type": "derived_real_image",
        "source_image": str(source_image),
        "output_video": str(output_video),
        "duration_seconds": duration_seconds,
        "fps": fps,
        "width": width,
        "height": height,
        "total_frames": total_frames,
        "transformation": "deterministic slow zoom and pan",
        "evaluation_warning": (
            "This fixture tests pipeline integration and temporal stability. "
            "It is not a substitute for evaluation on continuous real-world video."
        ),
    }
    metadata_path = output_video.with_suffix(".json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a deterministic video fixture from a real held-out image."
    )
    parser.add_argument("--source-image", type=Path, required=True)
    parser.add_argument("--output-video", type=Path, required=True)
    parser.add_argument("--duration-seconds", type=float, default=6.0)
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=683)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata = generate_violation_fixture(
        source_image=args.source_image,
        output_video=args.output_video,
        duration_seconds=args.duration_seconds,
        fps=args.fps,
        width=args.width,
        height=args.height,
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
