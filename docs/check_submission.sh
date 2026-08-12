#!/usr/bin/env bash
# Thin wrapper so `docker run ...` doesn't require students to know
# Docker's volume-mount syntax -- `docker run` on its own can't see
# anything on the host unless you mount it in, so a bare
# `docker run noam1023/check-submission .` would only ever see an empty
# container filesystem. This script does the mount, then just execution.
# This is the ONLY distributed method -- students need nothing but this
# one file and Docker itself; `docker run` auto-pulls the image from
# Docker Hub the first time it's needed, no `docker build`/repo clone
# required.
#   ./check_submission.sh path/to/your-submission.zip
#   ./check_submission.sh .
set -euo pipefail

IMAGE="noam1023/check-submission:latest"
TARGET="${1:-.}"

if [ ! -e "$TARGET" ]; then
    echo "error: $TARGET does not exist" >&2
    exit 1
fi

if [ -d "$TARGET" ]; then
    HOST_DIR="$(cd "$TARGET" && pwd)"
    docker run --rm -v "$HOST_DIR":/data:ro "$IMAGE" /data
else
    HOST_DIR="$(cd "$(dirname "$TARGET")" && pwd)"
    BASENAME="$(basename "$TARGET")"
    docker run --rm -v "$HOST_DIR":/data:ro "$IMAGE" "/data/$BASENAME"
fi
