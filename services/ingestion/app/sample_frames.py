import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2


@dataclass(frozen=True)
class VideoMetadata:
    source_path: str
    fps: float
    frame_count: int
    width: int
    height: int
    duration_seconds: float


@dataclass(frozen=True)
class SampledFrame:
    camera_id: str
    sample_index: int
    source_frame_index: int
    video_timestamp_ms: int
    source_fps: float
    image_path: str


def read_metadata(video_path: Path) -> VideoMetadata:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()

    if fps <= 0:
        raise ValueError(f"Video reports an invalid FPS value: {fps}")

    return VideoMetadata(
        source_path=str(video_path),
        fps=fps,
        frame_count=frame_count,
        width=width,
        height=height,
        duration_seconds=frame_count / fps,
    )


def sample_frames(
    video_path: Path,
    output_dir: Path,
    target_fps: float,
    camera_id: str,
    max_seconds: float | None = None,
) -> tuple[VideoMetadata, list[SampledFrame]]:
    metadata = read_metadata(video_path)
    if target_fps <= 0:
        raise ValueError("target_fps must be greater than zero")
    if target_fps > metadata.fps:
        raise ValueError("target_fps cannot be greater than the source FPS")
    if max_seconds is not None and max_seconds <= 0:
        raise ValueError("max_seconds must be greater than zero")

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "frames.jsonl"
    if manifest_path.exists() or any(output_dir.glob("frame_*.jpg")):
        raise FileExistsError(f"Output directory already contains sampled frames: {output_dir}")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    sampled_frames: list[SampledFrame] = []
    sample_period_seconds = 1.0 / target_fps
    next_sample_seconds = 0.0
    frame_index = 0

    try:
        with manifest_path.open("w", encoding="utf-8") as manifest:
            while True:
                success, frame = capture.read()
                if not success:
                    break

                timestamp_seconds = frame_index / metadata.fps
                if max_seconds is not None and timestamp_seconds >= max_seconds:
                    break

                if timestamp_seconds + 1e-9 >= next_sample_seconds:
                    timestamp_ms = round(timestamp_seconds * 1000)
                    image_name = f"frame_{len(sampled_frames):06d}_t{timestamp_ms:09d}ms.jpg"
                    image_path = output_dir / image_name
                    if not cv2.imwrite(str(image_path), frame):
                        raise RuntimeError(f"Could not write sampled frame: {image_path}")

                    sampled_frame = SampledFrame(
                        camera_id=camera_id,
                        sample_index=len(sampled_frames),
                        source_frame_index=frame_index,
                        video_timestamp_ms=timestamp_ms,
                        source_fps=metadata.fps,
                        image_path=str(image_path),
                    )
                    sampled_frames.append(sampled_frame)
                    manifest.write(json.dumps(asdict(sampled_frame)) + "\n")
                    next_sample_seconds += sample_period_seconds

                frame_index += 1
    finally:
        capture.release()

    return metadata, sampled_frames


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample timestamped JPEG frames from a video.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target-fps", type=float, default=5.0)
    parser.add_argument("--camera-id", default="camera-demo")
    parser.add_argument("--max-seconds", type=float)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata, sampled = sample_frames(
        video_path=args.input,
        output_dir=args.output_dir,
        target_fps=args.target_fps,
        camera_id=args.camera_id,
        max_seconds=args.max_seconds,
    )
    print(
        json.dumps(
            {
                "video": asdict(metadata),
                "target_fps": args.target_fps,
                "saved_frames": len(sampled),
                "manifest": str(args.output_dir / "frames.jsonl"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

