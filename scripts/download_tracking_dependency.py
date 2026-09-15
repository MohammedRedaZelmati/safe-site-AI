import hashlib
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path


VERSION = "0.5.12"
FILENAME = (
    "lap-0.5.12-cp313-cp313-manylinux_2_5_x86_64.manylinux1_x86_64."
    "manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
)
URL = f"https://files.pythonhosted.org/packages/f9/bb/0f3a44d7220bd48f9a313a64f4c228a02cbb0fb1f55fd449de7a0659a5e2/{FILENAME}"
EXPECTED_SHA256 = "6dd54bf8bb48c87f6276555e8014d4ea27742d84ddbb0e7b68be575f4ca438d7"
OUTPUT = Path(__file__).resolve().parents[1] / "services" / "ingestion" / "vendor" / FILENAME


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    with urllib.request.urlopen(url) as response, output.open("wb") as file:
        shutil.copyfileobj(response, file)


def main() -> None:
    if OUTPUT.is_file():
        actual_sha256 = sha256(OUTPUT)
        if actual_sha256 != EXPECTED_SHA256:
            raise ValueError(
                f"Existing wheel hash mismatch: expected {EXPECTED_SHA256}, got {actual_sha256}"
            )
        print(f"Verified existing lap {VERSION} wheel: {OUTPUT}")
        return

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = OUTPUT.with_suffix(OUTPUT.suffix + ".part")
    try:
        download(URL, temporary_output)
        actual_sha256 = sha256(temporary_output)
        if actual_sha256 != EXPECTED_SHA256:
            raise ValueError(
                f"Downloaded wheel hash mismatch: expected {EXPECTED_SHA256}, got {actual_sha256}"
            )
        temporary_output.replace(OUTPUT)
    finally:
        temporary_output.unlink(missing_ok=True)

    print(f"Downloaded and verified lap {VERSION}: {OUTPUT}")
    print(f"SHA256: {EXPECTED_SHA256}")


if __name__ == "__main__":
    main()
