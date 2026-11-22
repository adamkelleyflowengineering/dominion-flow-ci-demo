"""Demo reset helpers, used by .github/workflows/demo-reset.yml.

  python scripts/demo_reset.py cancel-tickets   # Flow cancels open 'CI failure: REQ-…' Linear tickets
  python scripts/demo_reset.py verify            # read REQ-44098 back from Flow on the starting branch

Needs FLOW_API_KEY / FLOW_CUSTOMER. Never prints secrets.
"""
from __future__ import annotations

import ast
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import post_to_flow as p


def summary(text: str) -> None:
    print(text)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


def cancel_tickets() -> int:
    res = p.trigger("ci-linear-sync", {"reset": True})
    out = (res[0].get("integration_response") or "") if res else ""
    canceled = []
    for line in out.splitlines():
        if line.startswith("RESULT="):
            canceled = ast.literal_eval(line[len("RESULT="):]).get("canceled", [])
    summary(f"- Linear: canceled {len(canceled)} old CI failure ticket(s): {', '.join(canceled) or 'none open'}")
    return 0


def verify() -> int:
    branch = p.branch_id_by_name(p.MAIN_REVIEW_BRANCH)
    ref = "REQ-44098"
    v = p.get_entity(p.IDS["requirements"][ref]["id"], branch)["values"]
    status, actual, upper = v.get("verification"), p.num(v.get(p.ACTUAL)), p.num(v.get(p.UPPER))
    summary(f"- Flow ({p.MAIN_REVIEW_BRANCH}): {ref} {v.get('name')} is **{status}**, {actual} ms vs ≤ {upper} ms")
    return 0 if status == "Fail" else 1


if __name__ == "__main__":
    sys.exit({"cancel-tickets": cancel_tickets, "verify": verify}[sys.argv[1]]())
