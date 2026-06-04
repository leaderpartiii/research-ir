"""Апгрейд модели: дообучение предобученного CodeT5-small на переводе IR -> Lean.

В отличие от char-GRU (ml/train.py), здесь трансфер с модели, уже видевшей код:
токен-уровневый seq2seq-трансформер. На крошечных данных это даёт реальный шанс
на генерализацию (held-out), а не только запоминание.

Запуск:  just train-t5   (нужен ML-стек и доступ в интернет для скачивания весов)
"""
from __future__ import annotations

import difflib
import json
import os
import warnings
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TQDM_DISABLE", "1")
warnings.filterwarnings("ignore")

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from transformers.utils import logging as hf_logging

hf_logging.set_verbosity_error()

ROOT = Path(__file__).resolve().parent.parent
MODEL = "t5-small"
PREFIX = "translate IR to Lean: "
VAL_FRAC = 0.2
EPOCHS = 120
# constrained decoding (softmax только по токенам корпуса). На наших данных
# модель и так выдаёт валидные токены, а жёсткая маска ломает beam search и
# УХУДШАЕТ результат (8/9 -> 4/9), поэтому по умолчанию выключено.
CONSTRAIN = False
torch.manual_seed(0)


def split(rows):
    rng = torch.Generator().manual_seed(0)
    perm = torch.randperm(len(rows), generator=rng).tolist()
    n_val = max(1, int(len(rows) * VAL_FRAC))
    val_idx = set(perm[:n_val])
    train = [r for i, r in enumerate(rows) if i not in val_idx]
    val = [r for i, r in enumerate(rows) if i in val_idx]
    return train, val


def evaluate(model, tok, rows, device, allowed_ids=None):
    """allowed_ids: если задан — constrained decoding (softmax только по валидным токенам)."""
    model.eval()
    # маска: на каждом шаге разрешаем только токены из словаря корпуса
    allow_fn = (lambda batch_id, sent: allowed_ids) if allowed_ids else None
    exact, sim_sum, shown = 0, 0.0, []
    for r in rows:
        ids = tok(PREFIX + r["haskell_ir"], return_tensors="pt", truncation=True,
                  max_length=512).input_ids.to(device)
        with torch.no_grad():
            out = model.generate(ids, max_length=200, num_beams=4,
                                  prefix_allowed_tokens_fn=allow_fn)
        pred = tok.decode(out[0], skip_special_tokens=True).strip()
        gold = r["lean_src"].strip()
        ok = pred == gold
        sim = difflib.SequenceMatcher(None, pred, gold).ratio()  # 0..1 близость
        exact += ok
        sim_sum += sim
        shown.append((r["name"], ok, sim, gold, pred))
    return exact, sim_sum / max(1, len(rows)), shown


def main():
    rows = json.loads((ROOT / "ml" / "dataset.json").read_text())
    train_rows, val_rows = split(rows)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"модель: {MODEL}   train={len(train_rows)}  val={len(val_rows)}  device={device}")
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL).to(device)

    inputs = [PREFIX + r["haskell_ir"] for r in train_rows]
    targets = [r["lean_src"] for r in train_rows]
    enc = tok(inputs, padding=True, truncation=True, max_length=512, return_tensors="pt")
    label_ids = tok(text_target=targets, padding=True, truncation=True,
                    max_length=256, return_tensors="pt").input_ids

    # словарь валидных выходных токенов (для constrained decoding)
    allowed_ids = sorted(set(label_ids.flatten().tolist()) |
                         {tok.eos_token_id, tok.pad_token_id})

    labels = label_ids.clone()
    labels[labels == tok.pad_token_id] = -100  # игнор pad в loss
    enc = {k: v.to(device) for k, v in enc.items()}
    labels = labels.to(device)

    opt = torch.optim.AdamW(model.parameters(), lr=5e-4)
    print("\nдообучаем ...")
    model.train()
    for epoch in range(1, EPOCHS + 1):
        opt.zero_grad()
        loss = model(**enc, labels=labels).loss
        loss.backward()
        opt.step()
        if epoch % 10 == 0 or epoch == 1:
            print(f"  epoch {epoch:3d}   loss {loss.item():.4f}")

    constrain = allowed_ids if CONSTRAIN else None
    tr_exact, tr_sim, _ = evaluate(model, tok, train_rows, device, constrain)
    val_exact, val_sim, val_shown = evaluate(model, tok, val_rows, device, constrain)

    print("\n=== Held-out (модель эти функции НЕ видела при обучении) ===")
    for name, ok, sim, gold, pred in val_shown:
        print(f"\n[{name}]  {'✓ exact' if ok else f'~{sim:.0%} близость'}")
        print(f"  gold: {gold}")
        print(f"  pred: {pred}")

    print(f"\ntrain:  exact {tr_exact}/{len(train_rows)}   близость {tr_sim:.1%}")
    print(f"val:    exact {val_exact}/{len(val_rows)}   близость {val_sim:.1%}")


if __name__ == "__main__":
    main()
