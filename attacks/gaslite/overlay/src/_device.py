"""Central device selection so GASLITE runs without CUDA (Mac CPU/MPS).

The upstream repo hardcodes `.cuda()` / `device='cuda'` everywhere. We replace
those with `DEVICE`, resolved here once:

  - env GASLITE_DEVICE wins (e.g. GASLITE_DEVICE=cpu or =mps or =cuda)
  - else CUDA if available
  - else MPS (Apple Silicon) if available
  - else CPU

Note: MPS may not support every op GASLITE uses (int scatter, some gradient
ops). If you hit an MPS "not implemented" error, run with GASLITE_DEVICE=cpu
(slower but reliable).
"""
import os
import torch

_env = os.environ.get("GASLITE_DEVICE", "").strip().lower()
if _env:
    _dev = _env
elif torch.cuda.is_available():
    _dev = "cuda"
elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
    _dev = "mps"
else:
    _dev = "cpu"

DEVICE = torch.device(_dev)
print(f"[GASLITE] Using device: {DEVICE}")
