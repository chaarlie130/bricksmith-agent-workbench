# BrickSmith visual and construction benchmark

This is a local, private comparison baseline, not a training corpus. Do not
add either model to the retrieval index for a blind generation test.

## User-provided modern-house baseline

- Claude model: `/Users/charliecittadini/modern-house-test2.ldr` (766 LDraw
  placements); visual reference:
  `/Users/charliecittadini/modern_hillside_house_test_2.png`.
- Older GPT model: `/Users/charliecittadini/gpt-modern-house-test.ldr` (181
  placements). These are different model sizes and runs, so this is a quality
  bar, **not** a controlled model ranking.
- Claude visual strengths to reproduce in an original build: complete thin
  layered roof planes; continuous but framed upper glazing; balcony with
  railing; visible entrance and stairs; stepped site terrain; coordinated
  trim, furniture, and planting. These features form one architectural
  composition, not isolated decorations.
- A local render of the Claude source using the workbench's transparent-part
  renderer is saved at `runs/claude-modern-baseline-alpha.png` (ignored
  benchmark artifact). Compare multiple camera angles; it need not match
  the framing of the user-supplied image.

Run the structural checks with the correct ground convention:

```bash
python scripts/workbench.py check /Users/charliecittadini/modern-house-test2.ldr --ground-y 0
python scripts/workbench.py check /Users/charliecittadini/gpt-modern-house-test.ldr
```

As checked on 2026-10-02, the Claude file was mesh-collision-free and had one
connected component of 755/766 pieces plus eleven singleton components. It
did **not** pass complete connectivity or equilibrium. Its plate-built base
is at Y=0; checking it with the harness default Y=8 additionally reports no
ground base. The older GPT file had 52 mesh-collision pairs, failed
connectivity, and failed equilibrium. The checker is approximate and can
miss special-part connections; investigate the eleven isolated placements
before treating them as real-world construction defects.
The default-ground report now suggests candidate ground Y=0 for Claude's
plate-built base, rather than making the user infer that convention from
the `no_ground_baseplate` error alone.

## Traditional-house reference-photo baseline

The separate Claude model `/Users/charliecittadini/trad_house.ldr` contains
974 placements. A local front-right render is saved at
`runs/claude-traditional-baseline.png` (ignored benchmark artifact). Its
visual strengths are the gabled main mass joined to a lower wing, porch
columns and railings, repeated glazed windows with shutters/trim, clear
entrance hierarchy, and developed path, planting, and fence. With
`--ground-y 0`, the checker finds no mesh collisions and a 908-piece main
connected component; remaining small components prevent a full pass. This
build used a user-supplied house photo, so it is **not** a fair no-photo
comparison against the modern-house runs.

## Acceptance protocol for new harness runs

1. Keep the generated model out of the retrieval corpus during its test.
   Record the exact brief, model, token usage, reference inputs, and tool
   history; do not compare a photo-guided run to a no-photo run as if equal.
2. Save front-left and another view at comparable framing. Judge silhouette,
   roof closure and thickness, facade/opening rhythm, balcony/porch detail,
   material palette, terrain/landscape, and overall composition against the
   subject brief. A few colored studs or posts do not satisfy a requested
   garden or architectural feature.
3. Separately report the five construction checks, ground Y, part count,
   collision count, and connected-component sizes. A visual win does not
   imply a physics pass; a physics pass does not imply premium design.
4. Reject a submission if a major planned mass, roof, entrance, or signature
   feature is missing, even when every structural check is green. Iterate
   from the render and preserve failed revisions for diagnosis.

The current `gpt-5.6-luna` shed pilot is a useful small construction-tool
test, not evidence of meeting this modern-house quality bar. The first Astra
house attempt spent six requests on references without saving geometry; the
starter-pack attempt saved a plan and rendered a reference before the plan-
token-sharing route hit its separate limit. Neither produced a house to score.
Future modern-house sessions can use `start --ground-y 0` to try a compact
plate-built display plinth rather than automatically placing a small house
on a 32×32 baseplate. Record this ground choice as part of the benchmark;
changing ground Y alone does not make a build stable or visually better.
Check building-to-base proportion in the renders. Claude's modern-house
geometry spans about 39×21 studs and 40 plates of height; the older GPT
house spans about 23×17 studs and 24 plates. These are origin extents, not
full mesh bounds, and are context for the size difference—not an aesthetic
score. A compact building should have intentional margin and site features,
not a largely empty fixed-size lawn.

The `runs/astra-modern-house-prefetch-20261002` experiment is **not** a pure
model result after step 30. It had 270 model-generated pieces and passed the
checker but still appeared as a plain, largely empty-site box. The local Sol
operator then directly added a five-piece balcony railing, 44-piece terraced
forecourt/approach, and five-piece roof lantern without another model API
call. The resulting 324-piece hybrid passes the five approximate construction
checks; its render is `runs/astra-modern-house-prefetch-20261002/renders/local-sol-roof-front-right.png`.
Keep this hybrid labeled separately from both the original Astra snapshot and
the held-out Claude sources. Its simpler massing and sparse facade/landscape
still do not meet the Claude visual benchmark.
