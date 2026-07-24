# PySpark Job Image — AWS EKS
# This image runs the same src/core transformations that run on Databricks.
#
# Build: docker build -f platforms/aws/docker/Dockerfile -t pos-retail-spark:latest .
# Run:   Deployed via SparkApplication CRDs (see k8s/manifests/)

# Base image: Official Apache Spark with Python 3.11
# Pinned by digest for reproducibility (update with scripts/update_base_image.sh)
FROM apache/spark:3.5.0-python3@sha256:TODO_FETCH_DIGEST

USER root

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /opt/spark/work-dir

# Copy Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy platform-agnostic transformation code
COPY src/core /opt/spark/work-dir/src/core

# Copy AWS platform adapter utilities
COPY platforms/aws/scripts /opt/spark/work-dir/scripts

# Set PYTHONPATH so imports work
ENV PYTHONPATH="/opt/spark/work-dir:${PYTHONPATH}"

# Create directories for Delta Lake checkpoints
RUN mkdir -p /tmp/delta-lake /tmp/spark-warehouse \
    && chmod -R 777 /tmp/delta-lake /tmp/spark-warehouse

# Run as non-root user (Spark Operator creates service account)
USER 185

ENTRYPOINT ["/opt/entrypoint.sh"]
