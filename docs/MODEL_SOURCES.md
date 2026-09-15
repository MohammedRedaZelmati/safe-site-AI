# SafeSite AI Model Sources

This register records where external model artifacts come from, how their identity is verified, and which license conditions apply. Downloaded weights remain under `data/models/` and are not committed to Git.

## YOLO26n COCO baseline

- **Model:** Ultralytics YOLO26n object detector
- **Purpose:** CPU smoke test for generic object detection before PPE-specific training
- **Official documentation:** <https://docs.ultralytics.com/models/yolo26/>
- **Weight URL:** <https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt>
- **Local path:** `data/models/yolo26n.pt`
- **Retrieved:** 2026-08-07
- **File size:** 5,544,453 bytes
- **SHA256:** `9B09CC8BF347F0FC8A5F7657480587F25DB09B34BF33B0652110FB03A8AD4FEF`
- **Runtime image:** `ultralytics/ultralytics:8.4.107-python`
- **Runtime image digest:** `sha256:a3f950c1d318397b86ee801899170957658bd91b549bc2d633a5cfc0c158fab0`

The released checkpoint is pretrained on COCO. Its vocabulary includes `person`, but not the PPE-specific classes required by SafeSite AI, such as `helmet`, `safety_vest`, `NO_HELMET`, or `NO_VEST`.

## License boundary

Ultralytics documents YOLO26 code and models under AGPL-3.0 and Enterprise licensing options. Its licensing page lists learning, experimentation, university coursework, and fully open-source projects as AGPL-3.0 use cases. It says proprietary or commercial applications require an Enterprise license.

SafeSite AI currently uses this model as a learning and portfolio baseline. Before any private company deployment or commercial product use, the model and software license must be reviewed again.

## Reproduction

Run:

```powershell
python scripts/download_yolo_model.py
```

The downloader accepts an existing file only when its SHA256 equals the value recorded above. This prevents an incomplete, replaced, or silently changed weight file from entering the experiment.
# Tracking runtime dependency

ByteTrack requires `lap`, a linear-assignment solver used while associating detections with tracks.

```text
package: lap 0.5.12
platform: CPython 3.13, Linux x86_64
source: PyPI files.pythonhosted.org
SHA256: 6dd54bf8bb48c87f6276555e8014d4ea27742d84ddbb0e7b68be575f4ca438d7
```

`scripts/download_tracking_dependency.py` downloads and verifies the wheel on Windows. The ingestion Dockerfile installs that artifact with `--no-index`, so the container does not contact PyPI and does not bypass TLS verification.
