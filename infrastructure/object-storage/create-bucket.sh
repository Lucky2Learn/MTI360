#!/bin/sh
# =============================================================================
# MTI 360 — local object-storage bucket initialisation (T00-03)
# =============================================================================
#
# Executed by the one-shot `object-storage-init` Compose service after the
# SeaweedFS `object-storage` service is healthy. Creates the private
# application bucket through the SeaweedFS admin shell.
#
# Idempotent: re-running when the bucket already exists succeeds.
#
# The bucket is PRIVATE: the S3 gateway is started with an admin identity
# taken from S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY, so anonymous requests are
# denied. No bucket policy granting public access is ever applied.
# =============================================================================
set -eu

: "${S3_BUCKET:?S3_BUCKET must be set}"
: "${SEAWEEDFS_HOST:=object-storage}"

printf 's3.bucket.create -name %s\nexit\n' "$S3_BUCKET" \
  | weed shell -master="${SEAWEEDFS_HOST}:9333" -filer="${SEAWEEDFS_HOST}:8888"

echo "MTI 360: private bucket '${S3_BUCKET}' is ready."
