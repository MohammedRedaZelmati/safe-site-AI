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
                "Added the file-catalog link and documentation synchronization rule.",
            ),
            (
                "compose.yaml",
                "Defines and connects the PostgreSQL and FastAPI containers.",
                "Starts the current system reproducibly and preserves database data in a volume.",
                "Initial services, health check, ports, dependency, and named volume added.",
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
                "Initial Python 3.12 and Uvicorn image recipe added.",
            ),
            (
                "services/api/requirements.txt",
                "Declares the Python dependencies required by the API.",
                "Makes dependency installation repeatable in the container.",
                "FastAPI, Uvicorn, Psycopg, pool, and settings dependencies added.",
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
                "Initial four API routes and parameterized SQL operations added.",
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
                "docs/ROADMAP.md",
                "Defines the realistic 28-day learning and implementation plan.",
                "Protects the deadline using must-have, should-have, and stretch priorities.",
                "Initial plan adapted for a GTX 1650 with 4 GB VRAM.",
            ),
            (
                "docs/FILE_CATALOG.md",
                "Provides the human-readable source catalog for maintained project files.",
                "Keeps file responsibilities and meaningful changes understandable.",
                "Created and populated with the Day 1 repository state.",
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
                "Initial cover, grouped entries, change register, and page numbering added.",
            ),
            (
                "output/pdf/SafeSite_AI_File_Catalog.pdf",
                "Provides the printable and shareable form of the file catalog.",
                "Supports project reviews, learning, and PFE interview preparation.",
                "First edition generated from the Day 1 project state.",
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
                ["Edition", "Day 1 baseline"],
                ["Updated", date(2026, 8, 5).isoformat()],
                ["Maintained files", str(sum(len(entries) for _, entries in SECTIONS))],
                ["Current milestone", "Event storage and REST API"],
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
            Paragraph("2026-08-05 - File catalog introduced", path_style),
            Paragraph(
                "Added the Markdown catalog, PDF generator, generated PDF, and README synchronization rule.",
                body,
            ),
            Paragraph("2026-08-04 - Initial vertical slice", path_style),
            Paragraph(
                "Added Docker Compose, PostgreSQL schema and seed data, FastAPI routes, architecture explanation, Day 1 lesson, and the 28-day roadmap.",
                body,
            ),
            Spacer(1, 10 * mm),
            Paragraph(
                "End of catalog - regenerate after every meaningful project change.",
                subtitle,
            ),
        ]
    )

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()
