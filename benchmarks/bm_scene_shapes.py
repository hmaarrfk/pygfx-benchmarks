"""Full-frame cost of different scene shapes: many separate objects vs one batched object.

Shows how per-object CPU cost scales (100 to 30,000 separate one-point objects),
and that batching the same points into one object avoids it entirely.

Usage: python bm_scene_shapes.py <pygfx checkout> [rounds] [case,case,...]
"""
import gc, statistics, sys, time
sys.path.insert(0, sys.argv[1])
import numpy as np
import pygfx as gfx

ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
rng = np.random.default_rng(0)

def separate(n, per_group=10):
    """n separate one-point Points objects, in groups of 10 (like bm_render_loop)."""
    scene = gfx.Scene()
    scene.add(gfx.AmbientLight(), gfx.DirectionalLight())
    pos = rng.uniform(-100, 100, (n, 3)).astype(np.float32)
    for g_i in range(0, n, per_group):
        g = gfx.Group(); g.render_order = g_i // per_group; scene.add(g)
        for p in pos[g_i:g_i + per_group]:
            ob = gfx.Points(gfx.Geometry(positions=p[None]), gfx.PointsMaterial(size=4, color="#fff"))
            g.add(ob)
    return scene

def batched(n):
    """The same n points as ONE Points object (one geometry, one draw call)."""
    scene = gfx.Scene()
    scene.add(gfx.AmbientLight(), gfx.DirectionalLight())
    pos = rng.uniform(-100, 100, (n, 3)).astype(np.float32)
    scene.add(gfx.Points(gfx.Geometry(positions=pos), gfx.PointsMaterial(size=4, color="#fff")))
    return scene

def time_frames(scene, n=15, warm=5):
    tex = gfx.Texture(dim=2, size=(320, 240, 1), format="rgba8unorm-srgb")
    r = gfx.WgpuRenderer(tex)
    cam = gfx.PerspectiveCamera(70, 1); cam.local.position = (0, 0, 500); cam.show_pos((0, 0, 0))
    f = [0]
    def frame():
        f[0] += 1; cam.local.x = f[0] * 0.5; r.render(scene, cam)
    for _ in range(warm): frame()
    gc.disable(); ts = []
    try:
        for _ in range(n):
            t = time.perf_counter(); frame(); ts.append(time.perf_counter() - t)
    finally:
        gc.enable()
    return statistics.median(ts) * 1e3

cases = [("separate 100", lambda: separate(100)),
         ("separate 1000", lambda: separate(1000)),
         ("separate 3000", lambda: separate(3000)),
         ("separate 30000", lambda: separate(30000)),
         ("batched 30000", lambda: batched(30000))]
only = sys.argv[3].split(",") if len(sys.argv) > 3 else None
for name, make in cases:
    if only and name not in only:
        continue
    scene = make()
    vals = [time_frames(scene) for _ in range(ROUNDS)]
    print(f"{name:16s} full-frame ms: median {statistics.median(vals):8.2f}  runs {' '.join(f'{v:.2f}' for v in vals)}", flush=True)
