from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "SafeSite_AI_File_Catalog.pdf"

SECTIONS = [
    (
        "Root configuration",
        [
            (
                ".gitattributes",
                "Marks generated PDFs, images, videos, and model weights as binary Git artifacts.",
                "Prevents line-ending conversion, whitespace checks, and unreadable text diffs for binary files.",
                "Added binary rules for PDF, image, video, and PyTorch model artifacts.",
            ),
            (
                ".env.example",
                "Documents the environment variables required by PostgreSQL and FastAPI.",
                "Lets developers create a local .env file without committing real credentials.",
                "Initial database name, user, password, and connection URL added.",
            ),
            (
                ".gitignore",
                "Excludes local, generated, cached, secret, and heavy files from Git.",
                "Keeps commits focused on maintained source files.",
                "Initial Python, editor, data, model, MLflow, and temporary-file exclusions added.",
            ),
            (
                "README.md",
                "Provides the project overview, startup commands, learning links, and working rules.",
                "Acts as the main entry point for every developer and reviewer.",
                "Added the Day 3 video lesson and reproducible ingestion exercise commands.",
            ),
            (
                "compose.yaml",
                "Defines and connects the PostgreSQL and FastAPI containers.",
                "Starts the current system reproducibly and preserves database data in a volume.",
                "Added the optional ingestion tools profile with a bind-mounted data workspace.",
            ),
        ],
    ),
    (
        "Database",
        [
            (
                "database/init/001_schema.sql",
                "Creates the violations table, constraints, indexes, and fake seed events.",
                "Establishes the structured event contract inside PostgreSQL.",
                "Initial camera, track, violation, confidence, evidence, and timestamp fields added.",
            ),
        ],
    ),
    (
        "API container",
        [
            (
                "services/api/Dockerfile",
                "Builds the container image that runs the FastAPI application.",
                "Packages Python, dependencies, source code, and the startup command reproducibly.",
                "Split the image into reusable base, runtime, and test build stages.",
            ),
            (
                "services/api/requirements.txt",
                "Declares the Python dependencies required by the API.",
                "Makes dependency installation repeatable in the container.",
                "FastAPI, Uvicorn, Psycopg, pool, and settings dependencies added.",
            ),
            (
                "services/api/requirements-dev.txt",
                "Declares dependencies used only by automated API tests.",
                "Keeps Pytest and HTTPX separate from the production runtime image.",
                "Added Pytest and HTTPX for black-box integration testing.",
            ),
        ],
    ),
    (
        "API application",
        [
            (
                "services/api/app/__init__.py",
                "Marks the app directory as a Python package.",
                "Makes imports such as app.main and app.schemas predictable.",
                "Initial package marker added.",
            ),
            (
                "services/api/app/config.py",
                "Loads the PostgreSQL connection URL from environment configuration.",
                "Separates deployment configuration from application logic.",
                "Initial Pydantic settings model and development default added.",
            ),
            (
                "services/api/app/database.py",
                "Creates and manages the asynchronous PostgreSQL connection pool.",
                "Reuses connections efficiently and manages them with the API lifecycle.",
                "Initial dictionary-row pool, startup wait, and shutdown functions added.",
            ),
            (
                "services/api/app/schemas.py",
                "Defines Pydantic request and response contracts for violations and statistics.",
                "Validates JSON fields, types, ranges, and allowed violation values.",
                "Initial creation, response, count, summary, and violation-type models added.",
            ),
            (
                "services/api/app/main.py",
                "Defines the FastAPI application lifecycle and HTTP routes.",
                "Exposes health, create, list, filter, and summary operations over PostgreSQL.",
                "Added inclusive occurrence-time filters and reversed-range validation.",
            ),
        ],
    ),
    (
        "API tests",
        [
            (
                "services/api/tests/test_time_filters.py",
                "Tests time filtering, invalid ranges, and SQL-injection resistance against the running stack.",
                "Proves that HTTP, validation, SQL, and PostgreSQL work correctly together.",
                "Added three integration tests with automatic test-data cleanup.",
            ),
        ],
    ),
    (
        "Ingestion container",
        [
            (
                "services/ingestion/Dockerfile",
                "Builds the reproducible OpenCV environment for video-ingestion tools.",
                "Gives every developer the same Python, decoder, and image-processing runtime.",
                "Added the Python 3.12 image, OpenCV installation, application copy, and help command.",
            ),
            (
                "services/ingestion/requirements.txt",
                "Declares the ingestion service's OpenCV dependency.",
                "Makes video decoding, generation, and image writing reproducible inside Docker.",
                "Added the supported OpenCV headless version range.",
            ),
        ],
    ),
    (
        "Ingestion application",
        [
            (
                "services/ingestion/app/__init__.py",
                "Marks the ingestion app directory as a Python package.",
                "Allows tools to run consistently with python -m app.<module>.",
                "Initial package marker added.",
            ),
            (
                "services/ingestion/app/generate_demo_video.py",
                "Generates a controlled MP4 with known timing, resolution, and frame count.",
                "Provides deterministic input without relying on personal or downloaded footage.",
                "Added configurable generation and a moving PPE-equipped worker scene.",
            ),
            (
                "services/ingestion/app/sample_frames.py",
                "Samples video frames by time and writes JPEG evidence plus JSONL metadata.",
                "Establishes the ingestion contract later consumed by Kafka, MinIO, and YOLO.",
                "Added validation, time-based sampling, traceable names, and metadata records.",
            ),
        ],
    ),
    (
        "Learning documentation",
        [
            (
                "docs/ARCHITECTURE.md",
                "Explains the architecture by following one PPE violation event.",
                "Builds a mental model connecting every planned system layer.",
                "Initial current and weekly architecture stages documented.",
            ),
            (
                "docs/LESSON_01.md",
                "Contains the first guided lesson and practical exercises.",
                "Teaches Docker, networking, validation, persistence, and event flow.",
                "Initial Day 1 exercises and explanation checkpoint added.",
            ),
            (
                "docs/LESSON_02.md",
                "Contains the second guided lesson and implementation exercise.",
                "Teaches HTTP, async waiting, pooling, safe SQL, time filters, and tests.",
                "Initial Day 2 lesson and explanation checkpoint added.",
            ),
            (
                "docs/LESSON_03.md",
                "Contains the video-fundamentals lesson and frame-sampling exercise.",
                "Teaches FPS, resolution, codecs, timestamps, sampling, and JSONL metadata.",
                "Added the Day 3 lesson, Docker commands, contract, and checkpoint.",
            ),
            (
                "docs/ROADMAP.md",
                "Defines the realistic 28-day learning and implementation plan.",
                "Protects the deadline using must-have, should-have, and stretch priorities.",
                "Initial plan adapted for a GTX 1650 with 4 GB VRAM.",
            ),
            (
                "docs/FILE_CATALOG.md",
                "Provides the human-readable source catalog for maintained project files.",
                "Keeps file responsibilities and meaningful changes understandable.",
                "Added all Day 3 ingestion files and recorded video generation and sampling changes.",
            ),
        ],
    ),
    (
        "Documentation tooling and output",
        [
            (
                "scripts/generate_file_catalog_pdf.py",
                "Generates this polished catalog PDF from maintained metadata.",
                "Makes future PDF updates consistent and repeatable.",
                "Added Day 3 ingestion entries, milestone metadata, and regenerated pagination.",
            ),
            (
                "output/pdf/SafeSite_AI_File_Catalog.pdf",
                "Provides the printable and shareable form of the file catalog.",
                "Supports project reviews, learning, and PFE interview preparation.",
                "Regenerated after the Day 3 ingestion service, tools, README, Compose, and lesson changes.",
            ),
        ],
    ),
]


def footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D9E2EC"))
    canvas.line(20 * mm, 15 * mm, 190 * mm, 15 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#52616B"))
    canvas.drawString(20 * mm, 10 * mm, "SafeSite AI - Maintained File Catalog")
    canvas.drawRightString(190 * mm, 10 * mm, f"Page {document.page}")
    canvas.restoreState()


def build_pdf() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title="SafeSite AI File Catalog",
        author="SafeSite AI Project",
        subject="Project file roles and change register",
    )

    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "CatalogTitle",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=34,
        textColor=colors.HexColor("#102A43"),
        alignment=TA_CENTER,
        spaceAfter=10 * mm,
    )
    subtitle = ParagraphStyle(
        "CatalogSubtitle",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=18,
        textColor=colors.HexColor("#486581"),
        alignment=TA_CENTER,
    )
    section = ParagraphStyle(
        "CatalogSection",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#0B6E75"),
        spaceBefore=5 * mm,
        spaceAfter=4 * mm,
        keepWithNext=True,
    )
    path_style = ParagraphStyle(
        "CatalogPath",
        parent=base["Heading2"],
        fontName="Courier-Bold",
        fontSize=9.2,
        leading=12,
        textColor=colors.HexColor("#102A43"),
        spaceAfter=2 * mm,
        splitLongWords=True,
    )
    body = ParagraphStyle(
        "CatalogBody",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=9.4,
        leading=13.5,
        textColor=colors.HexColor("#243B53"),
        spaceAfter=1.6 * mm,
    )
    small = ParagraphStyle(
        "CatalogSmall",
        parent=body,
        fontSize=8.7,
        leading=12.5,
        textColor=colors.HexColor("#52616B"),
    )

    story = [
        Spacer(1, 28 * mm),
        Paragraph("SafeSite AI", title),
        Paragraph("Maintained File Catalog", subtitle),
        Spacer(1, 12 * mm),
        Table(
            [
                ["Edition", "Day 3"],
                ["Updated", date(2026, 8, 6).isoformat()],
                ["Maintained files", str(sum(len(entries) for _, entries in SECTIONS))],
                ["Current milestone", "Video timing and frame sampling"],
            ],
            colWidths=[42 * mm, 92 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#D9F0F0")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#102A43")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BCCCDC")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            ),
        ),
        Spacer(1, 12 * mm),
        Paragraph(
            "This document explains the role, reason, and latest meaningful change for every maintained SafeSite AI project file. Generated caches, local secrets, Docker volumes, downloaded models, and temporary render files are intentionally excluded.",
            subtitle,
        ),
        PageBreak(),
        Paragraph("Maintenance protocol", section),
        Paragraph(
            "Whenever a file is created, removed, or meaningfully changed, update the Markdown catalog and the generator metadata, regenerate this PDF, render every page, and include the documentation update in the same Git commit.",
            body,
        ),
        Spacer(1, 3 * mm),
    ]

    for section_name, entries in SECTIONS:
        for entry_index, (file_path, role, reason, latest_change) in enumerate(entries):
            card = [
                Paragraph(file_path, path_style),
                Paragraph(f"<b>Role:</b> {role}", body),
                Paragraph(f"<b>Why it exists:</b> {reason}", body),
                Paragraph(f"<b>Latest change:</b> {latest_change}", small),
                Spacer(1, 3.2 * mm),
            ]
            if entry_index == 0:
                card.insert(0, Paragraph(section_name, section))
            story.append(KeepTogether(card))

    story.extend(
        [
            Paragraph("Change register", section),
            Paragraph("2026-08-06 - Video timing and frame sampling", path_style),
            Paragraph(
                "Added a reproducible OpenCV ingestion container, controlled demo-video generation, time-based JPEG sampling, JSONL metadata, fractional-FPS validation, and the Day 3 lesson.",
                body,
            ),
            Paragraph("2026-08-05 - Safe time filtering and tests", path_style),
            Paragraph(
                "Added inclusive occurrence-time filters, reversed-range validation, a multi-stage test image, black-box integration tests, the Day 2 lesson, and binary Git attributes.",
                body,
            ),
            Paragraph("2026-08-04 - Initial vertical slice", path_style),
            Paragraph(
                "Added Docker Compose, PostgreSQL schema and seed data, FastAPI routes, architecture explanation, Day 1 lesson, and the 28-day roadmap.",
                body,
            ),
        ]
    )

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()
