import argparse
import json
from pathlib import Path

import cv2
from ultralytics import YOLO


def extract_detections(result) -> list[dict]:
    detections = []
    if result.boxes is None:
        return detections

    for box in result.boxes:
        class_id = int(box.cls.item())
        x1, y1, x2, y2 = [round(value, 2) for value in box.xyxy[0].tolist()]
        detections.append(
            {
                "class_id": class_id,
                "class_name": result.names[class_id],
                "confidence": round(float(box.conf.item()), 4),
                "box_xyxy": [x1, y1, x2, y2],
            }
        )
    return detections


def detect_image(
    input_path: Path,
    output_image_path: Path,
    output_json_path: Path,
    model_name: str,
    confidence_threshold: float,
    image_size: int,
    device: str,
) -> dict:
    if not input_path.is_file():
        raise FileNotFoundError(f"Input image does not exist: {input_path}")
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be between 0 and 1")
    if image_size <= 0:
        raise ValueError("image_size must be greater than zero")
    if output_image_path.exists() or output_json_path.exists():
        raise FileExistsError("Output image or JSON already exists; choose new output paths")

    model = YOLO(model_name)
    results = model.predict(
        source=str(input_path),
        conf=confidence_threshold,
        imgsz=image_size,
        device=device,
        verbose=False,
    )
    result = results[0]
    detections = extract_detections(result)

    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_image_path), result.plot()):
        raise RuntimeError(f"Could not write annotated image: {output_image_path}")

    prediction = {
        "source_image": str(input_path),
        "annotated_image": str(output_image_path),
        "model": model_name,
        "device": device,
        "image_size": image_size,
        "confidence_threshold": confidence_threshold,
        "original_shape": list(result.orig_shape),
        "detection_count": len(detections),
        "detections": detections,
    }
    output_json_path.write_text(json.dumps(prediction, indent=2) + "\n", encoding="utf-8")
    return prediction


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run YOLO object detection on one image.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-image", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--model", default="/data/models/yolo26n.pt")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prediction = detect_image(
        input_path=args.input,
        output_image_path=args.output_image,
        output_json_path=args.output_json,
        model_name=args.model,
        confidence_threshold=args.confidence,
        image_size=args.image_size,
        device=args.device,
    )
    print(json.dumps(prediction, indent=2))


if __name__ == "__main__":
    main()
