#!/usr/bin/env bash
# Diagnose the "I log in and see nothing" report: logs into OMERO.web as the
# given user and prints how many projects the data tree returns when filtered
# to (a) that user's own data and (b) All Members (experimenter_id=-1).
# If (a)=0 and (b)>0, permissions are fine - the user just needs to switch the
# owner dropdown above the data tree (or use the ?experimenter=-1 link).
# Run inside WSL:  bash check_visibility.sh <username> <password> [base-url]
set -u
USER_=${1:?username}; PASS_=${2:?password}
BASE_URL=${3:-http://localhost:4080}
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

uid=$(curl -s -b "$J" "$BASE_URL/webapi/whoami/" 2>/dev/null | python3 -c 'import json,sys
try: print(json.load(sys.stdin)["id"])
except Exception: print("")')
if [ -z "$uid" ]; then
  # fallback: webclient active user endpoint
  uid=$(curl -s -b "$J" "$BASE_URL/api/v0/m/experimenters/?limit=500" | python3 -c 'import json,sys
d=json.load(sys.stdin); print("")' 2>/dev/null)
fi

count() {
  curl -s -b "$J" "$BASE_URL/webclient/api/containers/?experimenter_id=$1" \
    | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["projects"]))'
}
if [ -n "$uid" ]; then
  echo "projects owned by $USER_ (id $uid): $(count "$uid")"
fi
echo "projects visible as All Members:   $(count -1)"
