import hashlib
import json
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE_VIDEO = ROOT / "data" / "videos" / "external" / "pexels-32244795.mp4"
OUTPUT_DIR = ROOT / "data" / "final-demo" / "real-pexels-32244795"
FRAMES_DIR = OUTPUT_DIR / "frames"
EVIDENCE_FRAME = FRAMES_DIR / "frame_004_t2000ms.jpg"
PROOF_IMAGE = OUTPUT_DIR / "proof-no-vest.jpg"
SUMMARY = ROOT / "data" / "final-demo" / "summary.json"
SOURCE_PAGE = "https://www.pexels.com/video/construction-workers-inspecting-building-site-scaffolding-32244795/"
LICENSE_URL = "https://www.pexels.com/license/"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_font(name: str, size: int):
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def extract_evidence_frame() -> None:
    if not SOURCE_VIDEO.is_file():
        raise FileNotFoundError(
            f"Missing real Pexels video: {SOURCE_VIDEO}. Download and validate it first."
        )
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(SOURCE_VIDEO))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {SOURCE_VIDEO}")
    capture.set(cv2.CAP_PROP_POS_MSEC, 2000)
    success, frame = capture.read()
    capture.release()
    if not success:
        raise RuntimeError("Could not read the evidence frame at 2.0 seconds")
    if not cv2.imwrite(str(EVIDENCE_FRAME), frame):
        raise RuntimeError(f"Could not write evidence frame: {EVIDENCE_FRAME}")


def annotate_no_vest_evidence() -> None:
    image = Image.open(EVIDENCE_FRAME).convert("RGB")
    draw = ImageDraw.Draw(image)
    font_big = load_font("arialbd.ttf", 42)
    font_mid = load_font("arialbd.ttf", 30)
    font_small = load_font("arial.ttf", 24)

    worker_box = (915, 755, 1148, 1328)
    red = (239, 68, 68)
    yellow = (250, 204, 21)
    dark = (15, 23, 42)
    white = (255, 255, 255)

    for offset in range(6):
        draw.rectangle(
            [
                worker_box[0] - offset,
                worker_box[1] - offset,
                worker_box[2] + offset,
                worker_box[3] + offset,
            ],
            outline=red,
        )

    label = "NO SAFETY VEST"
    label_bounds = draw.textbbox((0, 0), label, font=font_big)
    label_width = label_bounds[2] - label_bounds[0]
    label_height = label_bounds[3] - label_bounds[1]
    banner_top = max(20, worker_box[1] - label_height - 26)
    banner = (
        worker_box[0],
        banner_top,
        worker_box[0] + label_width + 32,
        banner_top + label_height + 22,
    )
    draw.rounded_rectangle(banner, radius=10, fill=red)
    draw.text((banner[0] + 16, banner[1] + 8), label, fill=white, font=font_big)

    note = "Helmet present, safety vest missing"
    note_bounds = draw.textbbox((0, 0), note, font=font_mid)
    note_banner = (
        worker_box[0],
        worker_box[3] + 14,
        worker_box[0] + note_bounds[2] - note_bounds[0] + 28,
        worker_box[3] + 60,
    )
    draw.rounded_rectangle(note_banner, radius=8, fill=dark)
    draw.text((note_banner[0] + 14, note_banner[1] + 8), note, fill=yellow, font=font_mid)

    metadata = "Real Pexels construction video | Evidence frame: 00:02.0 | Violation: No vest"
    draw.rounded_rectangle((28, 26, 1120, 82), radius=12, fill=dark)
    draw.text((48, 39), metadata, fill=white, font=font_small)
    image.save(PROOF_IMAGE, quality=94)


def write_summary() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "demo_name": "SafeSite final real-video PPE violation evidence",
        "source_page": SOURCE_PAGE,
        "license_url": LICENSE_URL,
        "source_video": str(SOURCE_VIDEO.relative_to(ROOT)).replace("\\", "/"),
        "evidence_frame": str(EVIDENCE_FRAME.relative_to(ROOT)).replace("\\", "/"),
        "proof_image": str(PROOF_IMAGE.relative_to(ROOT)).replace("\\", "/"),
        "video_timestamp_seconds": 2.0,
        "violation_type": "NO_VEST",
        "violation_label": "No safety vest",
        "decision": "Human review required",
        "evidence_note": "The worker on the left has a hard hat but no high-visibility safety vest.",
        "review_confidence_label": "High",
        "model_precision": 0.544006,
        "model_recall": 0.754386,
        "model_map50": 0.713113,
        "metric_class": "vest",
        "source_video_sha256": sha256(SOURCE_VIDEO),
        "important_limitation": (
            "This final screen is a professional evidence view from a real Pexels "
            "construction video. The no-vest decision is visual-review evidence; "
            "model metrics shown are the trained vest class evaluation metrics."
        ),
    }
    SUMMARY.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


def main() -> None:
    extract_evidence_frame()
    annotate_no_vest_evidence()
    write_summary()


if __name__ == "__main__":
    main()
