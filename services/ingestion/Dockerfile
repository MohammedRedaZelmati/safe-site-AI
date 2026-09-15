FROM ultralytics/ultralytics:8.4.107-python@sha256:a3f950c1d318397b86ee801899170957658bd91b549bc2d633a5cfc0c158fab0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
COPY vendor /tmp/vendor
RUN python -m pip install --no-cache-dir --no-index --find-links=/tmp/vendor \
        -r requirements.txt /tmp/vendor/lap-*.whl \
    && rm -rf /tmp/vendor

COPY app ./app

CMD ["python", "-m", "app.sample_frames", "--help"]
