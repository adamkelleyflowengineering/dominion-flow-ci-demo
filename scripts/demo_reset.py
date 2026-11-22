"""Demo reset helpers, used by .github/workflows/demo-reset.yml.

  python scripts/demo_reset.py cancel-tickets   # Flow cancels open 'CI failure: REQ-…' Linear tickets
  python scripts/demo_reset.py verify            # read REQ-44098 back from Flow on the starting branch
  python scripts/demo_reset.py purge             # optional: with LINEAR_API_KEY, delete (trash) old tickets

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
    result: dict = {}
    for line in out.splitlines():
        if line.startswith("RESULT="):
            result = ast.literal_eval(line[len("RESULT="):])
    canceled, unlinked = result.get("canceled", []), result.get("removed_from_project", [])
    summary(f"- Linear: canceled {len(canceled)} old CI failure ticket(s) ({', '.join(canceled) or 'none open'}); "
            f"removed {len(unlinked)} from the demo project ({', '.join(unlinked) or 'none'})")
    return 0


def purge() -> int:
    """Delete old 'CI failure: REQ-' tickets (FLO-13+) except the newest open one. Needs LINEAR_API_KEY.

    Linear's issueDelete moves a ticket to the trash, where it can be restored for 30 days.
    """
    key = os.environ.get("LINEAR_API_KEY")
    if not key:
        summary("- Old tickets are canceled and out of the demo project. Add a LINEAR_API_KEY repo secret to delete them.")
        return 0
    import json
    import urllib.request

    def gql(query: str, variables: dict) -> dict:
        req = urllib.request.Request("https://api.linear.app/graphql", method="POST",
                                     data=json.dumps({"query": query, "variables": variables}).encode(),
                                     headers={"Authorization": key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310 - fixed https endpoint
            return json.loads(resp.read())

    nodes = gql("""query { issues(first: 100, filter: { team: { key: { eq: "FLO" } }, number: { gt: 12 },
                  title: { contains: "CI failure: REQ-" } }) { nodes { id identifier number state { type } } } }""",
                {}).get("data", {}).get("issues", {}).get("nodes", [])
    open_ = [n for n in nodes if n["state"]["type"] not in ("canceled", "completed")]
    keep = max(open_, key=lambda n: n["number"])["identifier"] if open_ else None
    deleted = []
    mutation = "mutation($id: String!) { issueDelete(id: $id) { success } }"
    for n in nodes:
        if n["identifier"] == keep or n["number"] <= 12:
            continue
        if gql(mutation, {"id": n["id"]}).get("data", {}).get("issueDelete", {}).get("success"):
            deleted.append(n["identifier"])
    summary(f"- Linear: kept {keep}; moved {len(deleted)} old ticket(s) to the trash (restorable 30 days): "
            f"{', '.join(deleted) or 'none'}")
    return 0


def verify() -> int:
    branch = p.branch_id_by_name(p.MAIN_REVIEW_BRANCH)
    ref = "REQ-44098"
    v = p.get_entity(p.IDS["requirements"][ref]["id"], branch)["values"]
    status, actual, upper = v.get("verification"), p.num(v.get(p.ACTUAL)), p.num(v.get(p.UPPER))
    summary(f"- Flow starting branch **{p.MAIN_REVIEW_BRANCH}** ({p.APP_URL}/{branch}/table): "
            f"{ref} {v.get('name')} is **{status}**, {actual} ms vs ≤ {upper} ms")
    return 0 if status == "Fail" else 1


if __name__ == "__main__":
    sys.exit({"cancel-tickets": cancel_tickets, "verify": verify, "purge": purge}[sys.argv[1]]())
