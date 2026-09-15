import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


SOURCE_PAGE = "https://docs.ultralytics.com/models/yolo26/"
DOWNLOAD_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt"
LICENSE_URL = "https://www.ultralytics.com/license"
EXPECTED_SHA256 = "9B09CC8BF347F0FC8A5F7657480587F25DB09B34BF33B0652110FB03A8AD4FEF"
DEFAULT_OUTPUT = Path("data/models/yolo26n.pt")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def download(output_path: Path) -> dict[str, str | int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        existing_hash = sha256(output_path)
        if existing_hash != EXPECTED_SHA256:
            raise ValueError(
                f"Existing file has unexpected SHA256: {existing_hash}. "
                f"Expected: {EXPECTED_SHA256}"
            )
        return {
            "status": "already-present",
            "output_path": str(output_path),
            "bytes": output_path.stat().st_size,
            "sha256": existing_hash,
        }

    temporary_path = output_path.with_suffix(output_path.suffix + ".part")
    request = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "SafeSite-AI/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        with temporary_path.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)

    downloaded_hash = sha256(temporary_path)
    if downloaded_hash != EXPECTED_SHA256:
        raise ValueError(
            f"Downloaded file has unexpected SHA256: {downloaded_hash}. "
            f"Expected: {EXPECTED_SHA256}"
        )

    temporary_path.replace(output_path)
    return {
        "status": "downloaded",
        "output_path": str(output_path),
        "bytes": output_path.stat().st_size,
        "sha256": downloaded_hash,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download the pinned SafeSite AI baseline model.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = download(args.output)
    result.update(
        {
            "source_page": SOURCE_PAGE,
            "license": LICENSE_URL,
        }
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
