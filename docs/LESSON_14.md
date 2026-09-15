# Lesson 14: Kafka and MinIO Foundations

## Goal

Understand why the large architecture needs both Kafka and MinIO, then verify
that each service is healthy and persistent before connecting ingestion.

## 1. The simple difference

Kafka and MinIO do not store the same kind of thing.

```text
Kafka = ordered messages moving between services
MinIO = large files kept as durable objects
```

For one sampled frame:

```text
MinIO stores: the JPEG bytes
Kafka stores: camera ID, timestamp, MinIO URI, and processing metadata
```

We avoid putting full images in Kafka because images are large. The Kafka
message stays small and points to the real image in MinIO.

## 2. Why Kafka exists

Without Kafka, ingestion would call inference directly:

```text
ingestion -> inference
```

If inference is slow or stopped, ingestion must wait or lose work.

With Kafka:

```text
ingestion -> Kafka topic -> inference consumer
```

Kafka keeps ordered records. Ingestion and inference can run at different
speeds, and the consumer can resume from its last committed offset.

Important words:

- **Topic:** named stream of records, such as `safesite.frames.raw`.
- **Partition:** ordered section of a topic that enables parallel processing.
- **Producer:** service that sends records.
- **Consumer:** service that reads records.
- **Offset:** position of one record inside one partition.
- **Consumer lag:** records produced but not processed yet.

We created three partitions. Later, the camera ID will be the message key so
frames from one camera remain ordered while different cameras can run in
parallel.

## 3. Why MinIO exists

MinIO exposes an S3-compatible object-storage API. It will contain:

```text
bronze/ -> raw clips and sampled frames
silver/ -> annotated frames and detection JSON
gold/   -> aggregated analytical files
```

PostgreSQL stores the searchable event row. Its `frame_uri` points to MinIO
instead of storing JPEG bytes inside the database.

## 4. Local service addresses

```text
Kafka from Windows:          localhost:9092
Kafka inside Docker:         kafka:29092
MinIO S3 API:                http://localhost:9000
MinIO web console:           http://localhost:9001
MinIO inside Docker:         http://minio:9000
```

Kafka needs two advertised listeners because `localhost` means different
machines inside and outside Docker.

## 5. KRaft mode

Kafka `4.3.1` runs in KRaft mode. Kafka manages cluster metadata itself, so this
single-node learning environment does not need ZooKeeper.

This local node has both roles:

```text
broker     -> stores topic records and serves producers/consumers
controller -> manages cluster metadata and leadership
```

Production normally separates or replicates these roles across several nodes.

## 6. Persistence proof

We created:

```text
topic: safesite.frames.raw
partitions: 3
replication factor: 1
```

Then we restarted Kafka. The topic still existed because `kafka_data` is a
named Docker volume.

MinIO stores `/data` in the separate `minio_data` named volume. Its official
liveness endpoint returned HTTP `200`, and the web console also returned HTTP
`200`.

## 7. Current safety boundary

This setup is correct for local development, not production:

- Kafka has one node and replication factor `1`.
- Kafka and MinIO use plaintext local networking.
- MinIO uses development credentials.
- MinIO has one storage node and one data volume.
- Authentication, TLS, replication, backups, and monitoring come later.

The official references are the [Apache Kafka Docker guide](https://kafka.apache.org/43/getting-started/docker/)
and the [MinIO health-check documentation](https://min.io/docs/minio/linux/operations/monitoring/healthcheck-probe.html).

## Explain it aloud

Explain why SafeSite stores the JPEG in MinIO but sends only its metadata and
object URI through Kafka.
