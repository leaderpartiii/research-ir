"""Шаг 1 (TDD): контракт общего IR — ридер sexpr и round-trip.

Запуск:  python3 -m pytest tests/test_ir.py -q
Тулчейны GHC/Lean тут не нужны — чистый Python на фикстурах.
"""
from pathlib import Path

from research_ir.ir import (
    App, Case, Const, Def, Lam, Lit, Module, PCon, Var, dumps, loads,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_parses_factorial_structure():
    """Эталонный factorial.cir разбирается в ожидаемое дерево."""
    mod = loads((FIXTURES / "factorial.cir").read_text())

    assert isinstance(mod, Module)
    assert len(mod.defs) == 1

    fac = mod.defs[0]
    assert isinstance(fac, Def)
    assert fac.name == "factorial"

    # body — это лямбда по n
    assert isinstance(fac.body, Lam)
    assert fac.body.binder == "n"
    assert isinstance(fac.body.binder_type, Const) and fac.body.binder_type.name == "Nat"

    # тело лямбды — case по (var n) с двумя ветками
    body = fac.body.body
    assert isinstance(body, Case)
    assert isinstance(body.scrutinee, Var) and body.scrutinee.name == "n"
    assert len(body.alts) == 2

    # первая ветка: zero -> (lit 1 nat)
    a0 = body.alts[0]
    assert isinstance(a0.pattern, PCon) and a0.pattern.name == "zero"
    assert isinstance(a0.body, Lit) and a0.body.value == "1" and a0.body.kind == "nat"

    # вторая ветка: succ m -> mul n (factorial m)
    a1 = body.alts[1]
    assert isinstance(a1.pattern, PCon) and a1.pattern.name == "succ"
    assert a1.pattern.binders == ["m"]
    assert isinstance(a1.body, App)


def test_roundtrip_is_stable():
    """parse -> dumps -> parse даёт равное дерево, и текст стабилизируется."""
    text = (FIXTURES / "factorial.cir").read_text()
    tree1 = loads(text)
    out1 = dumps(tree1)
    tree2 = loads(out1)
    out2 = dumps(tree2)

    assert tree1 == tree2          # dataclass-равенство
    assert out1 == out2            # печать идемпотентна


def test_rejects_unknown_head():
    """Неизвестная голова терма — явная ошибка, а не молчаливый мусор."""
    import pytest

    with pytest.raises(ValueError):
        loads("(module (def f (sort Type) (bogus 1 2)))")
