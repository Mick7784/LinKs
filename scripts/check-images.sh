#!/usr/bin/env bash
# Only disposable CI containers and tmpfs data; never a deployed instance or volume.
set -euo pipefail
version=${1:-$(cat VERSION)}
version=${version:-$(cat VERSION)}
revision=${2:-$(git rev-parse HEAD)}
container=links-architecture-check
cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT
native_architecture=$(uname -m)
case "$native_architecture" in x86_64) native_architecture=amd64;; aarch64) native_architecture=arm64;; esac
for architecture in ${LINKS_CHECK_ARCHITECTURES:-amd64 arm64}; do
  docker buildx build --platform "linux/$architecture" --load --tag "links-check-$architecture" \
    --build-arg "APP_RELEASE_VERSION=$version" --build-arg "APP_RELEASE_ID=$version:$revision" \
    --label "org.opencontainers.image.version=$version" --label "org.opencontainers.image.revision=$revision" .
  docker run -d --platform "linux/$architecture" --name "$container" --read-only \
    --tmpfs /data:rw,nosuid,size=64m,mode=1777 --tmpfs /tmp:rw,noexec,nosuid,size=512m,mode=1777 \
    --cap-drop ALL --security-opt no-new-privileges:true \
    -p 127.0.0.1:28080:8080 -p 127.0.0.1:28081:8081 "links-check-$architecture"
  for attempt in $(seq 1 40); do
    if curl -fsS http://127.0.0.1:28080/healthz; then break; fi
    sleep 1
  done
  bootstrap=$(docker exec "$container" cat /data/setup-code)
  python3 scripts/smoke.py http://127.0.0.1:28080 http://127.0.0.1:28081 "$bootstrap"
  python3 -c 'import json,sys,urllib.request; data=json.load(urllib.request.urlopen("http://127.0.0.1:28080/api/public-config")); assert data["profile"]["app_version"]==sys.argv[1],data' "$version"
  docker exec "$container" python3 -c 'import sqlite3; assert sqlite3.sqlite_version_info >= (3,35,0),sqlite3.sqlite_version; db=sqlite3.connect("/data/analytics.db"); assert "category" not in {row[1] for row in db.execute("PRAGMA table_info(tracked_links)")}; assert db.execute("PRAGMA integrity_check").fetchone()[0]=="ok"; assert not list(db.execute("PRAGMA foreign_key_check")); db.close()'
  # Chromium's GPU subprocess cannot be qualified reliably under QEMU. The
  # required arm-runtime CI job executes this same image check on native ARM64.
  if [ "$architecture" = "$native_architecture" ]; then
    docker exec -i "$container" node --input-type=module < scripts/affiliation-runtime-smoke.mjs
  else
    echo "Chromium $architecture is gated by its native runner; application smoke passed under emulation."
  fi
  docker logs "$container"
  cleanup
done
