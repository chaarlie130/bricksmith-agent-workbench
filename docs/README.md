# Documentation

- [Local setup](SETUP.md) covers Python, LDraw, BrickNet, and preflight.
- [Command guide](AGENT_WORKBENCH.md) covers reference search, design documents,
  revision transactions, construction checks, and the model session.
- [Agent instructions](../AGENTS.md) describe the direct build workflow.

For contributors, the [design contracts](HARNESS_CONTRACTS.md) describe the
data and tool interfaces. The [implementation plan](HARNESS_IMPLEMENTATION_PLAN.md)
and [implementation records](implementation/) preserve the history of the
workbench. The [benchmark draft](BENCHMARK_PROTOCOL_DRAFT.md) and
[evaluation notes](QUALITY_BENCHMARK.md) describe proposed comparisons.

Run the test suite from the repository root after setup:

```sh
./.venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py'
BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```
