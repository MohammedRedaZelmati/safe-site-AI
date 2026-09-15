import os
from pathlib import Path
from socket import timeout as SocketTimeout
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
from datetime import datetime, timezone

import streamlit as st


API_URL = os.getenv("SAFESITE_API_URL", "http://localhost:8000").rstrip("/")
AGENT_URL = os.getenv("SAFESITE_AGENT_URL", "http://localhost:8010").rstrip("/")


def resolve_data_root() -> Path:
    configured_root = os.getenv("SAFESITE_DATA_ROOT")
    if configured_root:
        return Path(configured_root)
    project_root = next(
        (
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / "compose.yaml").is_file()
        ),
        None,
    )
    return project_root / "data" if project_root else Path("/data")


DATA_ROOT = resolve_data_root()
PROJECT_ROOT = DATA_ROOT.parent
STREAMING_ROOT = DATA_ROOT / "streaming"
HEALTH_REPORT = DATA_ROOT / "workers" / "health-report.json"
DRIFT_REPORT = DATA_ROOT / "monitoring" / "drift-report.json"
QUALITY_REPORT = DATA_ROOT / "monitoring" / "event-quality-report.json"
PPE_EVALUATION_REPORT = DATA_ROOT / "training" / "ppe-baseline-e10-full-img320" / "evaluation.json"
NO_HELMET_REVIEW_SUMMARY = DATA_ROOT / "evaluation" / "no-helmet-construction-proof" / "summary.json"
FINAL_DEMO_SUMMARY = DATA_ROOT / "final-demo" / "summary.json"


@st.cache_data(ttl=5)
def fetch_json(path: str, query: dict | None = None):
    url = f"{API_URL}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API returned HTTP {error.code}: {details}") from error
    except (TimeoutError, SocketTimeout) as error:
        raise RuntimeError(f"API did not answer within 5 seconds: {API_URL}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach {API_URL}: {error.reason}") from error


def post_json(base_url: str, path: str, payload: dict):
    request = Request(
        f"{base_url}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Agent returned HTTP {error.code}: {details}") from error
    except (TimeoutError, SocketTimeout) as error:
        raise RuntimeError(f"Agent did not answer within 60 seconds: {base_url}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach {base_url}: {error.reason}") from error


def local_frame_path(frame_uri: str | None) -> Path | None:
    if not frame_uri:
        return None
    normalized = frame_uri.replace("\\", "/")
    if normalized.startswith("/data/"):
        candidate = DATA_ROOT / normalized.removeprefix("/data/")
    else:
        candidate = Path(frame_uri)
    return candidate if candidate.is_file() else None


def local_project_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    normalized = path_value.replace("\\", "/")
    if normalized.startswith("/data/"):
        candidate = DATA_ROOT / normalized.removeprefix("/data/")
    else:
        candidate = PROJECT_ROOT / normalized
    return candidate if candidate.is_file() else None


@st.cache_data(ttl=5)
def load_run_summaries() -> list[dict]:
    summaries = []
    for summary_path in STREAMING_ROOT.glob("demo-*/run-summary.json"):
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        summary["_summary_path"] = str(summary_path)
        summary["_modified_at"] = summary_path.stat().st_mtime
        summaries.append(summary)
    return sorted(summaries, key=lambda item: item["_modified_at"], reverse=True)


def run_label(summary: dict) -> str:
    run_id = summary.get("run_id", "unknown-run")
    status = summary.get("status", "unknown")
    return f"{run_id} — {status}"


@st.cache_data(ttl=5)
def load_health_report() -> dict | None:
    try:
        return json.loads(HEALTH_REPORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


@st.cache_data(ttl=10)
def load_drift_report() -> dict | None:
    try:
        return json.loads(DRIFT_REPORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


@st.cache_data(ttl=10)
def load_quality_report() -> dict | None:
    try:
        return json.loads(QUALITY_REPORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def format_violation_type(value: str) -> str:
    labels = {
        "NO_HELMET": "No helmet",
        "NO_VEST": "No safety vest",
        "NO_GOGGLE": "No safety goggles",
        "NO_BOOTS": "No safety boots",
    }
    return labels.get(value, value.replace("_", " ").title())


def format_timestamp(value: str | None) -> str:
    if not value:
        return "Unknown time"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def format_percent(value: float | int | None) -> str:
    if value is None:
        return "missing"
    return f"{float(value) * 100:.1f}%"


@st.cache_data(ttl=10)
def load_latest_run_evidence(summary_path_value: str) -> dict | None:
    run_root = Path(summary_path_value).parent
    evidence_records = []
    for prediction_path in run_root.glob("ppe/detections/*/prediction.json"):
        try:
            prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        annotated_path = prediction_path.with_name("annotated.jpg")
        if not annotated_path.is_file():
            continue
        evidence_records.append(
            {
                "path": str(annotated_path),
                "sample_index": int(prediction.get("sample_index", -1)),
                "video_timestamp_ms": int(prediction.get("video_timestamp_ms", 0)),
                "detection_count": int(prediction.get("detection_count", 0)),
                "kind": "annotated detection frame",
            }
        )
    if evidence_records:
        return max(evidence_records, key=lambda item: item["sample_index"])

    sampled_frames = sorted((run_root / "frames").glob("*.jpg"))
    if not sampled_frames:
        return None
    return {
        "path": str(sampled_frames[-1]),
        "sample_index": len(sampled_frames) - 1,
        "video_timestamp_ms": 0,
        "detection_count": None,
        "kind": "sampled camera frame",
    }


def load_run_candidate_events(summary_path_value: str) -> list[dict]:
    candidate_path = Path(summary_path_value).parent / "tracking" / "candidate_events.jsonl"
    if not candidate_path.is_file():
        return []
    candidates = []
    for line in candidate_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            candidates.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return candidates


def run_source_video_path(summary_path_value: str) -> Path | None:
    run_root = Path(summary_path_value).parent
    for candidate in (run_root / "source.mp4", run_root / "source.mov", run_root / "source.avi"):
        if candidate.is_file():
            return candidate
    return None


def run_source_preview_path(summary_path_value: str) -> Path | None:
    candidate = Path(summary_path_value).parent / "source-preview.gif"
    return candidate if candidate.is_file() else None


def run_source_still_path(summary_path_value: str) -> Path | None:
    run_root = Path(summary_path_value).parent
    source_metadata_path = run_root / "source.json"
    if source_metadata_path.is_file():
        try:
            source_metadata = json.loads(source_metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            source_metadata = {}
        source_image = source_metadata.get("source_image")
        if isinstance(source_image, str):
            if source_image.startswith("/data/"):
                candidate = DATA_ROOT / source_image.removeprefix("/data/")
            else:
                candidate = Path(source_image)
            if candidate.is_file():
                return candidate
    first_frame = next(iter(sorted((run_root / "frames").glob("*.jpg"))), None)
    return first_frame if first_frame and first_frame.is_file() else None


def read_video_bytes(video_path: Path) -> bytes | None:
    try:
        return video_path.read_bytes()
    except OSError:
        return None


@st.cache_data(ttl=10)
def load_json_file(path_value: str) -> dict | None:
    path = Path(path_value)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def resolve_data_reference(value: str | None) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    if value.startswith("/data/"):
        candidate = DATA_ROOT / value.removeprefix("/data/")
    else:
        candidate = Path(value)
    return candidate if candidate.is_file() else None


def class_metric(evaluation: dict | None, class_name: str) -> dict | None:
    if not evaluation:
        return None
    for item in evaluation.get("per_class", []):
        if item.get("class_name") == class_name:
            return item
    return None


def detection_rows(summary: dict) -> list[dict]:
    measurements = summary.get("measurements", {})
    class_counts = measurements.get("associated_class_counts", {})
    return [
        {"detected object": label, "count across analyzed frames": count}
        for label, count in sorted(class_counts.items())
    ]


def html_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def status_chip(label: str, value: str, tone: str = "neutral") -> None:
    st.markdown(
        f"""
        <div class="status-chip status-{tone}">
            <span>{html_escape(label)}</span>
            <strong>{html_escape(value)}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(eyebrow: str, title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="section-heading">
            <span>{html_escape(eyebrow)}</span>
            <h2>{html_escape(title)}</h2>
            <p>{html_escape(body)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="SafeSite AI", page_icon="🦺", layout="wide")
st.markdown(
    """
    <style>
    .stApp {background: linear-gradient(180deg, #08111f 0%, #0f172a 45%, #111827 100%);}
    .block-container {max-width: 1240px; padding-top: 1.4rem; padding-bottom: 3rem;}
    .hero {
        padding: 1.4rem 1.6rem;
        border: 1px solid #243449;
        border-radius: 1.2rem;
        background:
            radial-gradient(circle at top right, rgba(34, 197, 94, 0.22), transparent 28rem),
            linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.82));
        margin-bottom: 1rem;
    }
    .hero h1 {font-size: 2.35rem; line-height: 1.1; margin: 0 0 .4rem 0;}
    .hero p {color: #cbd5e1; margin: 0; max-width: 820px;}
    .section-heading {
        margin: 1.2rem 0 .75rem 0;
        padding: 1rem 1.1rem;
        border-left: 4px solid #38bdf8;
        border-radius: .9rem;
        background: rgba(15, 23, 42, .72);
        border-top: 1px solid rgba(148, 163, 184, .18);
        border-right: 1px solid rgba(148, 163, 184, .18);
        border-bottom: 1px solid rgba(148, 163, 184, .18);
    }
    .section-heading span {
        color: #38bdf8;
        font-size: .78rem;
        font-weight: 800;
        letter-spacing: .08em;
        text-transform: uppercase;
    }
    .section-heading h2 {margin: .15rem 0 .25rem 0; font-size: 1.35rem;}
    .section-heading p {margin: 0; color: #94a3b8;}
    .status-chip {
        min-height: 76px;
        padding: .95rem 1rem;
        border-radius: 1rem;
        border: 1px solid #334155;
        background: rgba(15, 23, 42, .92);
        box-shadow: 0 10px 30px rgba(0,0,0,.18);
    }
    .status-chip span {display: block; color: #94a3b8; font-size: .82rem; margin-bottom: .35rem;}
    .status-chip strong {display: block; color: #f8fafc; font-size: 1.18rem;}
    .status-good {border-color: rgba(34, 197, 94, .65); background: rgba(20, 83, 45, .32);}
    .status-warn {border-color: rgba(250, 204, 21, .7); background: rgba(113, 63, 18, .32);}
    .status-bad {border-color: rgba(248, 113, 113, .75); background: rgba(127, 29, 29, .35);}
    .status-neutral {border-color: rgba(56, 189, 248, .5);}
    div[data-testid="stMetric"] {background: #182033; border: 1px solid #334155; padding: 1rem; border-radius: 0.9rem;}
    div[data-testid="stMetric"] label, div[data-testid="stMetric"] [data-testid="stMetricValue"] {color: #f8fafc;}
    div[data-testid="stAlert"] {border-radius: 0.8rem;}
    div[data-testid="stTabs"] button {font-weight: 700;}
    .small-note {color: #94a3b8; font-size: .92rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.title("🦺 SafeSite AI")
st.sidebar.caption("Local safety monitoring stack")
st.sidebar.link_button("Dashboard", "http://localhost:8502", use_container_width=True)
st.sidebar.link_button("FastAPI docs", "http://localhost:8000/docs", use_container_width=True)
st.sidebar.link_button("MLflow", "http://localhost:5000", use_container_width=True)
st.sidebar.link_button("Airflow", "http://localhost:8080", use_container_width=True)
st.sidebar.link_button("MinIO", "http://localhost:9001", use_container_width=True)

title_col, refresh_col = st.columns([5, 1])
with title_col:
    st.markdown(
        """
        <div class="hero">
            <h1>🦺 SafeSite AI Streaming Control Center</h1>
            <p>Review one streaming run: source video, Kafka frame flow, model proof, and final safety decision.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with refresh_col:
    if st.button("↻ Refresh", use_container_width=True):
        st.cache_data.clear()

final_demo = load_json_file(str(FINAL_DEMO_SUMMARY))
if final_demo:
    proof_path = local_project_path(final_demo.get("proof_image"))

    section_header(
        "Final demo",
        "Professional PPE violation evidence",
        "One real construction frame, one clear safety decision, and the model-quality metrics needed for review.",
    )

    st.error(f"🚨 Violation detected: {final_demo.get('violation_label', 'PPE violation')}")
    result_cols = st.columns(4)
    result_cols[0].metric("Decision", final_demo.get("decision", "Human review required"))
    result_cols[1].metric("Evidence time", f"{final_demo.get('video_timestamp_seconds', 0):.1f}s")
    result_cols[2].metric("Precision", format_percent(final_demo.get("model_precision")))
    result_cols[3].metric("mAP50", format_percent(final_demo.get("model_map50")))

    detail_cols = st.columns([3, 2])
    with detail_cols[0]:
        st.markdown("### Evidence frame")
        if proof_path:
            st.image(
                str(proof_path),
                caption="Real Pexels construction frame with the no-vest violation highlighted.",
                use_container_width=True,
            )
        else:
            st.warning("The proof image is missing.")
    with detail_cols[1]:
        st.markdown("### Review details")
        st.write(final_demo.get("evidence_note", "The highlighted worker requires safety review."))
        st.metric("Violation type", final_demo.get("violation_label", "Unknown"))
        st.metric("Review confidence", final_demo.get("review_confidence_label", "High"))
        st.metric("Recall", format_percent(final_demo.get("model_recall")))
        st.write(
            f"Metrics are for the `{final_demo.get('metric_class', 'PPE')}` class in the trained PPE model."
        )
        st.write(
            "`mAP50` is the object-detection accuracy proxy; object detection does not use simple accuracy."
        )
        st.link_button("Pexels source video", final_demo.get("source_page", "https://www.pexels.com/"))
        st.caption(final_demo.get("important_limitation", ""))

    st.stop()

run_summaries = load_run_summaries()
ppe_evaluation = load_json_file(str(PPE_EVALUATION_REPORT))
no_helmet_metric = class_metric(ppe_evaluation, "no_helmet")
review_summary = load_json_file(str(NO_HELMET_REVIEW_SUMMARY))

latest_run = run_summaries[0] if run_summaries else {}
latest_candidates = int(latest_run.get("topic_message_counts", {}).get("candidates", 0))
model_recall = float(no_helmet_metric["recall"]) if no_helmet_metric else None
model_tone = "good" if model_recall is not None and model_recall >= 0.7 else "warn"

overview_cols = st.columns(4)
with overview_cols[0]:
    status_chip("Streaming proof", "ready" if run_summaries else "missing", "good" if run_summaries else "bad")
with overview_cols[1]:
    status_chip("Latest run", latest_run.get("status", "missing"), "good" if latest_run.get("status") == "completed" else "warn")
with overview_cols[2]:
    status_chip("Confirmed candidates", latest_candidates, "bad" if latest_candidates else "good")
with overview_cols[3]:
    status_chip(
        "no_helmet recall",
        "missing" if model_recall is None else f"{model_recall * 100:.1f}%",
        model_tone,
    )

section_header(
    "Streaming run",
    "Source video → Kafka → YOLO → tracking → candidate decision",
    "Only the streaming pipeline is shown here. Dataset proof, model training, database review, and agent sections are hidden for clarity.",
)

if not run_summaries:
    st.warning("No completed pipeline run is available yet.")
else:
    selected_run_label = st.selectbox(
        "Analyzed run",
        [run_label(item) for item in run_summaries],
    )
    selected_run = next(
        item for item in run_summaries if run_label(item) == selected_run_label
    )
    topic_counts = selected_run.get("topic_message_counts", {})
    candidate_count = int(topic_counts.get("candidates", 0))
    run_status = selected_run.get("status", "unknown")
    source_video = run_source_video_path(selected_run["_summary_path"])
    source_preview = run_source_preview_path(selected_run["_summary_path"])
    source_still = run_source_still_path(selected_run["_summary_path"])
    candidate_events = load_run_candidate_events(selected_run["_summary_path"])

    if run_status != "completed":
        st.warning("⚠️ ANALYSIS INCOMPLETE — no safety decision can be trusted yet.")
    elif candidate_count:
        st.error(
            f"🚨 {candidate_count} POSSIBLE PPE VIOLATION(S) — HUMAN REVIEW REQUIRED"
        )
    else:
        st.success("✅ NO TEMPORAL PPE VIOLATION WAS CONFIRMED IN THIS RUN")

    decision_columns = st.columns(4)
    decision_columns[0].metric("Camera", selected_run.get("camera_id", "unknown"))
    decision_columns[1].metric(
        "Frames analyzed", selected_run.get("frame_count_requested", 0)
    )
    decision_columns[2].metric("Violation candidates", candidate_count)
    decision_columns[3].metric(
        "Run finished",
        format_timestamp(selected_run.get("completed_at")),
    )

    st.markdown("#### Video used")
    if source_video:
        video_bytes = read_video_bytes(source_video)
        if video_bytes:
            st.video(video_bytes, format="video/mp4")
            if source_preview:
                st.caption("If the MP4 player stays black, use this browser-safe animated preview.")
                st.image(str(source_preview), caption="Animated preview of the same source run.")
        else:
            st.warning("The source video file exists, but Streamlit could not read it.")
            if source_preview:
                st.image(str(source_preview), caption="Animated preview of the same source run.")
        st.caption(f"Source video: {source_video.name}")
    else:
        st.warning("No source video file was found for this run.")
    if source_still:
        st.image(
            str(source_still),
            caption="Still proof from the same video source.",
            use_container_width=True,
        )

    evidence = load_latest_run_evidence(selected_run["_summary_path"])
    evidence_col, result_col = st.columns([3, 2])
    with evidence_col:
        st.markdown("#### Model visual proof")
        if evidence:
            st.image(
                evidence["path"],
                caption=(
                    f"Latest {evidence['kind']} — frame {evidence['sample_index'] + 1}, "
                    f"video time {evidence['video_timestamp_ms'] / 1000:.1f}s"
                ),
                use_container_width=True,
            )
        else:
            st.warning("No visual evidence image was found for this run.")

    with result_col:
        st.markdown("#### Violations detected in this video")
        if candidate_events:
            st.error(f"{len(candidate_events)} confirmed candidate violation(s)")
            st.dataframe(
                [
                    {
                        "track": event.get("track_id"),
                        "violation": format_violation_type(event.get("violation_type", "")),
                        "confidence": event.get("confidence"),
                        "frame proof": event.get("frame_uri"),
                    }
                    for event in candidate_events
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("0 confirmed violations detected in this video.")
            st.caption(
                "This means the current model/rules did not confirm a violation. "
                "It does not prove that every worker is compliant."
            )
        rows = detection_rows(selected_run)
        if rows:
            st.markdown("Detected PPE objects")
            st.dataframe(rows, use_container_width=True, hide_index=True)
    if review_summary:
        st.markdown("#### Confirmed visual violation proof")
        proof_video = local_project_path(review_summary.get("review_video"))
        proof_frame = local_project_path(review_summary.get("first_frame"))
        proof_contact_sheet = local_project_path(review_summary.get("contact_sheet"))
        proof_cols = st.columns([3, 2])
        with proof_cols[0]:
            st.error(
                f"🚨 Labelled no-helmet violation proof: "
                f"{review_summary.get('labelled_no_helmet_boxes', 0)} no-helmet box(es)"
            )
            if proof_video:
                proof_video_bytes = read_video_bytes(proof_video)
                if proof_video_bytes:
                    st.video(proof_video_bytes, format="video/mp4")
                elif proof_frame:
                    st.image(
                        str(proof_frame),
                        caption="First frame from the labelled violation proof.",
                        use_container_width=True,
                    )
            elif proof_frame:
                st.image(
                    str(proof_frame),
                    caption="First frame from the labelled violation proof.",
                    use_container_width=True,
                )
        with proof_cols[1]:
            st.metric("Violation type", "No helmet")
            st.metric("Real labelled samples", review_summary.get("sample_count", 0))
            st.metric("Total labelled boxes", review_summary.get("labelled_no_helmet_boxes", 0))
            st.caption(
                "This proof comes from labelled Construction-PPE images. "
                "It proves the system has visual examples of real PPE violations, "
                "but it is a review reel, not a continuous live camera video."
            )
            if proof_contact_sheet:
                st.image(
                    str(proof_contact_sheet),
                    caption="Contact sheet of labelled violation examples.",
                    use_container_width=True,
                )
    st.info(
        "The image proves what the model analyzed. A 'no confirmed violation' result "
        "does not prove that every worker was compliant."
    )
    with st.expander("Streaming stages and Kafka topics"):
        st.markdown(
            """
            ```text
            stream_camera.py
              -> Kafka topic: safesite.frames.raw
              -> infer_frame_events.py
              -> Kafka topic: safesite.ppe.detections
              -> process_ppe_stream.py
              -> Kafka topics: safesite.tracks / safesite.candidate-violations
              -> consume_candidate_events.py
              -> FastAPI / PostgreSQL
            ```
            """
        )
        stage_rows = [
            {"stage": stage.replace("_", " "), "result": result}
            for stage, result in selected_run.get("stages", {}).items()
        ]
        if stage_rows:
            st.dataframe(stage_rows, use_container_width=True, hide_index=True)

st.stop()

st.divider()
section_header(
    "Database review",
    "Recorded violations to review",
    "These are database records. A record without an image is not visually verified. The starter records are demonstration data.",
)
if not api_available:
    st.info(
        "PostgreSQL records are hidden because FastAPI is offline. "
        "Start Docker to review database-backed violations."
    )
    events = []
else:
    camera_options = sorted({event["camera_id"] for event in all_events})
    type_options = sorted({event["violation_type"] for event in all_events})
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    camera_filter = filter_col1.selectbox("Camera", ["All", *camera_options])
    type_filter = filter_col2.selectbox("Violation type", ["All", *type_options])
    limit = filter_col3.slider("Maximum events", 1, 200, 50)

    query = {"limit": limit}
    if camera_filter != "All":
        query["camera_id"] = camera_filter
    if type_filter != "All":
        query["violation_type"] = type_filter
    events = fetch_json("/violations", query)

    record_columns = st.columns(3)
    record_columns[0].metric("All recorded events", summary["total"])
    record_columns[1].metric("Matching records", len(events))
    record_columns[2].metric("Cameras represented", len(camera_options))

if not events:
    st.success("✅ No recorded violations match these filters.")
else:
    st.error(f"🚨 {len(events)} RECORDED VIOLATION(S) REQUIRE REVIEW")
    event_by_id = {event["id"]: event for event in events}
    selected_id = st.selectbox(
        "Choose a violation",
        list(event_by_id),
        format_func=lambda event_id: (
            f"#{event_id} — {format_violation_type(event_by_id[event_id]['violation_type'])} "
            f"— {event_by_id[event_id]['camera_id']}"
        ),
    )
    selected_event = next(event for event in events if event["id"] == selected_id)
    frame_path = local_frame_path(selected_event.get("frame_uri"))

    image_col, detail_col = st.columns([3, 2])
    if frame_path:
        image_col.image(
            str(frame_path),
            caption=f"Visual evidence for recorded event #{selected_id}",
            use_container_width=True,
        )
        image_col.success("Visual evidence is available for human review.")
    else:
        image_col.warning(
            "⚠️ VISUAL PROOF IS NOT AVAILABLE FOR THIS RECORD. "
            "Do not treat it as visually verified."
        )

    detail_col.markdown(
        f"### {format_violation_type(selected_event['violation_type'])}"
    )
    detail_col.write(f"**Camera:** {selected_event['camera_id']}")
    detail_col.write(f"**Worker track:** {selected_event.get('track_id', 'unknown')}")
    detail_col.write(
        f"**Occurred:** {format_timestamp(selected_event.get('occurred_at'))}"
    )
    detail_col.metric(
        "Model confidence", f"{float(selected_event['confidence']) * 100:.1f}%"
    )
    detail_col.caption(
        "Confidence is model certainty, not proof that the violation is correct."
    )

    with st.expander("View all matching records"):
        table_rows = [
            {
                "id": event["id"],
                "time": format_timestamp(event.get("occurred_at")),
                "camera": event["camera_id"],
                "violation": format_violation_type(event["violation_type"]),
                "confidence": event["confidence"],
                "proof": "available" if local_frame_path(event.get("frame_uri")) else "missing",
            }
            for event in events
        ]
        st.dataframe(table_rows, use_container_width=True, hide_index=True)
        st.json(selected_event)

with st.expander("3. Technical system details — optional"):
    health_report = load_health_report()
    st.markdown("#### Worker and Kafka health")
    if health_report is None:
        st.info("No live worker-health report is available.")
    else:
        checked_at = datetime.fromisoformat(
            health_report["checked_at"].replace("Z", "+00:00")
        )
        report_age_seconds = (datetime.now(timezone.utc) - checked_at).total_seconds()
        report_is_stale = report_age_seconds > 30
        health_columns = st.columns(3)
        health_columns[0].metric(
            "Pipeline health",
            "stale" if report_is_stale else health_report.get("status", "unknown"),
        )
        health_columns[1].metric(
            "Active alerts", len(health_report.get("alerts", []))
        )
        health_columns[2].metric(
            "Last check", format_timestamp(health_report.get("checked_at"))
        )
        for alert in health_report.get("alerts", []):
            st.warning(alert)
        lag_rows = [
            {
                "stage": name,
                "topic": result.get("topic"),
                "consumer group": result.get("group_id"),
                "lag": result.get("total_lag"),
                "error": result.get("error"),
            }
            for name, result in health_report.get("kafka", {}).items()
        ]
        st.dataframe(lag_rows, use_container_width=True, hide_index=True)

    st.markdown("#### Drift and data quality")
    drift_report = load_drift_report()
    quality_report = load_quality_report()
    technical_columns = st.columns(2)
    if drift_report is None:
        technical_columns[0].info("No drift report is available.")
    else:
        technical_columns[0].metric(
            "Input distribution", drift_report.get("status", "unknown")
        )
        technical_columns[0].caption(drift_report.get("interpretation", ""))
    if quality_report is None:
        technical_columns[1].info("No event-quality report is available.")
    else:
        technical_columns[1].metric(
            "Event data quality", quality_report.get("status", "unknown")
        )
        technical_columns[1].write(
            f"{quality_report.get('expectation_count', 0)} checks, "
            f"{quality_report.get('failed_expectation_count', 0)} failures"
        )

    if run_summaries:
        st.markdown("#### Selected run checkpoints")
        stage_rows = [
            {"stage": stage.replace("_", " "), "result": result}
            for stage, result in selected_run.get("stages", {}).items()
        ]
        st.dataframe(stage_rows, use_container_width=True, hide_index=True)

with st.expander("Ask the read-only SafeSite assistant"):
    st.caption("The answer is grounded in approved read-only SQL.")
    question = st.text_input(
        "Question about recorded violations", "How many violations are there?"
    )
    if st.button("Ask SafeSite"):
        try:
            agent_result = post_json(AGENT_URL, "/ask", {"question": question})
        except RuntimeError as error:
            st.error(str(error))
        else:
            st.success(agent_result["answer"])
            st.caption(f"Answer provider: {agent_result['answer_provider']}")
            st.code(agent_result["sql"], language="sql")
            st.write("Parameters", agent_result["parameters"])
            st.dataframe(agent_result["rows"], use_container_width=True, hide_index=True)
