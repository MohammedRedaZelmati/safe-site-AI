import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def generate_demo_video(
    output_path: Path,
    duration_seconds: float,
    fps: float,
    width: int,
    height: int,
) -> dict[str, int | float | str]:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be greater than zero")
    if fps <= 0:
        raise ValueError("fps must be greater than zero")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be greater than zero")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_frames = round(duration_seconds * fps)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not create video: {output_path}")

    try:
        for frame_index in range(total_frames):
            timestamp_seconds = frame_index / fps
            frame = np.full((height, width, 3), (235, 218, 185), dtype=np.uint8)

            ground_y = int(height * 0.72)
            cv2.rectangle(frame, (0, ground_y), (width, height), (80, 92, 105), -1)
            cv2.line(frame, (0, ground_y), (width, ground_y), (35, 45, 55), 3)

            crane_x = int(width * 0.78)
            cv2.rectangle(frame, (crane_x, int(height * 0.12)), (crane_x + 12, ground_y), (45, 155, 220), -1)
            cv2.line(frame, (crane_x, int(height * 0.14)), (int(width * 0.96), int(height * 0.14)), (45, 155, 220), 9)
            cv2.line(frame, (int(width * 0.92), int(height * 0.14)), (int(width * 0.92), int(height * 0.43)), (40, 40, 40), 2)

            travel = max(1, width - 170)
            worker_x = 70 + int((timestamp_seconds / duration_seconds) * travel)
            head_y = ground_y - 105
            cv2.circle(frame, (worker_x, head_y), 18, (120, 175, 220), -1)
            cv2.ellipse(frame, (worker_x, head_y - 11), (23, 10), 0, 180, 360, (25, 215, 245), -1)
            cv2.rectangle(frame, (worker_x - 22, head_y + 18), (worker_x + 22, ground_y - 18), (35, 130, 240), -1)
            cv2.rectangle(frame, (worker_x - 19, head_y + 35), (worker_x + 19, head_y + 62), (40, 220, 245), -1)
            cv2.line(frame, (worker_x - 10, ground_y - 18), (worker_x - 15, ground_y), (25, 25, 25), 6)
            cv2.line(frame, (worker_x + 10, ground_y - 18), (worker_x + 15, ground_y), (25, 25, 25), 6)

            cv2.putText(
                frame,
                f"SafeSite demo | frame={frame_index:03d} | t={timestamp_seconds:05.2f}s",
                (18, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (15, 35, 55),
                2,
                cv2.LINE_AA,
            )
            writer.write(frame)
    finally:
        writer.release()

    return {
        "output_path": str(output_path),
        "duration_seconds": duration_seconds,
        "fps": fps,
        "width": width,
        "height": height,
        "total_frames": total_frames,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a small synthetic SafeSite AI demo video.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration-seconds", type=float, default=6.0)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = generate_demo_video(
        output_path=args.output,
        duration_seconds=args.duration_seconds,
        fps=args.fps,
        width=args.width,
        height=args.height,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

