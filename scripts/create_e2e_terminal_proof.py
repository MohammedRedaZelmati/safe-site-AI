import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path.cwd()
if not (ROOT / "compose.yaml").is_file():
    raise RuntimeError("Run this script from the SafeSite AI project root.")

OUTPUT = ROOT / "output" / "linkedin" / "dashboard-proof" / "05-e2e-streaming-test.png"
LOG_OUTPUT = ROOT / "output" / "linkedin" / "dashboard-proof" / "05-e2e-streaming-test.txt"
FONT_REGULAR = Path(r"C:\Windows\Fonts\consola.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\consolab.ttf")


def load_report(path: Path) -> dict:
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    if report.get("status") != "passed":
        raise RuntimeError(f"Refusing to render a success proof from a non-passed report: {path}")
    assertions = report.get("assertions", [])
    failed = [assertion for assertion in assertions if not assertion.get("passed")]
    if failed:
        raise RuntimeError(f"Refusing to render proof because {len(failed)} assertion(s) failed.")
    return report


def shorten(text: str, maximum: int = 112) -> str:
    return text if len(text) <= maximum else f"{text[:maximum - 3]}..."


def render_terminal(report: dict, report_path: Path) -> None:
    width = 1900
    margin_x = 44
    margin_y = 34
    line_height = 34
    font = ImageFont.truetype(str(FONT_REGULAR), 24)
    bold_font = ImageFont.truetype(str(FONT_BOLD), 25)
    small_font = ImageFont.truetype(str(FONT_REGULAR), 21)

    assertions = report["assertions"]
    passed_count = sum(1 for assertion in assertions if assertion["passed"])
    failed_count = len(assertions) - passed_count

    lines = [
        ("PS C:\\Users\\LEGION\\Documents\\safe site ai> .\\scripts\\test_streaming_e2e.ps1 -FrameCount 10", "command"),
        ("", "normal"),
        ("SafeSite AI - full streaming pipeline end-to-end", "title"),
        (f"Run ID: {report['run_id']} | Camera: {report['camera_id']}", "muted"),
        ("Scope: Kafka, MinIO, YOLO inference, tracking, FastAPI, PostgreSQL, duplicate protection", "muted"),
        ("", "normal"),
    ]

    for assertion in assertions:
        name = shorten(assertion["name"], 38)
        expected = shorten(str(assertion["expected"]), 34)
        actual = shorten(str(assertion["actual"]), 42)
        lines.append((f"[PASS] {name:<38} expected: {expected:<34} actual: {actual}", "success"))

    lines.extend(
        [
            ("", "normal"),
            ("-" * 132, "muted"),
            (f"E2E RESULT: PASSED | Assertions: {passed_count} passed, {failed_count} failed", "ok"),
            (f"Duration: {report['duration_seconds']:.2f} seconds", "summary"),
            (f"Report: {report_path}", "muted"),
        ]
    )

    height = margin_y * 2 + line_height * len(lines) + 24
    image = Image.new("RGB", (width, height), "#0c0f14")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 8), fill="#22c55e")

    palette = {
        "command": "#e5e7eb",
        "title": "#f8fafc",
        "muted": "#94a3b8",
        "normal": "#e5e7eb",
        "success": "#d1fae5",
        "summary": "#f8fafc",
        "ok": "#4ade80",
    }

    y = margin_y
    for text, role in lines:
        selected_font = bold_font if role in {"title", "summary", "ok"} else font
        if role == "muted":
            selected_font = small_font
        draw.text((margin_x, y), text, font=selected_font, fill=palette[role])
        y += line_height

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT, optimize=True)
    LOG_OUTPUT.write_text("\n".join(line for line, _ in lines) + "\n", encoding="utf-8")
    print(OUTPUT)
    print(LOG_OUTPUT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    render_terminal(load_report(args.report), args.report)


if __name__ == "__main__":
    main()
