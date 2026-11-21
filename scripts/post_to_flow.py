#!/usr/bin/env python3
"""Post CI results to Flow (webhook source "ci-test-results").

Reads JUnit XML (pytest --junitxml), coverage.xml and bandit JSON, groups test
outcomes by the Flow test case tagged on each test, and sends one webhook to
Flow's automation trigger endpoint. The Flow automation "Ingest CI test
results" then creates a Pass/Fail Test Result under each test case and writes
requirement actual values (coverage %, high-severity findings).

Env: FLOW_API_KEY (secret), FLOW_CUSTOMER (e.g. "demo"), optional FLOW_API_BASE,
GITHUB_* variables provided by GitHub Actions.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IDS = json.loads((ROOT / "flow_ids.json").read_text())

COVERAGE_TC, COVERAGE_REQ, COVERAGE_MIN = "TES-44178", "REQ-44094", 80.0
STATIC_TC, STATIC_REQ = "TES-44181", "REQ-44095"
PUBLISH_TC, PUBLISH_REQ = "TES-44184", "REQ-44096"
SWEEP_TC, LATMODEL_REQ = "TES-44190", "REQ-44098"


def parse_junit(path: Path) -> dict:
    groups: dict = defaultdict(lambda: {"passed": 0, "failed": 0, "failures": [], "measured": []})
    for case in ET.parse(path).getroot().iter("testcase"):
        props = {p.get("name"): p.get("value") for p in case.iter("property")}
        tc = props.get("flow_test_case")
        if not tc:
            continue
        g = groups[tc]
        failed = case.find("failure") is not None or case.find("error") is not None
        if case.find("skipped") is not None:
            continue
        if failed:
            g["failed"] += 1
            g["failures"].append(case.get("name"))
        else:
            g["passed"] += 1
        if props.get("flow_measured") not in (None, ""):
            g["measured"].append(float(props["flow_measured"]))
    return groups


def tc_entry(ref: str, outcome: str, measured=None, passed=0, failed=0, failures=None) -> dict:
    return {"id": IDS["test_cases"][ref]["id"], "ref": ref, "outcome": outcome,
            "measured": measured, "passed": passed, "failed": failed, "failures": failures or []}


def req_entry(ref: str, value) -> dict:
    return {"id": IDS["requirements"][ref]["id"], "ref": ref, "value": value}


def build_payload(junit: Path, coverage: Path | None, bandit: Path | None, started: str | None) -> dict:
    test_cases, req_values = [], []
    for ref, g in sorted(parse_junit(junit).items()):
        if ref not in IDS["test_cases"]:
            continue
        measured = max(g["measured"]) if g["measured"] else None
        test_cases.append(tc_entry(ref, "fail" if g["failed"] else "pass", measured,
                                   g["passed"], g["failed"], g["failures"]))
        if ref == SWEEP_TC and measured is not None:
            req_values.append(req_entry(LATMODEL_REQ, measured))  # worst planned-config budget, ms
    if coverage and coverage.exists():
        pct = round(float(ET.parse(coverage).getroot().get("line-rate")) * 100, 1)
        test_cases.append(tc_entry(COVERAGE_TC, "pass" if pct >= COVERAGE_MIN else "fail", pct))
        req_values.append(req_entry(COVERAGE_REQ, pct))
    if bandit and bandit.exists():
        results = json.loads(bandit.read_text()).get("results", [])
        high = sum(1 for r in results if r.get("issue_severity") == "HIGH")
        test_cases.append(tc_entry(STATIC_TC, "pass" if high == 0 else "fail", high))
        req_values.append(req_entry(STATIC_REQ, high))
    if started:
        minutes = round((dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds() / 60, 1)
        test_cases.append(tc_entry(PUBLISH_TC, "pass" if minutes <= 30 else "fail", minutes))
        req_values.append(req_entry(PUBLISH_REQ, minutes))
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY", "adamkelleyflowengineering/dominion-flow-ci-demo")
    run_id = os.environ.get("GITHUB_RUN_ID")
    return {
        "commit": os.environ.get("GITHUB_SHA", "local"),
        "branch": os.environ.get("GITHUB_REF_NAME", "local"),
        "run_number": os.environ.get("GITHUB_RUN_NUMBER", "local"),
        "run_url": f"{server}/{repo}/actions/runs/{run_id}" if run_id else "local run",
        "date": dt.date.today().isoformat(),
        "test_cases": test_cases,
        "requirement_values": req_values,
    }


def post(payload: dict) -> dict:
    base = os.environ.get("FLOW_API_BASE", "https://backend.branch.flowengineering.com")
    body = json.dumps({"project_id": IDS["project_id"], "source": "ci-test-results",
                       "context": payload, "wait": True}).encode()
    request = urllib.request.Request(base + "/ai/trigger", data=body, method="POST", headers={
        "X-API-Key": os.environ["FLOW_API_KEY"],
        "customer": os.environ.get("FLOW_CUSTOMER", "demo"),
        "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as resp:  # nosec B310 - fixed https endpoint
        return json.loads(resp.read() or b"{}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--junit", default="reports/junit.xml", type=Path)
    ap.add_argument("--coverage", default="reports/coverage.xml", type=Path)
    ap.add_argument("--bandit", default="reports/bandit.json", type=Path)
    ap.add_argument("--started", default=os.environ.get("WORKFLOW_STARTED_AT"))
    ap.add_argument("--dry-run", action="store_true", help="print the payload, do not post")
    args = ap.parse_args()
    payload = build_payload(args.junit, args.coverage, args.bandit, args.started)
    print(json.dumps(payload, indent=2))
    if args.dry_run:
        return 0
    result = post(payload)
    print(json.dumps(result, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
