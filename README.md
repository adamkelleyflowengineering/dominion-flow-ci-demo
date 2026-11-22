# dominion-flow-ci-demo

Demo repository for the **Dominion Dynamics × Flow Engineering** trial workshop.
It shows software verification evidence flowing automatically from CI into Flow,
traced to requirements in the Flow project
[Dominion Scout Arctic Anti-Icing Demo](https://branch.flowengineering.com/demo/dominion-scout-arctic-anti-icing-demo).

> **Framing:** Dominion doesn't use Linear or (necessarily) GitHub Actions. In this demo
> **Linear stands in for Jira** (test execution tickets) and **GitHub Actions stands in for
> Buildkite / their CI** (automated test execution). The Flow side is identical whichever tools
> feed it: tickets and CI both talk to Flow through its API and automations.

## What's in here

| Path | What it is | Flow requirement |
| -- | -- | -- |
| `dominion_ci/latency_budget.py` | C2 datalink end-to-end latency budget (GCS + ground terminal + RF + air vehicle), flags configs over 250 ms total / 120 ms RF | REQ-44098 (allocates REQ-44077, REQ-44084) |
| `dominion_ci/heater_power.py` | Wing anti-icing heater power command, 2.4–3.0 kW in icing | REQ-44099 |
| `tests/test_latency_budget.py` | Unit tests | TES-44188 |
| `tests/test_latency_sweep.py` | Parametrized sweep of 21 planned link configurations (**one intentionally fails**) | TES-44190 |
| `tests/test_heater_power.py` | Unit tests | TES-44193 |
| `tests/test_heater_sweep.py` | Parametrized 60-case OAT × LWC envelope sweep | TES-44195 |
| coverage / bandit / workflow timing | Gates: ≥ 80 % coverage, 0 high-severity findings, results in Flow ≤ 30 min | TES-44178 / REQ-44094, TES-44181 / REQ-44095, TES-44184 / REQ-44096 |
| `flow_ids.json` | Map of Flow human IDs (TES-/REQ-) to Flow item IDs | |
| `scripts/post_to_flow.py` | Reads JUnit XML + coverage + bandit, groups by Flow test case, posts to Flow | |
| `.github/workflows/flow-ci.yml` | CI: ruff, bandit, pytest → JUnit XML → Flow | |

Every test carries its Flow IDs:

```python
@pytest.mark.flow(test_case="TES-44190", requirements=["REQ-44098", "REQ-44084"])
def test_planned_configuration_within_budget(config, flow_measure): ...
```

`conftest.py` writes those IDs (and any measured value) into the JUnit XML as test properties.

## How results reach Flow (and Linear)

1. The workflow runs on every pull request, every push to `main`, and on demand (*Run workflow*).
2. `scripts/post_to_flow.py` groups the JUnit results by Flow test case, then:
   * **Linear (standing in for Jira):** fires the Flow automation **CI failure → Linear ticket**
     (`source: "ci-linear-sync"`). A failing test case opens, or updates, a ticket in the Flow Demo team
     titled `CI failure: REQ-… <requirement> (TES-…)`, assigned to the owner, with the failing test names,
     the GitHub run link and the Flow link. When that test case passes later, the ticket is renamed
     `✅ Fixed in PR #n – …` and the passing evidence is appended. (With an optional `LINEAR_API_KEY`
     secret, CI also moves it to **Done**, comments, and files new tickets in the
     *Dominion demo – test execution loop* project.)
   * **Pull request →** a Flow branch named **`GitHub PR #<n> – <PR title>`** is created (or reused on
     later pushes). A Test Result per test case (Pass/Fail, measured value, commit, run link, Linear ticket)
     and the requirement Actual Values are written on it, so the branch's **Review** tab shows exactly what
     the PR changed, and requirement Verification flips red/green on that branch.
   * **Push to `main` →** the Flow automation **Ingest CI test results** (`source: "ci-test-results"`)
     records the results on its review branch *Automation: Ingest CI test results*.
3. On pull requests, Flow's verdict is posted back as **one sticky PR comment** ("Flow requirements check",
   by `github-actions[bot]`, updated in place on re-runs): overall verdict, a table of the affected requirements
   with the status Flow computed on the PR branch, measured vs limit and number of tests, plus links to the Flow
   branch and any Linear ticket. If Flow could not be reached, the comment says so instead of claiming a pass.
4. The job summary on GitHub lists the Flow branch, every test case result and the Linear tickets.

The intentionally failing case on `main` — *Inuvik relay corridor 300 km / interleaver 8* (≈ 147 ms RF,
≈ 261 ms end to end) — makes TES-44190 **Fail**, pushes REQ-44098's actual value over its 250 ms limit and
opens a Linear ticket. The branch `demo/inuvik-interleaver-fix` changes that one line to interleaver 4:
open a PR from it and Flow creates a `GitHub PR #n` branch where REQ-44098 turns **Pass** and the ticket is
marked fixed.

## Setup

Repository secrets (Settings → Secrets and variables → Actions):

| Secret | Value |
| -- | -- |
| `FLOW_API_KEY` | Flow API key with access to the demo project |
| `FLOW_CUSTOMER` | `demo` |
| `LINEAR_API_KEY` (optional) | Linear personal API key: lets CI move fixed tickets to Done, comment, and set the project |

Run locally:

```bash
pip install -e ".[dev]"
mkdir -p reports
bandit -r dominion_ci -f json -o reports/bandit.json
pytest --junitxml=reports/junit.xml -o junit_family=xunit1 --cov=dominion_ci --cov-report=xml:reports/coverage.xml
python scripts/post_to_flow.py --dry-run         # print the payload
FLOW_API_KEY=... FLOW_CUSTOMER=demo python scripts/post_to_flow.py   # post it
```

Note: the Flow project's Base branch is protected, so automation writes land on the review branch
*"Automation: Ingest CI test results"* until it is reviewed and merged in Flow.

## Related: the manual test loop (Linear standing in for Jira)

Hardware / HIL tests use the other two Flow automations from the same project:
**Run test in Linear** (right-click a test case → ticket with steps + empty Results section, plus a
linked Inconclusive Test Result in Flow) and **Populate test results from Linear** (daily 4 AM PT agent
that reads Done tickets and sets Pass/Fail + measured values). Example tickets live in the Linear
project *Dominion demo – test execution loop* (team Flow Demo, FLO-5 … FLO-12).

## Resetting the demo (practice runs)

Actions tab → **Demo reset** → **Run workflow** (about 2–3 minutes). It closes open pull requests without merging,
rebuilds `demo/inuvik-interleaver-fix` as a one-line fix on main, has Flow cancel old `CI failure: REQ-…` Linear
tickets, and re-runs main CI so REQ-44098 is red again in Flow with one fresh open Linear ticket. The job summary
lists the new ticket and the next PR number.
