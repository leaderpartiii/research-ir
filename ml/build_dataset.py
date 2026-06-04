"""Сборка датасета для обучения перевода через IR.

Единый источник правды — CORPUS: функции над Nat, записанные на Haskell и Lean.
Скрипт:
  1) генерирует frontends/haskell/examples/Corpus.hs и frontends/lean/Corpus.lean
  2) гоняет оба frontend'а -> общий IR на каждую функцию
  3) пишет ml/dataset.json: пары (haskell_ir -> lean_src) для seq2seq.

Запуск:  just dataset   (или poetry run python ml/build_dataset.py)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from corpus import FUNCTIONS as CORPUS, HASKELL_PRELUDE, LEAN_PRELUDE
from research_ir.ir import Module, dumps, loads

ROOT = Path(__file__).resolve().parent.parent
HS_DIR = ROOT / "frontends" / "haskell"
LEAN_DIR = ROOT / "frontends" / "lean"

LEAN_TOIR = r'''
def short (n : Name) : String := (toString n |>.splitOn ".").getLast!
def atomS (s : String) : String :=
  String.ofList (s.toList.filter (fun c => c != ' ' && c != '(' && c != ')'))

partial def toIR : Expr -> String
  | .bvar i        => s!"(var _bv{i})"
  | .fvar id       => s!"(var {atomS (toString id.name)})"
  | .mvar _        => "(const _mvar)"
  | .sort _        => "(sort Type)"
  | .const n _     => s!"(const {atomS (short n)})"
  | .app f a       => s!"(app {toIR f} {toIR a})"
  | .lam n t b _   => s!"(lam ({atomS (toString n)} {toIR t}) {toIR b})"
  | .forallE n t b _ => s!"(pi ({atomS (toString n)} {toIR t}) {toIR b})"
  | .letE n t v b _  => s!"(let ({atomS (toString n)} {toIR t} {toIR v}) {toIR b})"
  | .lit (.natVal v) => s!"(lit {v} nat)"
  | .lit (.strVal v) => s!"(lit {atomS v} str)"
  | .mdata _ e     => toIR e
  | .proj _ i e    => s!"(app (const _proj{i}) {toIR e})"

def dumpConst (name : Name) : MetaM String := do
  let some info := (← getEnv).find? name | throwError "not found: {name}"
  let some val := info.value? | throwError "no value: {name}"
  return s!"(module (def {short name} (const _ty) {toIR val}))"
'''


def gen_haskell() -> str:
    defs = "\n".join(src for _, src, _ in CORPUS)
    return f"module Corpus where\n\n{HASKELL_PRELUDE}\n\n{defs}\n"


def gen_lean() -> str:
    defs = "\n".join(src for _, _, src in CORPUS)
    names = " ".join(f"``{n}" for n, _, _ in CORPUS)
    loop = (
        "#eval show MetaM Unit from do\n"
        f"  let names := [{names}]\n"
        "  for nm in names do\n"
        "    IO.println s!\"{nm}|||{(← dumpConst nm)}\"\n"
    )
    return (
        "import Lean\nopen Lean Meta\n\n"
        f"{LEAN_PRELUDE}\n\n"
        f"{defs}\n{LEAN_TOIR}\n{loop}"
    )


def run(cmd: list[str], cwd: Path) -> str:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        # частая причина — новая функция в corpus.py не компилируется
        raise SystemExit(
            f"\n[ОШИБКА] команда упала: {' '.join(cmd)}\n"
            f"(проверь свежие функции в ml/corpus.py)\n\n{p.stderr}"
        )
    return p.stdout


def haskell_irs() -> dict[str, str]:
    (HS_DIR / "examples" / "Corpus.hs").write_text(gen_haskell())
    out = run(["cabal", "run", "-v0", "core-to-ir", "--", "examples/Corpus.hs"], HS_DIR)
    mod = loads(out)
    return {d.name: dumps(Module((d,))) for d in mod.defs}


def lean_irs_and_src() -> dict[str, str]:
    (LEAN_DIR / "Corpus.lean").write_text(gen_lean())
    out = run(["lean", "Corpus.lean"], LEAN_DIR)
    irs = {}
    for line in out.splitlines():
        if "|||" in line:
            name, ir = line.split("|||", 1)
            irs[name.strip()] = ir.strip()
    return irs


def main() -> None:
    hs = haskell_irs()
    lean_src = {n: src for n, _, src in CORPUS}
    rows = []
    for name, _, _ in CORPUS:
        if name in hs:
            rows.append({"name": name, "haskell_ir": hs[name], "lean_src": lean_src[name]})
    out_path = ROOT / "ml" / "dataset.json"
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"wrote {out_path} with {len(rows)} pairs")
    for r in rows:
        print(f"  {r['name']:10s} ir[{len(r['haskell_ir'])}] -> lean[{len(r['lean_src'])}]")


if __name__ == "__main__":
    main()
