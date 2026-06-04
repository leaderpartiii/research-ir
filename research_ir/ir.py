"""Общий IR: типы AST + ридер/принтер S-выражений.

Контракт описан в docs/common-ir.md. Это символьное представление — никакой
нейросети тут нет, только данные. frontends (Haskell/Lean) ПИШУТ этот формат,
данный модуль его ЧИТАЕТ (loads) и печатает обратно (dumps).
"""
from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# AST                                                                         #
# --------------------------------------------------------------------------- #


class Node:
    """Базовый класс для всех узлов IR (термы, паттерны, def, module)."""


# --- термы --------------------------------------------------------------- #


@dataclass(frozen=True)
class Var(Node):
    name: str


@dataclass(frozen=True)
class Const(Node):
    name: str


@dataclass(frozen=True)
class Lit(Node):
    value: str
    kind: str


@dataclass(frozen=True)
class App(Node):
    fn: Node
    arg: Node


@dataclass(frozen=True)
class Lam(Node):
    binder: str
    binder_type: Node
    body: Node


@dataclass(frozen=True)
class Pi(Node):
    binder: str
    binder_type: Node
    body: Node


@dataclass(frozen=True)
class Let(Node):
    binder: str
    binder_type: Node
    value: Node
    body: Node


@dataclass(frozen=True)
class Case(Node):
    scrutinee: Node
    alts: tuple["Alt", ...]


@dataclass(frozen=True)
class Con(Node):
    name: str
    args: tuple[Node, ...]


@dataclass(frozen=True)
class Sort(Node):
    name: str


# --- паттерны ------------------------------------------------------------ #


@dataclass(frozen=True)
class PCon(Node):
    name: str
    binders: list[str]


@dataclass(frozen=True)
class PLit(Node):
    value: str
    kind: str


@dataclass(frozen=True)
class PWild(Node):
    pass


@dataclass(frozen=True)
class Alt(Node):
    pattern: Node
    body: Node


# --- верхний уровень ----------------------------------------------------- #


@dataclass(frozen=True)
class Def(Node):
    name: str
    type: Node
    body: Node


@dataclass(frozen=True)
class Module(Node):
    defs: tuple[Def, ...]


# --------------------------------------------------------------------------- #
# S-expression reader: текст -> вложенные списки (str | list)                  #
# --------------------------------------------------------------------------- #


def _tokenize(text: str) -> list[str]:
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c in "()":
            out.append(c)
            i += 1
        elif c == '"':  # строковый литерал в кавычках
            j = i + 1
            while j < n and text[j] != '"':
                j += 1
            out.append(text[i : j + 1])
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()":
                j += 1
            out.append(text[i:j])
            i = j
    return out


def _parse_sexpr(tokens: list[str], pos: int) -> tuple[object, int]:
    if pos >= len(tokens):
        raise ValueError("unexpected end of input")
    tok = tokens[pos]
    if tok == "(":
        items: list[object] = []
        pos += 1
        while pos < len(tokens) and tokens[pos] != ")":
            item, pos = _parse_sexpr(tokens, pos)
            items.append(item)
        if pos >= len(tokens):
            raise ValueError("unbalanced '('")
        return items, pos + 1  # пропускаем ')'
    if tok == ")":
        raise ValueError("unexpected ')'")
    return tok, pos + 1


def _read_sexpr(text: str) -> object:
    tokens = _tokenize(text)
    sexpr, pos = _parse_sexpr(tokens, 0)
    if pos != len(tokens):
        raise ValueError("trailing tokens after top-level expression")
    return sexpr


# --------------------------------------------------------------------------- #
# sexpr (списки) -> AST                                                        #
# --------------------------------------------------------------------------- #


def _atom(x: object) -> str:
    if not isinstance(x, str):
        raise ValueError(f"expected atom, got list: {x!r}")
    return x


def _to_term(s: object) -> Node:
    if isinstance(s, str):
        # голый атом термом быть не может — все термы помечены головой
        raise ValueError(f"bare atom is not a term: {s!r}")
    if not s:
        raise ValueError("empty list is not a term")

    head = _atom(s[0])
    if head == "var":
        return Var(_atom(s[1]))
    if head == "const":
        return Const(_atom(s[1]))
    if head == "lit":
        return Lit(_atom(s[1]), _atom(s[2]))
    if head == "app":
        return App(_to_term(s[1]), _to_term(s[2]))
    if head == "lam":
        name, ty = s[1]  # (name <Term>)
        return Lam(_atom(name), _to_term(ty), _to_term(s[2]))
    if head == "pi":
        name, ty = s[1]
        return Pi(_atom(name), _to_term(ty), _to_term(s[2]))
    if head == "let":
        name, ty, val = s[1]  # (name <Term> <Term>)
        return Let(_atom(name), _to_term(ty), _to_term(val), _to_term(s[2]))
    if head == "case":
        return Case(_to_term(s[1]), tuple(_to_alt(a) for a in s[2:]))
    if head == "con":
        return Con(_atom(s[1]), tuple(_to_term(a) for a in s[2]))
    if head == "sort":
        return Sort(_atom(s[1]))
    raise ValueError(f"unknown term head: {head!r}")


def _to_alt(s: object) -> Alt:
    if isinstance(s, str) or not s or _atom(s[0]) != "alt":
        raise ValueError(f"expected (alt ...), got: {s!r}")
    return Alt(_to_pattern(s[1]), _to_term(s[2]))


def _to_pattern(s: object) -> Node:
    if isinstance(s, str) or not s:
        raise ValueError(f"expected pattern, got: {s!r}")
    head = _atom(s[0])
    if head == "pcon":
        return PCon(_atom(s[1]), [_atom(b) for b in s[2]])
    if head == "plit":
        return PLit(_atom(s[1]), _atom(s[2]))
    if head == "pwild":
        return PWild()
    raise ValueError(f"unknown pattern head: {head!r}")


def _to_def(s: object) -> Def:
    if isinstance(s, str) or not s or _atom(s[0]) != "def":
        raise ValueError(f"expected (def ...), got: {s!r}")
    return Def(_atom(s[1]), _to_term(s[2]), _to_term(s[3]))


def loads(text: str) -> Module:
    """Разобрать текст общего IR (module) в AST."""
    s = _read_sexpr(text)
    if isinstance(s, str) or not s or _atom(s[0]) != "module":
        raise ValueError("top-level form must be (module ...)")
    return Module(tuple(_to_def(d) for d in s[1:]))


# --------------------------------------------------------------------------- #
# AST -> sexpr-текст (стабильная печать)                                       #
# --------------------------------------------------------------------------- #


def _p(node: Node) -> str:
    match node:
        case Var(name):
            return f"(var {name})"
        case Const(name):
            return f"(const {name})"
        case Lit(value, kind):
            return f"(lit {value} {kind})"
        case App(fn, arg):
            return f"(app {_p(fn)} {_p(arg)})"
        case Lam(b, ty, body):
            return f"(lam ({b} {_p(ty)}) {_p(body)})"
        case Pi(b, ty, body):
            return f"(pi ({b} {_p(ty)}) {_p(body)})"
        case Let(b, ty, val, body):
            return f"(let ({b} {_p(ty)} {_p(val)}) {_p(body)})"
        case Case(scrut, alts):
            inner = " ".join(_p(a) for a in alts)
            return f"(case {_p(scrut)} {inner})"
        case Con(name, args):
            inner = " ".join(_p(a) for a in args)
            return f"(con {name} ({inner}))"
        case Sort(name):
            return f"(sort {name})"
        case Alt(pat, body):
            return f"(alt {_p(pat)} {_p(body)})"
        case PCon(name, binders):
            return f"(pcon {name} ({' '.join(binders)}))"
        case PLit(value, kind):
            return f"(plit {value} {kind})"
        case PWild():
            return "(pwild)"
        case Def(name, ty, body):
            return f"(def {name} {_p(ty)} {_p(body)})"
        case Module(defs):
            return "(module " + " ".join(_p(d) for d in defs) + ")"
    raise ValueError(f"cannot print node: {node!r}")


def dumps(module: Node) -> str:
    """Напечатать AST обратно в текст общего IR (одной строкой, стабильно)."""
    return _p(module)


# --------------------------------------------------------------------------- #
# shape: структурный скелет (стираем имена/литералы)                           #
# --------------------------------------------------------------------------- #


def shape(node: Node) -> object:
    """Скелет терма без идентификаторов — для кросс-языкового сравнения.

    Стираем имена переменных/констант/конструкторов и значения литералов,
    оставляя только теги узлов и структуру. Если у двух программ из РАЗНЫХ
    языков совпадает shape — значит общий IR уловил одну и ту же семантику.
    """
    match node:
        case Var(_) | Const(_):
            return ("ref",)
        case Lit(_, _):
            return ("lit",)
        case Sort(_):
            return ("sort",)
        case App(fn, arg):
            return ("app", shape(fn), shape(arg))
        case Lam(_, ty, body):
            return ("lam", shape(ty), shape(body))
        case Pi(_, ty, body):
            return ("pi", shape(ty), shape(body))
        case Let(_, ty, val, body):
            return ("let", shape(ty), shape(val), shape(body))
        case Case(scrut, alts):
            return ("case", shape(scrut), tuple(shape(a) for a in alts))
        case Con(_, args):
            return ("con", tuple(shape(a) for a in args))
        case Alt(pat, body):
            return ("alt", shape(pat), shape(body))
        case PCon(_, binders):
            return ("pcon", len(binders))
        case PLit(_, _):
            return ("plit",)
        case PWild():
            return ("pwild",)
        case Def(_, ty, body):
            return ("def", shape(ty), shape(body))
        case Module(defs):
            return ("module", tuple(shape(d) for d in defs))
    raise ValueError(f"cannot shape node: {node!r}")
