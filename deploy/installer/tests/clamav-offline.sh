#!/usr/bin/env bash
# Release gate: the ClamAV image in the bundle must carry a virus database and start without
# internet access, because customer servers may have none.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
image="$(ASSAYR_VERSION=unused POSTGRES_PASSWORD=unused \
  docker compose -f "$HERE/../../compose.yaml" --profile av config --images | grep '^clamav/')"
docker image inspect "$image" >/dev/null 2>&1 || docker pull "$image" >/dev/null

docker run --rm --network none --entrypoint sh "$image" -c 'ls /var/lib/clamav/*.c?d' \
  || { echo "The image $image has no virus database" >&2; exit 1; }

name=assayr-clamav-offline-check
docker rm -f "$name" >/dev/null 2>&1 || true
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$name" --network none "$image" >/dev/null
for _ in $(seq 1 60); do
  if docker logs "$name" 2>&1 | grep -q 'clamd started'; then
    echo "$image starts and loads its virus database without internet access"
    exit 0
  fi
  sleep 5
done
docker logs "$name" 2>&1 | tail -n 40
echo "$image did not start without internet access" >&2
exit 1
