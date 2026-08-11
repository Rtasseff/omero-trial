"""Faithful probes of the webclient tree API for a given login + owner filter.

Prints, for the given experimenter-filter id (use -1 for All Members):
  - project count (and whether a specific project is present)
  - dataset count under --project
  - image count under --dataset
Endpoints and parameter names match omero-web master (owner param is `id`).

Run inside WSL:
  python3 probe_views.py <user> <pass> <filter-id> [--project N] [--dataset N] [--base URL]
"""
import http.cookiejar
import json
import re
import sys
import urllib.parse
import urllib.request

args = sys.argv[1:]
user, pw, fid = args[0], args[1], args[2]
base = "http://localhost:4080"
project = dataset = None
for i, a in enumerate(args):
    if a == "--project":
        project = args[i + 1]
    if a == "--dataset":
        dataset = args[i + 1]
    if a == "--base":
        base = args[i + 1]

jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

page = op.open(base + "/webclient/login/").read().decode()
csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page).group(1)
data = urllib.parse.urlencode({"csrfmiddlewaretoken": csrf, "server": "1",
                               "username": user, "password": pw}).encode()
req = urllib.request.Request(base + "/webclient/login/", data=data,
                             headers={"Referer": base + "/webclient/login/"})
op.open(req)

def get(path, **params):
    q = urllib.parse.urlencode(params)
    with op.open(f"{base}{path}?{q}") as r:
        return json.loads(r.read().decode())

c = get("/webclient/api/containers/", id=fid)
projs = c.get("projects", [])
print(f"filter id={fid}: {len(projs)} projects; orphaned childCount="
      f"{(c.get('orphaned') or {}).get('childCount', 0)}")
if project:
    hit = [p for p in projs if str(p.get("id")) == str(project)]
    print(f"  project {project} in list: {bool(hit)}"
          + (f" (name: {hit[0].get('name')})" if hit else ""))
    d = get("/webclient/api/datasets/", id=fid, page=1, project=project)
    print(f"  datasets under project {project}: {len(d.get('datasets', []))}")
if dataset:
    im = get("/webclient/api/images/", id=fid, page=1, dataset=dataset)
    print(f"  images under dataset {dataset}: {len(im.get('images', []))}")
