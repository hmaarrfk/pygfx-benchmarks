# Render-loop optimizations: per-commit progression

Benchmark: [`benchmarks/bm_render_loop.py`](../../benchmarks/bm_render_loop.py) —
per-frame `FlatScene(scene, view_matrix) + sort()` for a large scene, with a
**moving camera** (the realistic case: the view matrix changes every frame) and
**without a camera** (`sort_objects=False`). This is the CPU work the renderer
does each frame before issuing GPU draws.

**Scene:** 3000 groups × 10 points = 30 000 renderables (~33 000 objects incl.
groups + lights). Figure = median of 30 frames, GC disabled, after warm-up.
Lower is better. `step` = speedup vs the previous commit; `cumulative` = vs `main`.

Each row is a commit on [pygfx#1298 / PR #13](https://github.com/hmaarrfk/pygfx/pull/13):

0. `main` — baseline (per-render scene-graph walk; per-object distance + Python sort)
1. **scene-index** — maintain a categorized index incrementally; render reads flat lists
2. **vectorize** — batched `vec_transform` + `np.lexsort` instead of per-object
3. **cache** — cache the camera-independent renderable structure across frames
4. **skip-id** — assign ids / `_update_object` only for new/moved objects, in one sweep

Raw output: [`render_loop_percommit_apple-m5-max.txt`](render_loop_percommit_apple-m5-max.txt),
[`render_loop_percommit_nano.txt`](render_loop_percommit_nano.txt),
[`render_loop_percommit_core-ultra-7-270k.txt`](render_loop_percommit_core-ultra-7-270k.txt).

> **Refresh, 2026-11-23:** PR #13 was rebased onto pygfx main `27a0692`
> and re-measured on a third machine (Intel Core Ultra 7 270K, see the
> section below). The M5 Max and i7-1180G7 tables were measured
> before the rebase, against the older main, and have not been re-run.
> After the rebase, *skip-id* is part of commit 3 (*cache*), and a new
> commit 4 (*render-pass state*) speeds up drawing. The new section also
> times a full `renderer.render()`.

## Apple M5 Max — macOS 26.4

**Moving camera**

| commit | µs | step | cumulative |
|---|---:|---:|---:|
| 0 main | 74,424 | — | 1.00× |
| 1 scene-index | 67,966 | 1.10× | 1.10× |
| 2 vectorize | 35,621 | 1.91× | 2.09× |
| 3 cache | 6,880 | 5.18× | 10.82× |
| 4 skip-id | 4,740 | 1.45× | **15.70×** |

**No camera** (`sort_objects=False`)

| commit | µs | step | cumulative |
|---|---:|---:|---:|
| 0 main | 35,543 | — | 1.00× |
| 1 scene-index | 25,380 | 1.40× | 1.40× |
| 2 vectorize | 26,895 | 0.94× | 1.32× |
| 3 cache | 4,055 | 6.63× | 8.77× |
| 4 skip-id | 4,307 | 0.94× | 8.25× |

## Intel i7-1180G7 @ 1.30GHz — Ubuntu 26.04 (low-power)

**Moving camera**

| commit | µs | step | cumulative |
|---|---:|---:|---:|
| 0 main | 439,336 | — | 1.00× |
| 1 scene-index | 388,941 | 1.13× | 1.13× |
| 2 vectorize | 210,739 | 1.85× | 2.08× |
| 3 cache | 52,549 | 4.01× | 8.36× |
| 4 skip-id | 31,240 | 1.68× | **14.06×** |

**No camera** (`sort_objects=False`)

| commit | µs | step | cumulative |
|---|---:|---:|---:|
| 0 main | 179,203 | — | 1.00× |
| 1 scene-index | 150,986 | 1.19× | 1.19× |
| 2 vectorize | 163,416 | 0.92× | 1.10× |
| 3 cache | 28,998 | 5.64× | 6.18× |
| 4 skip-id | 29,749 | 0.97× | 6.02× |

## Intel Core Ultra 7 270K Plus — Ubuntu (Linux 7.0), PR rebased onto main `27a0692`

Python 3.14.7, numpy 2.5.5, wgpu via Dawn, cpufreq governor `powersave`.
These are medians of three rounds (raw numbers in the `.txt`). The PR now
has five commits. The first, a stencil bug fix, has no performance effect
and is not listed below; with it, the times are within noise of main
(moving camera 80.3 ms, full frame 166.7 ms). *skip-id* is part of commit 3.
Commit 4 (*render-pass state*) only speeds up drawing, so it shows up in
the full frame only.

**Moving camera** (`FlatScene` + `sort`)

| commit | µs | step | cumulative |
|---|---:|---:|---:|
| 0 main (`27a0692`) | 81,336 | — | 1.00× |
| 1 scene-index | 75,677 | 1.07× | 1.07× |
| 2 vectorize | 40,035 | 1.89× | 2.03× |
| 3 cache + skip-id | 7,120 | 5.62× | 11.42× |
| 4 render-pass state | 7,053 | 1.01× | **11.53×** |

**No camera** (`sort_objects=False`)

| commit | µs | step | cumulative |
|---|---:|---:|---:|
| 0 main (`27a0692`) | 35,780 | — | 1.00× |
| 1 scene-index | 28,340 | 1.26× | 1.26× |
| 2 vectorize | 25,506 | 1.11× | 1.40× |
| 3 cache + skip-id | 5,298 | 4.81× | 6.75× |
| 4 render-pass state | 6,119 | 0.87× | **5.85×** |

**Full frame** (`renderer.render()` to a 320×240 offscreen texture, moving camera)

| commit | µs | step | cumulative |
|---|---:|---:|---:|
| 0 main (`27a0692`) | 163,975 | — | 1.00× |
| 1 scene-index | 161,280 | 1.02× | 1.02× |
| 2 vectorize | 125,251 | 1.29× | 1.31× |
| 3 cache + skip-id | 87,788 | 1.43× | 1.87× |
| 4 render-pass state | 73,472 | 1.19× | **2.23×** |

* The FlatScene work goes from 81 ms to 7 ms (about 11.5×), the same
  pattern as on the other machines.
* In a full frame, the FlatScene saving is only part of the story: drawing
  30k objects and submitting them to the GPU remain. Commit 4 removes the
  redundant wgpu calls (pipeline, renderstate bind group, stencil
  reference) and the per-object pipeline lookup, which takes the frame from
  88 ms to 73 ms. In total, a frame goes from **164 ms to 73 ms (2.2×)**.
* Without a camera, commit 4 measured slightly slower (5.3 → 6.1 ms). That
  is noise: commit 4 does not touch this code path, and the three runs
  ranged from 5.4 to 8.6 ms.
* What is left in the full frame is about 1 µs per object for drawing (one
  bind group and one draw call through the wgpu wrapper) and about 0.5 µs
  per object to check its pipeline for changes. Removing that would need
  render bundles or instancing.

## What each commit buys (consistent across machines)

* **scene-index** — modest here (1.1–1.4×): this is a *flat, depth-2* grouped
  scene, so there is little tree to walk. Its large wins are deep hierarchies
  (up to ~7× in the FlatScene micro-benchmark), not this shape.
* **vectorize** — ~1.9× with a moving camera (replaces 30k per-object
  `vec_transform` with one matmul + `lexsort`). No effect without a camera
  (~0.93× = noise) — correct, since there is no distance to compute.
* **cache** — the single biggest lever, **~4–6.6×**, and it helps both paths:
  it eliminates the per-frame gather of materials, positions and wrapper
  allocation.
* **skip-id** — ~1.45–1.68× **only with a moving camera**; flat without one.
  It merges the all-objects id/transform loop *and* the renderable-position
  refresh into one sweep — the moving path had two O(N) scans to collapse, the
  no-camera path only had one.

**Bottom line:** `main` → tip is **~15.7× on the M5** and **~14× on nano** for a
moving camera (~8× / ~6× without one). The win is slightly larger *relative* on
the M5, but the *absolute* saving is far bigger on the low-power CPU:
439 ms → 31 ms per frame — roughly a 2 fps → 32 fps swing in the CPU portion of
the frame for a 33k-object scene.
