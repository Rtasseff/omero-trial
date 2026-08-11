#!/usr/bin/env bash
# Diagnose the "I log in and see nothing" report: logs into OMERO.web as the
# given user and prints how many projects the whole-group view returns. If
# this is >0 while the user's tree looks empty in the browser, permissions are
# fine - they just need to switch the owner dropdown above the data tree to
# All Members.
# CAUTION (learned 2026-08-11): this containers endpoint IGNORES an
# experimenter_id query parameter - do not use it to test the own-data filter;
# that once produced a false "own view shows everything" conclusion. The
# browser UI is the only honest test of the owner filter.
# Run inside WSL:  bash check_visibility.sh <username> <password> [base-url]
set -u
USER_=${1:?username}; PASS_=${2:?password}
BASE_URL=${3:-http://localhost:4080}
OWN_ID=""
J=$(mktemp); trap 'rm -f "$J"' EXIT

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
  curl -s -b "$J" "$BASE_URL/webclient/api/containers/?experimenter_id=$1" \
    | python3 -c 'import json,sys
d = json.load(sys.stdin)
print("projects=%d orphaned_images=%d" % (len(d.get("projects", [])),
      (d.get("orphaned") or {}).get("childCount", 0)))'
}
if [ -n "$OWN_ID" ]; then
  echo "own-filter view (id $OWN_ID):  $(count "$OWN_ID")"
fi
echo "All Members view:          $(count -1)"
