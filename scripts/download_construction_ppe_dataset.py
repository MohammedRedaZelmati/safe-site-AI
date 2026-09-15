import argparse
import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path
from zipfile import ZipFile


SOURCE_PAGE = "https://docs.ultralytics.com/datasets/detect/construction-ppe/"
DOWNLOAD_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip"
LICENSE = "AGPL-3.0"
EXPECTED_BYTES = 178_415_813
EXPECTED_SHA256 = "BEF8DCB599AA4E9D9F5E602CB6FA7143D3C84D7F6A0FF40463D7F2A4C2632CCC"
DEFAULT_ARCHIVE = Path("data/datasets/external/construction-ppe.zip")
DEFAULT_OUTPUT_DIR = Path("data/datasets/construction-ppe")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def download(url: str, output: Path) -> None:
    if os.name == "nt":
        environment = os.environ.copy()
        environment["SAFESITE_DOWNLOAD_URL"] = url
        environment["SAFESITE_DOWNLOAD_OUTPUT"] = str(output)
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "$ProgressPreference='SilentlyContinue'; "
                "Invoke-WebRequest -Uri $env:SAFESITE_DOWNLOAD_URL "
                "-OutFile $env:SAFESITE_DOWNLOAD_OUTPUT",
            ],
            check=True,
            env=environment,
        )
        return

    request = urllib.request.Request(url, headers={"User-Agent": "SafeSite-AI/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, output.open("wb") as file:
        shutil.copyfileobj(response, file)


def verify_archive(archive_path: Path) -> dict[str, str | int]:
    actual_bytes = archive_path.stat().st_size
    if actual_bytes != EXPECTED_BYTES:
        raise ValueError(f"Archive size mismatch: expected {EXPECTED_BYTES}, got {actual_bytes}")
    actual_sha256 = sha256(archive_path)
    if actual_sha256 != EXPECTED_SHA256:
        raise ValueError(
            f"Archive SHA256 mismatch: expected {EXPECTED_SHA256}, got {actual_sha256}"
        )
    return {"bytes": actual_bytes, "sha256": actual_sha256}


def extract_safely(archive_path: Path, output_dir: Path) -> str:
    if output_dir.exists() and any(output_dir.iterdir()):
        if (output_dir / "data.yaml").is_file():
            return "already-extracted"
        raise FileExistsError(f"Output directory is not empty: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_root = output_dir.resolve()
    with ZipFile(archive_path) as archive:
        for member in archive.infolist():
            destination = (output_dir / member.filename).resolve()
            if output_root != destination and output_root not in destination.parents:
                raise ValueError(f"Unsafe archive path: {member.filename}")
        archive.extractall(output_dir)
    return "extracted"


def acquire(archive_path: Path, output_dir: Path) -> dict[str, str | int]:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    download_status = "already-present"
    if not archive_path.is_file():
        temporary_path = archive_path.with_suffix(archive_path.suffix + ".part")
        try:
            download(DOWNLOAD_URL, temporary_path)
            verify_archive(temporary_path)
            temporary_path.replace(archive_path)
            download_status = "downloaded"
        finally:
            temporary_path.unlink(missing_ok=True)

    verification = verify_archive(archive_path)
    extraction_status = extract_safely(archive_path, output_dir)
    return {
        "download_status": download_status,
        "extraction_status": extraction_status,
        "archive": str(archive_path),
        "output_dir": str(output_dir),
        **verification,
        "source_page": SOURCE_PAGE,
        "download_url": DOWNLOAD_URL,
        "license": LICENSE,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download, verify, and safely extract the Construction-PPE dataset."
    )
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(acquire(args.archive, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
