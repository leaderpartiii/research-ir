"""Шаг 4 — главный тезис PoC: общий IR из РАЗНЫХ компиляторов совпадает по структуре.

`inc n = Succ n` независимо прошёл через GHC Core (Haskell) и Lean Expr (Lean).
Имена различаются (Succ/succ, n/_bv0), но структурный скелет обязан совпасть.
"""
from pathlib import Path

from research_ir.ir import loads, shape

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _inc_def(fixture: str):
    mod = loads((FIXTURES / fixture).read_text())
    return next(d for d in mod.defs if d.name == "inc")


def test_inc_has_same_shape_across_haskell_and_lean():
    hs = _inc_def("add.cir")        # из GHC Core
    lean = _inc_def("lean_inc.cir")  # из Lean Expr
    assert shape(hs) == shape(lean), (
        f"shapes differ:\n  haskell={shape(hs)}\n  lean={shape(lean)}"
    )
