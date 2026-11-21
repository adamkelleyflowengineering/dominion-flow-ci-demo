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

## How results reach Flow

1. The workflow runs on every push / PR to `main` (or manually via *Run workflow*).
2. `scripts/post_to_flow.py` sends one webhook: `POST https://backend.branch.flowengineering.com/ai/trigger`
   with `source: "ci-test-results"` and the grouped results as `context`.
3. The Flow automation **Ingest CI test results** (project Settings → Automations) creates a
   **Test Result** (Pass/Fail, measured value, commit SHA, run link, failing test names) under each
   test case and writes requirement **Actual Values** (coverage %, high-severity findings, worst-case
   latency budget). Requirement verification status then rolls up in Flow automatically.

The intentionally failing case — *Inuvik relay corridor 300 km / interleaver 8* (≈ 147 ms RF, ≈ 261 ms
end to end) — makes TES-44190 **Fail** and pushes REQ-44098's actual value over its 250 ms limit,
so the workshop can show a requirement being flagged by a code change. Change the interleaver to 4
in `tests/test_latency_sweep.py`, push, and watch it go green in Flow.

## Setup

Repository secrets (Settings → Secrets and variables → Actions):

| Secret | Value |
| -- | -- |
| `FLOW_API_KEY` | Flow API key with access to the demo project |
| `FLOW_CUSTOMER` | `demo` |

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
