import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "services" / "ingestion" / "requirements.txt"
VENDOR = ROOT / "services" / "ingestion" / "vendor"
EXPECTED_SHA256 = {
    "argon2_cffi-25.1.0-py3-none-any.whl": "fdc8b074db390fccb6eb4a3604ae7231f219aa669a2652e0f20e16ba513d5741",
    "argon2_cffi_bindings-25.1.0-cp39-abi3-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl": "d3e924cfc503018a714f94a49a149fdc0b644eaead5d1f089330399134fa028a",
    "certifi-2026.7.22-py3-none-any.whl": "62f22742b58a1a33014a2b6b706588a8d7e2a88ae7bd1a6ebe8c992928483775",
    "cffi-2.1.1-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl": "a931079504ecc49efed7744c476a5c343a92fabf66dec2db95edb1b2fdc770e2",
    "confluent_kafka-2.15.0-cp313-cp313-manylinux_2_28_x86_64.whl": "0455754e8294e1e76cb5acc083c300b6bd8d88f2d2c551c583cbf4ab55889a57",
    "minio-7.2.20-py3-none-any.whl": "eb33dd2fb80e04c3726a76b13241c6be3c4c46f8d81e1d58e757786f6501897e",
    "pyarrow-21.0.0-cp313-cp313-manylinux_2_28_x86_64.whl": "69cbbdf0631396e9925e048cfa5bce4e8c3d3b41562bbd70c685a8eb53a91e61",
    "pycparser-3.0-py3-none-any.whl": "b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992",
    "pycryptodome-3.23.0-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl": "c8987bd3307a39bc03df5c8e0e3d8be0c4c3518b7f044b0f4c15d1aa78f52575",
    "typing_extensions-4.16.0-py3-none-any.whl": "481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8",
    "urllib3-2.7.0-py3-none-any.whl": "9fb4c81ebbb1ce9531cce37674bbc6f1360472bc18ca9a553ede278ef7276897",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(directory: Path) -> None:
    actual_names = {path.name for path in directory.glob("*.whl")}
    expected_names = set(EXPECTED_SHA256)
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        unexpected = sorted(actual_names - expected_names)
        raise ValueError(f"Wheel set mismatch; missing={missing}, unexpected={unexpected}")

    for filename, expected_hash in EXPECTED_SHA256.items():
        actual_hash = sha256(directory / filename)
        if actual_hash != expected_hash:
            raise ValueError(
                f"Hash mismatch for {filename}: expected {expected_hash}, got {actual_hash}"
            )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="safesite-streaming-wheels-") as temporary:
        download_dir = Path(temporary)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--dest",
                str(download_dir),
                "--only-binary=:all:",
                "--platform",
                "manylinux_2_28_x86_64",
                "--platform",
                "manylinux2014_x86_64",
                "--python-version",
                "3.13",
                "--implementation",
                "cp",
                "--abi",
                "cp313",
                "-r",
                str(REQUIREMENTS),
            ],
            check=True,
        )
        verify(download_dir)
        VENDOR.mkdir(parents=True, exist_ok=True)
        for filename in EXPECTED_SHA256:
            (download_dir / filename).replace(VENDOR / filename)

    print(f"Downloaded and verified {len(EXPECTED_SHA256)} streaming wheels in {VENDOR}")


if __name__ == "__main__":
    main()
