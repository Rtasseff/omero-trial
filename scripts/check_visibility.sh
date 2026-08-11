#!/usr/bin/env bash
# Diagnose the "I log in and see nothing" report: logs into OMERO.web as the
# given user and prints the project count under (a) their own-data filter and
# (b) All Members. If (a)=0 and (b)>0, permissions are fine - the tree's owner
# filter is just on its default (the logged-in user, who owns no containers).
# Fix: give testers the landing link  <base-url>/webclient/?experimenter=-1
# (explicitly supported; sets the session's owner filter to All Members).
# NOTE: the containers endpoint's owner parameter is `id` - an
# `experimenter_id` parameter is silently ignored (that mistake once produced
# a false "own view shows everything" conclusion here).
# Run inside WSL:  bash check_visibility.sh <username> <password> <own-id> [base-url]
set -u
USER_=${1:?username}; PASS_=${2:?password}; OWN=${3:?own experimenter id}
BASE_URL=${4:-http://localhost:4080}
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
  curl -s -b "$J" "$BASE_URL/webclient/api/containers/?id=$1" \
    | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["projects"]))'
}
echo "own-data filter (id=$OWN):  $(count "$OWN") projects"
echo "All Members (id=-1):      $(count -1) projects"
