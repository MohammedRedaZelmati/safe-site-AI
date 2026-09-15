# Lesson 25: Multi-Camera Kafka Partitioning and Tracking State

## Goal

Process several cameras without mixing worker identities or temporal evidence.

## Kafka key rule

Every producer uses `camera_id` as the Kafka message key. Kafka always sends the
same key to the same partition.

```text
camera key -> stable partition -> ordered events
```

Different camera keys may share one partition. The guarantee is stable placement
and order per key, not one exclusive partition per camera.

## Isolated tracking state

The tracking worker now keeps separate state per camera:

- one persistent ByteTrack/YOLO instance;
- one temporal sliding-window engine;
- one previous sample index;
- camera-scoped identities such as `camera-proof-02:1`.

The default capacity is three cameras and is configurable with
`SAFESITE_MAX_CAMERAS`.

## Scaling

Several inference or tracking containers can share the same consumer group. Kafka
assigns each partition to only one member of that group. Since one camera key stays
on one partition, its ordered state stays with one active worker.

## Verified result

Three cameras produced three PPE events. Tracking processed all three with:

```text
cameras: 3
camera-scoped track identities: 6
helmet associations: 6
boot associations: 3
state collisions: 0
```

## Explain it aloud

Why can two cameras share one Kafka partition without mixing their tracking state?
