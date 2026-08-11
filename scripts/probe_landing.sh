#!/usr/bin/env bash
# Verify the All-Members landing URL against THIS deployment:
#   1. login as the given user
#   2. GET /webclient/?experimenter=-1  (should set session owner filter = All Members)
#   3. re-GET /webclient/ WITHOUT params (does the session remember -1?)
#   4. honest own-view vs all-view counts via the containers API (param is `id`,
#      NOT `experimenter_id` -- the latter is silently ignored)
# Run inside WSL:  bash probe_landing.sh <username> <password> <own-id> [base-url]
set -u
USER_=${1:?username}; PASS_=${2:?password}; OWN=${3:?own experimenter id}
BASE_URL=${4:-http://localhost:4080}
J=$(mktemp); trap 'rm -f "$J" /tmp/landing.html' EXIT

page=$(curl -s -c "$J" "$BASE_URL/webclient/login/")
csrf=$(printf '%s' "$page" | grep -o 'name="csrfmiddlewaretoken" value="[^"]*' | sed 's/.*value="//')
curl -s -b "$J" -c "$J" -o /dev/null \
  -H "Referer: $BASE_URL/webclient/login/" \
  --data-urlencode "csrfmiddlewaretoken=$csrf" \
  --data-urlencode "server=1" \
  --data-urlencode "username=$USER_" \
  --data-urlencode "password=$PASS_" \
  "$BASE_URL/webclient/login/"

count() {
  curl -s -b "$J" "$BASE_URL/webclient/api/containers/?id=$1" \
    | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["projects"]))'
}
echo "own view (id=$OWN):        $(count "$OWN") projects"
echo "all members (id=-1):     $(count -1) projects"

active() {
  grep -o "active_user[^,}]*" /tmp/landing.html | head -2
}
curl -s -b "$J" -c "$J" -o /tmp/landing.html "$BASE_URL/webclient/?experimenter=-1"
echo "after ?experimenter=-1 landing: $(active)"
curl -s -b "$J" -c "$J" -o /tmp/landing.html "$BASE_URL/webclient/"
echo "plain /webclient/ afterwards:   $(active)"
