# Lesson 16: Consume a Kafka Frame and Download It from MinIO

## Goal

Build the receiving side of the frame pipeline:

```text
Kafka frame event -> consumer -> MinIO download -> local verified JPEG
```

The consumer is `services/ingestion/app/consume_frames.py`.

## What the consumer does

For one Kafka message, it performs these operations in order:

1. read the message from `safesite.frames.raw`;
2. verify that the value is valid UTF-8 JSON;
3. verify the frame-event fields and schema version;
4. verify that the Kafka key equals `camera_id`;
5. parse the `s3://bucket/object` URI;
6. download the JPEG from MinIO to a temporary file;
7. atomically rename the completed JPEG;
8. write a JSON evidence record;
9. commit the Kafka offset.

The offset is committed last so Kafka does not consider the event complete before
the image and its evidence record are safely written.

## Consumer group

The verified run used this consumer group:

```text
lesson-16-20260818
```

A consumer group is a team of consumers sharing work from one topic. Kafka keeps
an independent committed position for every group. A new group can read the topic
from the beginning without changing another group's position.

If three consumers belong to one group and the topic has three partitions, Kafka
can assign one partition to each consumer. Two consumers in the same group do not
normally process the same partition simultaneously.

## Offset and commit

The frame message was stored at:

```text
partition = 2
offset = 0
```

An offset is the message's position inside one partition. After successfully
processing offset `0`, the consumer committed next offset `1`. This means:

> The next message this group should read from partition 2 is offset 1.

Kafka reported:

```text
CURRENT-OFFSET = 1
LOG-END-OFFSET = 1
LAG = 0
```

`LAG = 0` means this consumer group has processed every currently available
message in that partition.

## Why disable automatic commits?

With automatic commits, Kafka may save progress because a message was delivered
to Python, even if MinIO downloading or YOLO processing later fails.

SafeSite uses a manual commit:

```text
receive -> validate -> download -> save evidence -> commit
```

If the process crashes before the commit, Kafka can deliver the event again. This
is called at-least-once processing. A replay is safer than silently losing a
frame, but consumers must make repeated processing harmless.

## Replay safety

The output JPEG and JSON filenames use the deterministic `event_id`. Processing
the same event again replaces the same files atomically instead of creating a new
random filename.

This is not complete exactly-once processing, but it gives the consumer a clear
idempotency key for later database and inference-result protection.

## Atomic download

The consumer first downloads to:

```text
<event_id>.jpg.part
```

Only after the download succeeds does it rename the file to:

```text
<event_id>.jpg
```

Therefore, another process does not mistake a half-downloaded file for a complete
JPEG.

## Verified result

The consumer downloaded one `186640`-byte JPEG. The original frame and downloaded
frame had the same SHA256:

```text
c2e22e944fecf184f89347d2fcf8e6b46853d8e3ca22ab863655c0155dba90e2
```

This proves that the image bytes survived:

```text
local source -> MinIO upload -> MinIO download -> local consumer output
```

It proves transport correctness, not whether the image contains a PPE violation.

## Reproduce the test

```powershell
docker compose --profile tools build ingestion
docker compose --profile tools run --rm ingestion python -m app.consume_frames `
  --group-id lesson-16-your-name `
  --output-dir /data/streaming/lesson-16-your-name `
  --max-messages 1
```

Use a new group ID when you intentionally want to read the existing topic from
its earliest message.

Inspect group progress:

```powershell
docker compose exec kafka /opt/kafka/bin/kafka-consumer-groups.sh `
  --bootstrap-server localhost:9092 `
  --describe `
  --group lesson-16-your-name
```

## What comes next?

The next change will put YOLO after the download:

```text
Kafka -> consumer -> MinIO JPEG -> YOLO -> detection JSON
```

The consumer must still commit only after the required processing output has been
saved successfully.

## Explain it aloud

Why do we commit the Kafka offset after downloading and saving the frame instead
of immediately after receiving the message?
