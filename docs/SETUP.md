# Local setup

BrickSmith runs from the repository root. The dependency pins were recorded on
macOS arm64 with CPython 3.14.7. Other platforms and Python versions may require
different versions of the native wheels.

## Install Python dependencies

```sh
git clone https://github.com/chaarlie130/bricksmith-agent-workbench.git
cd bricksmith-agent-workbench
python3.14 -m venv .venv
./.venv/bin/python -m pip install -r requirements-lock.txt \
  'git+https://github.com/kulits/BrickNet.git@b09a689c4929bd27f59c9bb9446237967aa332c9'
```

`requirements-lock.txt` records the tested dependencies. The pinned BrickNet
checkout provides the part catalog and connector data. Collision checking also
requires its separate mesh bundle.

## Configure the part libraries

1. Download the [LDraw parts library](https://library.ldraw.org/updates)
   and extract it. Make sure you point to the directory that contains `parts/`,
   `p/`, and `LDConfig.ldr`.
2. From the repository root, create the local LDraw link. Replace the sample path
   with your actual path.

   ```sh
   ln -s "/absolute/path/to/ldraw" data/ldraw
   ```

3. Fetch the BrickNet meshes into the local data directory. The extracted
   bundle takes about 1.6 GB. If you already have the compatible mesh snapshot,
   you can link `data/bricknet-data` to it instead.

   ```sh
   mkdir -p data/bricknet-data
   BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m bricknet fetch-meshes
   ```

   BrickSmith's checker uses the `inset/` mesh directory, including
   `inset/3024.ply` for the preflight example.

## Verify the installation

```sh
BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python scripts/workbench.py preflight
```

The preflight loads the part libraries, runs five checks on a small fixture,
and renders a PNG. Read the report before running a build. After it passes,
try the [example commands](../README.md#try-it-locally).

The search, check, export, and render commands run locally. For the optional
model session and its authentication setup, see the
[command guide](AGENT_WORKBENCH.md#chatgpt-plan-usage).
