"""Генератор самодостаточного Kaggle-ноутбука для обучения перевода IR -> Lean.

Создаёт notebooks/kaggle_train.ipynb, в котором ВЕСЬ код инлайн — ничего не
импортируется из этого репозитория. Единственный внешний вход — dataset.json
(добавляется на Kaggle как Dataset через "Add Input").

Запуск:  poetry run python ml/make_kaggle_notebook.py
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "notebooks" / "kaggle_train.ipynb"


def md(src: str) -> dict:
    return {"cell_type": "markdown", "id": uuid.uuid4().hex[:8],
            "metadata": {}, "source": src.strip("\n").splitlines(keepends=True)}


def code(src: str) -> dict:
    return {"cell_type": "code", "id": uuid.uuid4().hex[:8], "metadata": {},
            "execution_count": None, "outputs": [],
            "source": src.strip("\n").splitlines(keepends=True)}


CELLS = [
    md(r"""
# IR → Lean: дообучение перевода (self-contained, для Kaggle)

Самодостаточный ноутбук: **ничего не импортируется из проекта**, нужен только `dataset.json`
(пары `Haskell-IR → Lean-код`).

**Как запустить на Kaggle:**
1. Загрузи `ml/dataset.json` как Kaggle Dataset, затем в ноутбуке **Add Input** → выбери его.
2. Settings → **Internet: On** (чтобы скачать веса `t5-small`), при наличии — включи **GPU**.
3. **Run All**.

Ноутбук сам найдёт `dataset.json` в `/kaggle/input/...`. Модель учится переводить общий IR
в код Lean; held-out split показывает генерализацию.
"""),

    code(r"""
# --- конфиг и зависимости (только стандартные + torch/transformers, есть на Kaggle) ---
import json, os, glob, difflib, random
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

MODEL    = "t5-small"                 # можно codet5-small при совместимой версии transformers
PREFIX   = "translate IR to Lean: "
VAL_FRAC = 0.2                        # доля held-out
EPOCHS   = 200
LR       = 5e-4
SEED     = 0
torch.manual_seed(SEED); random.seed(SEED)

device = "cuda" if torch.cuda.is_available() else "cpu"
print("device:", device)
"""),

    code(r"""
# --- найти dataset.json (Kaggle input или рядом с ноутбуком) ---
cands = sorted(glob.glob("/kaggle/input/**/dataset.json", recursive=True)) + ["dataset.json", "ml/dataset.json"]
DATA = next((p for p in cands if os.path.exists(p)), None)
assert DATA, "dataset.json не найден. На Kaggle: Add Input -> твой датасет с dataset.json"
rows = json.loads(open(DATA).read())
print(f"dataset: {DATA}   ({len(rows)} пар)")
print("пример:", rows[0]["name"])
"""),

    code(r"""
# --- train/val split (детерминированный) ---
g = torch.Generator().manual_seed(SEED)
perm = torch.randperm(len(rows), generator=g).tolist()
n_val = max(1, int(len(rows) * VAL_FRAC))
val_idx = set(perm[:n_val])
train_rows = [r for i, r in enumerate(rows) if i not in val_idx]
val_rows   = [r for i, r in enumerate(rows) if i in val_idx]
print(f"train={len(train_rows)}  val={len(val_rows)}")
"""),

    code(r"""
# --- токенизация ---
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL).to(device)

enc = tok([PREFIX + r["haskell_ir"] for r in train_rows],
          padding=True, truncation=True, max_length=512, return_tensors="pt")
labels = tok(text_target=[r["lean_src"] for r in train_rows],
             padding=True, truncation=True, max_length=256, return_tensors="pt").input_ids
labels[labels == tok.pad_token_id] = -100        # игнор pad в loss
enc = {k: v.to(device) for k, v in enc.items()}
labels = labels.to(device)
"""),

    code(r"""
# --- обучение (full-batch, данных мало) ---
opt = torch.optim.AdamW(model.parameters(), lr=LR)
model.train()
for epoch in range(1, EPOCHS + 1):
    opt.zero_grad()
    loss = model(**enc, labels=labels).loss
    loss.backward()
    opt.step()
    if epoch % 20 == 0 or epoch == 1:
        print(f"epoch {epoch:4d}   loss {loss.item():.4f}")
"""),

    code(r"""
# --- оценка: exact match + мягкая близость ---
def evaluate(rows):
    model.eval()
    exact, sim_sum, shown = 0, 0.0, []
    for r in rows:
        ids = tok(PREFIX + r["haskell_ir"], return_tensors="pt",
                  truncation=True, max_length=512).input_ids.to(device)
        with torch.no_grad():
            gen = model.generate(ids, max_length=200, num_beams=4)
        pred = tok.decode(gen[0], skip_special_tokens=True).strip()
        gold = r["lean_src"].strip()
        ok = pred == gold
        exact += ok
        sim_sum += difflib.SequenceMatcher(None, pred, gold).ratio()
        shown.append((r["name"], ok, gold, pred))
    return exact, sim_sum / max(1, len(rows)), shown

tr_e, tr_s, _ = evaluate(train_rows)
val_e, val_s, shown = evaluate(val_rows)

print("\n=== Held-out (модель эти функции НЕ видела при обучении) ===")
for name, ok, gold, pred in shown:
    print(f"\n[{name}]  {'OK' if ok else 'x'}")
    print("  gold:", gold)
    print("  pred:", pred)

print(f"\ntrain:  exact {tr_e}/{len(train_rows)}   близость {tr_s:.1%}")
print(f"val:    exact {val_e}/{len(val_rows)}   близость {val_s:.1%}")
"""),
]


def main() -> None:
    nb = {
        "cells": CELLS,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1))
    print(f"написал {OUT}  ({len(CELLS)} ячеек)")


if __name__ == "__main__":
    main()
