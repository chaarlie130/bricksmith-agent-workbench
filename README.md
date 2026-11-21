# BrickSmith Agent Workbench

BrickSmith is a local Python workbench for designing LEGO models with coding
agents. It searches LDraw references, edits assemblies, checks construction, and
renders revisions for visual review.

[Setup](docs/SETUP.md) · [Command guide](docs/AGENT_WORKBENCH.md) · [Example gallery](examples/README.md)

![Brick model of Fallingwater with cantilevered terraces, a waterfall, and autumn trees](examples/images/fallingwater.png)

*Fallingwater study, 988 pieces. Blender render of a selected workbench build. [LDraw file](examples/fallingwater-gorge.ldr)*

## Try it locally

Follow the [setup guide](docs/SETUP.md) to install Python dependencies and
configure the LDraw and BrickNet libraries. You can search, check, and render
without an API key.

```sh
./.venv/bin/python scripts/workbench.py search "modern house with terrace" --limit 3
./.venv/bin/python scripts/workbench.py check examples/fallingwater-gorge.ldr --ground-y 8
mkdir -p runs
./.venv/bin/python scripts/render.py examples/fallingwater-gorge.ldr --azimuth 325 -o runs/fallingwater.png
```

To design a new model, open this checkout with a coding agent and give it a brief
such as “a small art studio with a shaded desert courtyard.” The
[agent instructions](AGENTS.md) cover staged construction, checking, and visual
review.

## Repository layout

| Directory | Contents |
| --- | --- |
| [`bricksmith/`](bricksmith/) | LDraw I/O, geometry, physics, rendering, and workbench services |
| [`scripts/`](scripts/) | Commands for design, validation, rendering, and parts lists |
| [`examples/`](examples/) | Selected renders and an example LDraw model |
| [`data/`](data/) | Reference corpus and local library setup |
| [`tests/`](tests/) | Unit tests, integration tests, and fixtures |
| [`docs/`](docs/) | Setup, command reference, and development records |
| [`experiments/`](experiments/) | Archived build drafts and one-off scripts |

## Status

BrickSmith is experimental. The checks cover mesh intersections, ground
placement, stud-based connectivity, and approximate static equilibrium.
Assembly order, insertion clearance, and clutch strength require separate
verification. The gallery shows selected runs. The
[benchmark protocol](docs/BENCHMARK_PROTOCOL_DRAFT.md) is still a draft.

BrickSmith uses [BrickNet](https://github.com/kulits/BrickNet) and
[LDraw](https://www.ldraw.org/). Related projects include
[BrickWright](https://github.com/AvaLovelace1/brickwright) and
[BrickAgent](https://github.com/kulits/BrickAgent).

The code is [MIT licensed](LICENSE). See the [data notes](data/README.md) for
third-party reference material. BrickSmith is independent of the LEGO Group.
