"""seq2seq: Haskell-IR -> Lean-код. Реализация перевода через общий IR.

Это последняя стрелка пайплайна: исходник -> frontend -> IR -> [НЕЙРОСЕТЬ] -> код.
Корпус крошечный (PoC), модель переобучается — но механизм end-to-end рабочий:
её вход — наш общий IR, выход — код на другом языке.

Запуск:  just train   (или PYTHONPATH=. poetry run python ml/train.py)
"""
from __future__ import annotations

import json
from pathlib import Path

import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parent.parent
torch.manual_seed(0)

PAD, SOS, EOS = 0, 1, 2


# --------------------------------------------------------------------------- #
# Данные / словарь                                                            #
# --------------------------------------------------------------------------- #


def load_data():
    rows = json.loads((ROOT / "ml" / "dataset.json").read_text())
    chars = sorted({c for r in rows for c in (r["haskell_ir"] + r["lean_src"])})
    stoi = {c: i + 3 for i, c in enumerate(chars)}  # 0..2 — спецтокены
    itos = {i: c for c, i in stoi.items()}
    return rows, stoi, itos


def enc(s, stoi):
    return [stoi[c] for c in s]


def pad(seqs, length):
    return [s + [PAD] * (length - len(s)) for s in seqs]


# --------------------------------------------------------------------------- #
# Модель                                                                      #
# --------------------------------------------------------------------------- #


class Seq2Seq(nn.Module):
    """GRU encoder-decoder с dot-product attention по токенам IR."""

    def __init__(self, vocab, emb=64, hid=128):
        super().__init__()
        self.emb = nn.Embedding(vocab, emb, padding_idx=PAD)
        self.enc = nn.GRU(emb, hid, batch_first=True)
        self.dec = nn.GRU(emb + hid, hid, batch_first=True)
        self.out = nn.Linear(hid * 2, vocab)

    def encode(self, src):
        enc_out, h = self.enc(self.emb(src))
        mask = src != PAD
        return enc_out, h, mask

    def step(self, tok, h, enc_out, mask):
        e = self.emb(tok)                                  # B,1,E
        q = h[-1]                                           # B,H
        scores = (enc_out * q.unsqueeze(1)).sum(-1)         # B,Tin
        scores = scores.masked_fill(~mask, -1e9)
        w = torch.softmax(scores, dim=1)                    # B,Tin
        ctx = (w.unsqueeze(-1) * enc_out).sum(1)            # B,H
        o, h = self.dec(torch.cat([e, ctx.unsqueeze(1)], -1), h)
        logit = self.out(torch.cat([o.squeeze(1), ctx], -1))  # B,V
        return logit, h

    def forward(self, src, tgt_in):
        enc_out, h, mask = self.encode(src)
        logits = []
        for t in range(tgt_in.size(1)):
            logit, h = self.step(tgt_in[:, t : t + 1], h, enc_out, mask)
            logits.append(logit)
        return torch.stack(logits, dim=1)                   # B,T,V

    @torch.no_grad()
    def translate(self, src, max_len=200):
        enc_out, h, mask = self.encode(src)
        tok = torch.tensor([[SOS]])
        out = []
        for _ in range(max_len):
            logit, h = self.step(tok, h, enc_out, mask)
            nxt = int(logit.argmax(-1))
            if nxt == EOS:
                break
            out.append(nxt)
            tok = torch.tensor([[nxt]])
        return out


# --------------------------------------------------------------------------- #
# Обучение                                                                     #
# --------------------------------------------------------------------------- #


VAL_FRAC = 0.2  # доля функций в held-out для проверки генерализации


def evaluate(model, rows, stoi, itos):
    exact, shown = 0, []
    for r in rows:
        s = torch.tensor([enc(r["haskell_ir"], stoi)])
        pred = "".join(itos[i] for i in model.translate(s))
        ok = pred == r["lean_src"]
        exact += ok
        shown.append((r["name"], ok, r["lean_src"], pred))
    return exact, shown


def main():
    rows, stoi, itos = load_data()
    vocab = len(stoi) + 3

    # train/val split (детерминированный): часть функций модель НЕ видит при обучении
    rng = torch.Generator().manual_seed(0)
    perm = torch.randperm(len(rows), generator=rng).tolist()
    n_val = max(1, int(len(rows) * VAL_FRAC))
    val_idx = set(perm[:n_val])
    train_rows = [r for i, r in enumerate(rows) if i not in val_idx]
    val_rows = [r for i, r in enumerate(rows) if i in val_idx]

    src = [enc(r["haskell_ir"], stoi) for r in train_rows]
    tgt = [enc(r["lean_src"], stoi) for r in train_rows]
    Lsrc = max(map(len, src))
    Ltgt = max(len(t) for t in tgt) + 1

    src_t = torch.tensor(pad(src, Lsrc))
    tgt_in = torch.tensor(pad([[SOS] + t for t in tgt], Ltgt))
    tgt_out = torch.tensor(pad([t + [EOS] for t in tgt], Ltgt))

    model = Seq2Seq(vocab)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    loss_fn = nn.CrossEntropyLoss(ignore_index=PAD)

    print(f"vocab={vocab}  train={len(train_rows)}  val={len(val_rows)}  обучаем seq2seq IR->Lean ...\n")
    for epoch in range(1, 601):
        opt.zero_grad()
        logits = model(src_t, tgt_in)
        loss = loss_fn(logits.reshape(-1, vocab), tgt_out.reshape(-1))
        loss.backward()
        opt.step()
        if epoch % 100 == 0 or epoch == 1:
            print(f"  epoch {epoch:4d}   loss {loss.item():.4f}")

    tr_exact, _ = evaluate(model, train_rows, stoi, itos)
    val_exact, val_shown = evaluate(model, val_rows, stoi, itos)

    print("\n=== Held-out (модель эти функции НЕ видела) ===")
    for name, ok, gold, pred in val_shown:
        print(f"\n[{name}]  {'✓' if ok else '✗'}")
        print(f"  gold: {gold}")
        print(f"  pred: {pred}")

    print(f"\ntrain exact: {tr_exact}/{len(train_rows)}   "
          f"val exact: {val_exact}/{len(val_rows)}")


if __name__ == "__main__":
    main()
