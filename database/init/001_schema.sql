CREATE TABLE IF NOT EXISTS violations (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL,
    camera_id VARCHAR(64) NOT NULL,
    track_id BIGINT NOT NULL,
    violation_type VARCHAR(32) NOT NULL
        CHECK (violation_type IN ('NO_HELMET', 'NO_VEST', 'NO_MASK')),
    confidence REAL NOT NULL
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    frame_uri TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_violations_occurred_at
    ON violations (occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_violations_camera_type_time
    ON violations (camera_id, violation_type, occurred_at DESC);

INSERT INTO violations (
    occurred_at,
    camera_id,
    track_id,
    violation_type,
    confidence,
    frame_uri
)
VALUES
    (NOW() - INTERVAL '15 minutes', 'camera-01', 101, 'NO_HELMET', 0.94, 'silver/camera-01/event-101.jpg'),
    (NOW() - INTERVAL '10 minutes', 'camera-01', 102, 'NO_VEST', 0.88, 'silver/camera-01/event-102.jpg'),
    (NOW() - INTERVAL '5 minutes', 'camera-02', 201, 'NO_HELMET', 0.91, 'silver/camera-02/event-201.jpg');

