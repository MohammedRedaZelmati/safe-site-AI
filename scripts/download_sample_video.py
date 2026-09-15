import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


SOURCE_PAGE = "https://www.pexels.com/video/construction-workers-walking-at-the-construction-site-8965526/"
DOWNLOAD_URL = "https://videos.pexels.com/video-files/8965526/8965526-hd_720_1280_25fps.mp4"
LICENSE_URL = "https://www.pexels.com/license/"
EXPECTED_SHA256 = "1B6755FCEAAC5DED99B023AE4786C15FE9E7C99DD9BE75FC1739352FE19C53E4"
DEFAULT_OUTPUT = Path("data/videos/external/pexels-8965526.mp4")


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
    parser = argparse.ArgumentParser(description="Download the licensed SafeSite AI sample video.")
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

