#!/bin/bash
# Create MinIO buckets required by the pipeline
# Run after minio-service is deployed and running
#
# Usage: ./manifests/minio/create-buckets.sh

set -e

NAMESPACE="${NAMESPACE:-data-strat-poc}"

echo "Creating MinIO bucket setup job..."
oc run minio-setup \
  --image=quay.io/minio/mc:latest \
  --restart=Never \
  -n "$NAMESPACE" \
  --env="MC_CONFIG_DIR=/tmp/.mc" \
  --command -- sh -c '
    mc alias set minio http://minio-service:9000 minio minio123 &&
    mc mb minio/rag-chunks --ignore-existing &&
    mc mb minio/pipeline-artifacts --ignore-existing &&
    echo "Buckets created successfully"
  '

echo "Waiting for bucket creation..."
oc wait --for=condition=Ready pod/minio-setup -n "$NAMESPACE" --timeout=60s 2>/dev/null || true
sleep 10
oc logs minio-setup -n "$NAMESPACE"
oc delete pod minio-setup -n "$NAMESPACE" --ignore-not-found
echo "Done."
