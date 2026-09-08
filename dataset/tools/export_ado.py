#!/usr/bin/env python3
"""Export the ADO story matrix into dataset/stories/ as re-keyed JSON files.

Design (Phase 3 increment 1, D9):
- Case id = "<template>/<scenario>" (e.g. "t3/conflicting"); one story file
  per test case, one folder per template. Context items (epic + features)
  go to stories/context/ — they are hierarchy context, not test cases.
- Each story file is an envelope + the verbatim ADO work-item JSON under
  "work_item". Fidelity decisions (trimming, HTML) happen in a SEPARATE
  later step against these files — never transformed on the fly.
- ADO ids are temporary authoring references: the scenario is resolved via
  the provenance lines in dataset/canonical-facts.md (the authoritative
  id map), the template via the area path. The ADO id survives only as
  ado_source_id provenance.
- "_links" keys are stripped recursively: they contain org URLs (identifier
  leak into git) and volatile avatar hrefs; everything else is verbatim.

Aborts loudly (exit 1) on any unknown id, missing story, duplicate case id,
or area-path/provenance template mismatch. Expected counts are asserted:
42 stories + 3 context items.

Usage:
    set -a; source infra/envs/ado.env; set +a
    python3 dataset/tools/export_ado.py
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STORIES_DIR = REPO / "dataset" / "stories"
CANONICAL = REPO / "dataset" / "canonical-facts.md"
T5SPEC = REPO / "dataset" / "t5-enabler-spec.md"
COMMENTSSPEC = REPO / "dataset" / "comments-stories-spec.md"
CONTEXT_IDS = {2, 3, 4}  # epic + two features
EXPECTED_STORIES = 45
TEMPLATE_BY_AREA = {None: "t1", "T2": "t2", "T3": "t3", "T4": "t4", "T5": "t5", "T6": "t6"}
SLUGS = [
    "clean", "business-weak", "engineering-weak", "conflicting",
    "partial-resolution", "unresolvable", "hidden-conflict",
]
# t1-only comment scenarios (dataset extensions, D9 amendment 3): not part
# of the template-major grid; numbered 43+ after the 42 core stories.
T1_ONLY_SLUGS = [
    "comments-benign", "comments-clarify-business",
    "comments-complete-engineering",
]
FIRST_T1_ONLY_ID = 43


def _sorted_keys(obj):
    """Recursively sort dict keys (matches the az-era serialization; keeps
    re-export diffs minimal — only exported_at changes on unchanged data)."""
    if isinstance(obj, dict):
        return {k: _sorted_keys(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sorted_keys(v) for v in obj]
    return obj


def use_rest() -> bool:
    """True when ADO_PAT is set: fetch via REST (Runbook 08 equivalence
    check, 2026-09-08 — GET workitems/{id}?$expand=all is byte-equivalent
    to the az fetch). This mirrors the production fetch route; the az CLI
    path remains the fallback when no PAT is configured."""
    return bool(os.environ.get("ADO_PAT"))


def _ado_cli(*args: str) -> dict:
    org = os.environ.get("ADO_ORG")
    if not org:
        sys.exit("ADO_ORG not set (set -a; source infra/envs/ado.env; set +a)")
    r = subprocess.run(
        ["az", "boards", *args, "--org", f"https://dev.azure.com/{org}", "--output", "json"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        sys.exit(f"az failed: {' '.join(args[:3])}\n{r.stderr}")
    return json.loads(r.stdout)


def _rest(method: str, path: str, body: dict | None = None, api_version: str = "7.1") -> dict:
    """One Azure DevOps REST call with PAT basic auth."""
    org = os.environ["ADO_ORG"]
    token = base64.b64encode(f":{os.environ['ADO_PAT']}".encode()).decode()  # guarded by main()
    url = f"https://dev.azure.com/{org}/{path}"
    url += f"&api-version={api_version}" if "?" in path else f"?api-version={api_version}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        sys.exit(f"REST {method} {path} failed: HTTP {exc.code}\n{exc.read().decode()[:500]}")
    except urllib.error.URLError as exc:
        sys.exit(f"REST {method} {path} failed: {exc.reason}")


def query_ids(project: str) -> list[int]:
    """WIQL query returning every story/epic/feature id, sorted."""
    wiql = (
        "SELECT [System.Id] FROM WorkItems "
        "WHERE [System.TeamProject] = '{p}' "
        "AND [System.WorkItemType] IN ('User Story', 'Epic', 'Feature') "
        "ORDER BY [System.Id]"
    ).format(p=project)
    if use_rest():
        result = _rest("POST", f"{project}/_apis/wit/wiql", {"query": wiql})
        return sorted(item["id"] for item in result["workItems"])
    rows = _ado_cli("query", "--wiql", wiql)
    return sorted(
        int(list(r.values())[0]) if not r.get("id") else int(r["id"]) for r in rows
    )


def show_item(project: str, wid: int) -> dict:
    """Fetch one work item with full expansion (all fields + relations).

    REST: single-item GET with $expand=all — the full-fidelity shape
    verified byte-equivalent to `az boards work-item show --expand all`.
    """
    if use_rest():
        return _rest("GET", f"{project}/_apis/wit/workitems/{wid}?$expand=all")
    return _ado_cli("work-item", "show", "--id", str(wid), "--expand", "all")


def fetch_comments(project: str, wid: int) -> list[dict]:
    """Fetch a work item's comments, sanitized like the work item itself.

    Comments are NOT part of the work-item payload — they need the comments
    API (GET workItems/{id}/comments, Runbook 08 equivalence family; the
    endpoint is preview-only: api-version 7.1-preview.4). The az boards CLI
    has no comments command, and `az rest` cannot authenticate with an MSA
    login (AADSTS500011, Runbook 08) — so comments-bearing exports REQUIRE
    the REST mode (ADO_PAT set); az mode aborts loudly if a story turns out
    to have comments.

    Returns the comments in chronological order (the API returns newest
    first); [] when the item has none (the envelope then omits the comments
    key entirely — pre-extension story files stay byte-stable).
    """
    if not use_rest():
        sys.exit(
            f"id {wid}: comments require the REST mode (set ADO_PAT; the az "
            "fallback cannot call the comments API — Runbook 08)"
        )
    raw = _rest(
        "GET",
        f"{project}/_apis/wit/workItems/{wid}/comments",
        api_version="7.1-preview.4",
    )
    org = os.environ["ADO_ORG"]
    comments = [
        anonymize_identities(sanitize_urls(strip_links(c), org))
        for c in raw.get("comments", [])
    ]
    return sorted(comments, key=lambda c: c["createdDate"])


def anonymize_identities(obj):
    """Replace author identity fields with placeholders (owner decision:
    personal data must not enter git / the public mirror).

    Applies to identity objects under work_item.fields (System.CreatedBy,
    System.ChangedBy, System.AuthorizedAs, System.AssignedTo, ...):
    uniqueName -> "<author>@example.com", displayName -> "Story Author",
    and account-resolvable ids (id, descriptor, url, imageUrl) dropped —
    they map to the real MSA/AAD account.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(v, dict) and {"displayName", "uniqueName"} <= v.keys():
                v = {kk: vv for kk, vv in v.items()
                     if kk not in ("id", "descriptor", "url", "imageUrl")}
                v = {**v, "displayName": "Story Author", "uniqueName": "<author>@example.com"}
            else:
                v = anonymize_identities(v)
            out[k] = v
        return out
    if isinstance(obj, list):
        return [anonymize_identities(v) for v in obj]
    return obj


def sanitize_urls(obj, org: str):
    """Replace org name and project GUID inside URL strings.

    Keeps the export shape (fidelity decision applies to trimming, not to
    identifier hygiene): `https://dev.azure.com/<org>/...` ->
    `https://dev.azure.com/$ADO_ORG/...`, and the project GUID segment
    (first path segment after the org in _apis URLs) -> `<project-id>`.
    """
    org_re = re.compile(r"https://dev\.azure\.com/" + re.escape(org) + r"(/[^/]*)?(/_apis/.*)")
    guid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

    def fix(s: str) -> str:
        m = org_re.match(s)
        if m:
            second = "/<project-id>" if (m.group(1) and guid_re.match(m.group(1)[1:])) else (m.group(1) or "")
            return f"https://dev.azure.com/$ADO_ORG{second}{m.group(2)}"
        return s

    if isinstance(obj, dict):
        return {k: sanitize_urls(v, org) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_urls(v, org) for v in obj]
    if isinstance(obj, str):
        return fix(obj)
    return obj


def strip_links(obj):
    """Recursively remove every "_links" key (org URLs, volatile avatars)."""
    if isinstance(obj, dict):
        return {k: strip_links(v) for k, v in obj.items() if k != "_links"}
    if isinstance(obj, list):
        return [strip_links(v) for v in obj]
    return obj


def provenance_map() -> dict[int, tuple[str, str]]:
    """Parse provenance lines -> {ado_id: (template, scenario)}.

    T1-T4/T6 come from canonical-facts.md (renderings of the canonical
    facts); T5 from t5-enabler-spec.md (self-contained enablers, mirrored
    per scenario by design).
    """
    mapping: dict[int, tuple[str, str]] = {}
    sources = [(CANONICAL, r"^- provenance: (.+)$"),
               (T5SPEC, r"^- provenance: (.+)$"),
               (COMMENTSSPEC, r"^- provenance: (.+)$")]
    for path, line_re in sources:
        text = path.read_text()
        for m in re.finditer(r"^## (\S+)\n$(.*?)((?=^## )|\Z)", text, re.M | re.S):
            scenario = m.group(1)
            pm = re.search(line_re, m.group(2), re.M)
            if not pm:
                sys.exit(f"{path.name}: no provenance line under '{scenario}'")
            for tm, ids in re.findall(r"T(\d) ids? ((?:\d+[,\s]+)*\d+)", pm.group(1)):
                for id_str in re.findall(r"\d+", ids):
                    ado_id = int(id_str)
                    if ado_id in mapping:
                        sys.exit(f"duplicate provenance id {ado_id} ({path.name})")
                    mapping[ado_id] = (f"t{tm}", scenario)
    return mapping


def story_id_for(template: str, scenario: str) -> str:
    """Deterministic dataset story id (D9 amendment 2): story-NN.

    Core scenarios are numbered template-major (t1/clean=01 ...
    t6/hidden-conflict=42, stride = len(SLUGS)). T1-only comment
    scenarios (D9 amendment 3) continue after the core grid: 43+ in slug
    order, and must not appear outside t1. Stress duplicates ('<slug>-2')
    get their own file but must not silently collide — they abort until
    explicitly registered here."""
    base = scenario.rsplit("-2", 1)[0] if scenario.endswith("-2") else scenario
    if template not in TEMPLATE_BY_AREA.values():
        sys.exit(f"no story id registered for template {template!r}")
    if base in T1_ONLY_SLUGS:
        if scenario in T1_ONLY_SLUGS and template == "t1":
            return f"story-{FIRST_T1_ONLY_ID + T1_ONLY_SLUGS.index(scenario):02d}"
        sys.exit(f"scenario {scenario!r} is t1-only but exported from {template}")
    if base not in SLUGS:
        sys.exit(f"no story id registered for scenario {scenario!r} (add it to SLUGS first)")
    if base != scenario:
        sys.exit(f"stress duplicate {scenario!r} needs its own story id (extend story_id_for)")
    t_index = int(template[1]) - 1
    return f"story-{t_index * len(SLUGS) + SLUGS.index(scenario) + 1:02d}"


def main() -> None:
    missing = [v for v in ("ADO_ORG", "ADO_PROJECT") if not os.environ.get(v)]
    if missing:
        sys.exit(f"{'/'.join(missing)} not set (set -a; source infra/envs/ado.env; set +a)")
    prov = provenance_map()
    mode = "REST (ADO_PAT)" if use_rest() else "az CLI"
    ids = query_ids(os.environ["ADO_PROJECT"])
    story_ids = [i for i in ids if i not in CONTEXT_IDS]
    context_ids = [i for i in ids if i in CONTEXT_IDS]

    if story_ids != sorted(prov):
        sys.exit(
            f"ADO id set does not match canonical-facts provenance.\n"
            f"  in ADO only: {sorted(set(story_ids) - set(prov))}\n"
            f"  in provenance only: {sorted(set(prov) - set(story_ids))}"
        )
    if len(story_ids) != EXPECTED_STORIES:
        sys.exit(f"expected {EXPECTED_STORIES} stories, query returned {len(story_ids)}")
    if sorted(context_ids) != sorted(CONTEXT_IDS):
        sys.exit(f"expected context ids {sorted(CONTEXT_IDS)}, got {sorted(context_ids)}")

    exported_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    print(f"fetch mode: {mode}")
    for wid in ids:
        item = anonymize_identities(sanitize_urls(strip_links(
            show_item(os.environ["ADO_PROJECT"], wid)),
            os.environ["ADO_ORG"],
        ))
        fields = item["fields"]
        area = fields.get("System.AreaPath", "").split("\\", 1)[1] if "\\" in fields.get("System.AreaPath", "") else None
        template = TEMPLATE_BY_AREA.get(area)
        if template is None:
            sys.exit(f"id {wid}: unknown area path {fields.get('System.AreaPath')!r}")

        if wid in CONTEXT_IDS:
            case = f"context/{fields['System.Title'].lower().replace(' ', '-')}"
            path = STORIES_DIR / "context" / f"{case.split('/', 1)[1]}.json"
            template = "context"
            scenario = None
        else:
            prov_tm, prov_slug = prov[wid]
            if template != prov_tm:
                sys.exit(f"id {wid}: area-path template {template} != provenance template {prov_tm}")
            scenario = prov_slug
            case = f"{template}/{scenario}"
            path = STORIES_DIR / template / f"{scenario}.json"

        envelope = {
            "schema_version": 1,
            "case_id": case,
            "template": template,
            "scenario": scenario,
            "ado_source_id": wid,
            "exported_at": exported_at,
            "work_item": _sorted_keys(item),
        }
        if scenario is not None:
            envelope["story_id"] = story_id_for(template, scenario)
            envelope = {
                k: envelope[k] for k in (
                    "schema_version", "case_id", "story_id", "template",
                    "scenario", "ado_source_id", "exported_at", "work_item",
                )
            }
            comments = fetch_comments(os.environ["ADO_PROJECT"], wid)
            if comments:
                # appended after work_item — keeps the documented key order
                # and leaves comment-less story files byte-stable
                envelope["comments"] = comments
                print(f"  {len(comments)} comment(s) attached")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n")
        print(f"{case:32s} ado id {wid}  -> {path.relative_to(REPO)}")

    print(f"\n{len(story_ids)} stories + {len(context_ids)} context items exported at {exported_at}")


if __name__ == "__main__":
    main()
