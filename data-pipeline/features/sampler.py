"""Ambil vektor fitur di titik (lat, lng) dari raster fitur 25 m (build_features.py)."""
import math, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
_Z = np.load(os.path.join(ROOT, 'data-pipeline/.cache/features.npz'))
W, N, DX, DY, NX, NY = _Z['_meta']; NX = int(NX); NY = int(NY)
LAYERS = {k: _Z[k] for k in _Z.files if not k.startswith('_')}
# transformasi: jarak → log(1 + d/100 m); hitungan → log(1 + n)
DIST = [k for k in LAYERS if k.startswith('d_')]
COUNT = ['poi_comm_1000', 'poi_comm_3000', 'school_1000', 'health_1500', 'bld_250']
NAMES = sorted(LAYERS)
def tf(name, v):
    if name in DIST: return np.log1p(np.asarray(v) / 100.0)
    if name in COUNT: return np.log1p(np.maximum(np.asarray(v), 0))
    return np.asarray(v)
def idx(lat, lng):
    i = np.clip(((N - np.asarray(lat)) / DY).astype(int), 0, NY - 1); j = np.clip(((np.asarray(lng) - W) / DX).astype(int), 0, NX - 1); return i, j
def sample(lat, lng, names=None):
    names = names or NAMES; i, j = idx(lat, lng)
    return np.column_stack([tf(n, LAYERS[n][i, j]) for n in names])
def raw(lat, lng, name):
    i, j = idx(lat, lng); return LAYERS[name][i, j]
