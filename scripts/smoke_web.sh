#!/usr/bin/env bash
# End-to-end web smoke test: login as a trial user, fetch a thumbnail AND a
# rendered plane (the render exercises the ln_s symlink -> D:\ pixel path).
# Run inside WSL:  bash smoke_web.sh [base-url]   (default http://localhost:4080)
set -u
BASE_URL=${1:-http://localhost:4080}
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO/accounts.env"
J=$(mktemp); trap 'rm -f "$J" /tmp/omero_thumb.jpg /tmp/omero_plane.jpg' EXIT

page=$(curl -s -c "$J" "$BASE_URL/webclient/login/")
csrf=$(printf '%s' "$page" | grep -o 'name="csrfmiddlewaretoken" value="[^"]*' | sed 's/.*value="//')
if [ -z "$csrf" ]; then echo "FAIL: no csrf token"; exit 1; fi

curl -s -b "$J" -c "$J" -o /dev/null -w "login POST -> %{http_code} (302 = success)\n" \
  -H "Referer: $BASE_URL/webclient/login/" \
  --data-urlencode "csrfmiddlewaretoken=$csrf" \
  --data-urlencode "server=1" \
  --data-urlencode "username=$OMERO_TRIAL1_USER" \
  --data-urlencode "password=$OMERO_TRIAL1_PASS" \
  "$BASE_URL/webclient/login/"

curl -s -L -b "$J" -o /tmp/omero_thumb.jpg \
  -w "thumbnail -> %{http_code}, %{size_download} bytes\n" \
  "$BASE_URL/webclient/render_thumbnail/2/"
curl -s -L -b "$J" -o /tmp/omero_plane.jpg \
  -w "rendered plane -> %{http_code}, %{size_download} bytes\n" \
  "$BASE_URL/webclient/render_image/2/0/0/"
file /tmp/omero_thumb.jpg /tmp/omero_plane.jpg
