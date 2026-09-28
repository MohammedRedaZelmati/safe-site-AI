import os
from pathlib import Path
import re
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont


ROOT = Path.cwd()
if not (ROOT / "compose.yaml").is_file():
    raise RuntimeError("Run this script from the SafeSite AI project root.")
OUTPUT = ROOT / "output" / "linkedin" / "dashboard-proof" / "04-tests.png"
LOG_OUTPUT = ROOT / "output" / "linkedin" / "dashboard-proof" / "04-tests.txt"
TEMP_ROOT = Path(r"D:\SafeSiteStorage\safe-site-ai\tmp\portfolio-tests")
FONT_REGULAR = Path(r"C:\Windows\Fonts\consola.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\consolab.ttf")


SUITES = (
    (
        "Grounded AI assistant",
        ROOT / "services" / "agent",
        ROOT / "services" / "agent" / ".venv" / "Scripts" / "python.exe",
        ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
    ),
    (
        "MLflow model comparison",
        ROOT / "services" / "mlops",
        ROOT / "services" / "mlops" / ".venv" / "Scripts" / "python.exe",
        ["-m", "unittest", "test_compare_ppe_runs.py", "-v"],
    ),
    (
        "Monitoring and data quality",
        ROOT / "services" / "monitoring",
        ROOT / "services" / "monitoring" / ".venv" / "Scripts" / "python.exe",
        ["-m", "unittest", "test_analyze_drift.py", "test_validate_events.py", "-v"],
    ),
)


def run_tests() -> tuple[list[tuple[str, str]], float]:
    environment = os.environ.copy()
    environment["TEMP"] = str(TEMP_ROOT)
    environment["TMP"] = str(TEMP_ROOT)
    environment["PYTHONPYCACHEPREFIX"] = str(TEMP_ROOT / "pycache")
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)

    started_at = time.perf_counter()
    results = []
    failures = []
    for suite_name, working_directory, python, arguments in SUITES:
        completed = subprocess.run(
            [str(python), *arguments],
            cwd=working_directory,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        combined_output = f"{completed.stdout}\n{completed.stderr}"
        test_names = re.findall(r"^(test_.+?) \.\.\.", combined_output, re.MULTILINE)
        for test_name in test_names:
            results.append((f"[{suite_name}] {test_name}", "ok"))
        if completed.returncode:
            failures.append(f"{suite_name} exited with status {completed.returncode}")

    elapsed = time.perf_counter() - started_at
    if failures:
        raise RuntimeError("; ".join(failures))
    if len(results) != 14 or any(status != "ok" for _, status in results):
        raise RuntimeError(f"Expected 14 passing tests, observed {len(results)} results")
    return results, elapsed


def shorten_test_name(value: str, maximum: int = 126) -> str:
    return value if len(value) <= maximum else f"{value[:maximum - 3]}..."


def render_terminal(results: list[tuple[str, str]], elapsed: float):
    width = 1800
    margin_x = 42
    margin_y = 34
    font = ImageFont.truetype(str(FONT_REGULAR), 24)
    bold_font = ImageFont.truetype(str(FONT_BOLD), 25)
    small_font = ImageFont.truetype(str(FONT_REGULAR), 21)
    line_height = 34

    lines = [
        ("PS C:\\Users\\LEGION\\Documents\\safe site ai> python scripts\\create_test_terminal_proof.py", "command"),
        ("", "normal"),
        ("SafeSite AI — automated verification", "title"),
        ("Running grounded-agent, MLOps, monitoring, and data-quality test suites...", "muted"),
        ("", "normal"),
    ]
    lines.extend((f"{shorten_test_name(name)} ... {status}", "success") for name, status in results)
    lines.extend(
        [
            ("", "normal"),
            ("─" * 112, "muted"),
            (f"Ran {len(results)} tests in {elapsed:.3f}s", "summary"),
            ("", "normal"),
            ("OK — 14 passed, 0 failed", "ok"),
        ]
    )

    height = margin_y * 2 + line_height * len(lines) + 22
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
    current_y = margin_y
    for text, role in lines:
        selected_font = bold_font if role in {"title", "summary", "ok"} else font
        if role == "muted":
            selected_font = small_font
        draw.text((margin_x, current_y), text, font=selected_font, fill=palette[role])
        current_y += line_height

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT, optimize=True)

    log_lines = [line for line, _ in lines]
    LOG_OUTPUT.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(OUTPUT)
    print(LOG_OUTPUT)


def main():
    results, elapsed = run_tests()
    render_terminal(results, elapsed)


if __name__ == "__main__":
    main()
