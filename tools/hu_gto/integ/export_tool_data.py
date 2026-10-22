"""Eksport wyniku rundy punktu stałego do tool/data: book.npz (+json), leaves_<S>.json,
leaf_model.npz, meta.json.  Użycie: python export_tool_data.py [out/roundN.pkl]"""

import json
import pickle
import sys
from pathlib import Path

import fp
import numpy as np
from fp import H

src = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else max(fp.OUT.glob("round*.pkl"), key=lambda p: int(p.stem[5:]))
)
z = pickle.load(open(src, "rb"))
res, model = z["res"], z["model"]
dst = fp.HU / "tool" / "data"
dst.mkdir(parents=True, exist_ok=True)
H.save_book([res[d] for d in sorted(res)], dst / "book.npz")
for d, r in res.items():
    H.export_leaves(r, dst / f"leaves_{d:g}.json")
arrs = {}
for k, (a_sb, a_bb) in getattr(model, "a", {}).items():
    arrs[f"{k}|sb"], arrs[f"{k}|bb"] = a_sb, a_bb
np.savez(dst / "leaf_model.npz", **arrs)
json.dump(
    dict(
        source=str(src),
        depths=[f"{d:g}" for d in sorted(res)],
        model_info=getattr(model, "info", "ConstEQR"),
        round=z["state"]["rounds"][-1]["r"],
    ),
    open(dst / "meta.json", "w"),
    indent=1,
    default=str,
)
print("eksport", src, "->", dst, "klucze modelu:", sorted(k.rsplit("|", 1)[0] for k in arrs)[:20])
