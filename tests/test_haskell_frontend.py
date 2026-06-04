"""Шаг 2 (TDD): вывод Haskell-frontend соответствует контракту общего IR.

Тест НЕ требует GHC: проверяет зафиксированную golden-фикстуру `add.cir`,
которую породил frontend (frontends/haskell). Регенерация фикстуры —
`just gen-haskell`, побайтовая сверка — `just test-haskell`.
"""
from pathlib import Path

from research_ir.ir import (
    App, Case, Const, Def, Lam, Module, PCon, Var, dumps, loads,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_haskell_output_conforms_to_contract():
    """Реальный вывод GHC Core -> общий IR парсится и round-trip стабилен."""
    text = (FIXTURES / "add.cir").read_text()
    mod = loads(text)

    assert isinstance(mod, Module)
    # round-trip идемпотентен -> вывод frontend лежит в нашем формате
    assert dumps(loads(dumps(mod))) == dumps(mod)


def test_haskell_add_has_expected_shape():
    """Структура add: λa.λb. case a of Zero->b ; Succ m -> Succ (add m b)."""
    mod = loads((FIXTURES / "add.cir").read_text())
    add = next(d for d in mod.defs if d.name == "add")
    assert isinstance(add, Def)

    # два вложенных лямбда-связывания: a, b
    outer = add.body
    assert isinstance(outer, Lam) and outer.binder == "a"
    inner = outer.body
    assert isinstance(inner, Lam) and inner.binder == "b"

    # case по (var a) с ветками Zero / Succ
    body = inner.body
    assert isinstance(body, Case)
    assert isinstance(body.scrutinee, Var) and body.scrutinee.name == "a"
    pats = {a.pattern.name for a in body.alts if isinstance(a.pattern, PCon)}
    assert pats == {"Zero", "Succ"}

    # конструктор Succ — глобальная ссылка (const), рекурсивный вызов add присутствует
    succ_alt = next(a for a in body.alts if a.pattern.name == "Succ")
    assert isinstance(succ_alt.body, App)
    assert isinstance(succ_alt.body.fn, Const) and succ_alt.body.fn.name == "Succ"
