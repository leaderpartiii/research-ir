"""Корпус функций для датасета — ЕДИНОЕ место, куда добавлять примеры.

Чтобы добавить функцию:
  1) допиши кортеж (name, haskell_src, lean_src) в FUNCTIONS;
  2) обе версии должны КОМПИЛИРОВАТЬСЯ (Haskell — в Corpus.hs, Lean — в Corpus.lean);
  3) для Lean порядок важен: определение должно идти ДО использования;
  4) новый тип? добавь его объявление и в HASKELL_PRELUDE, и в LEAN_PRELUDE.

Стиль таргетов держим единым (Lean: `:= match x with | ...`), это помогает модели.
Потом:  just dataset
"""

HASKELL_PRELUDE = "data Nat = Zero | Succ Nat"
LEAN_PRELUDE = "inductive MyNat where\n  | zero : MyNat\n  | succ : MyNat -> MyNat"


def _plus(name: str, k: int):
    hs_body = "n"
    lean_body = "n"
    for _ in range(k):
        hs_body = f"Succ ({hs_body})" if hs_body != "n" else "Succ n"
        lean_body = f"MyNat.succ ({lean_body})" if lean_body != "n" else "MyNat.succ n"
    return (name,
            f"{name} n = {hs_body}",
            f"def {name} (n : MyNat) : MyNat := {lean_body}")


FUNCTIONS: list[tuple[str, str, str]] = [
    # --- Bool: базовые ---
    ("idB", "idB b = b",
     "def idB (b : Bool) : Bool := b"),
    ("notB", "notB b = case b of { True -> False; False -> True }",
     "def notB (b : Bool) : Bool := match b with | true => false | false => true"),
    ("constTrue", "constTrue b = True",
     "def constTrue (b : Bool) : Bool := true"),
    ("constFalse", "constFalse b = False",
     "def constFalse (b : Bool) : Bool := false"),
    ("andB", "andB a b = case a of { True -> b; False -> False }",
     "def andB (a b : Bool) : Bool := match a with | true => b | false => false"),
    ("orB", "orB a b = case a of { True -> True; False -> b }",
     "def orB (a b : Bool) : Bool := match a with | true => true | false => b"),
    # --- Bool: производные ---
    ("nandB", "nandB a b = notB (andB a b)",
     "def nandB (a b : Bool) : Bool := notB (andB a b)"),
    ("norB", "norB a b = notB (orB a b)",
     "def norB (a b : Bool) : Bool := notB (orB a b)"),
    ("xorB", "xorB a b = case a of { True -> notB b; False -> b }",
     "def xorB (a b : Bool) : Bool := match a with | true => notB b | false => b"),
    ("implyB", "implyB a b = case a of { True -> b; False -> True }",
     "def implyB (a b : Bool) : Bool := match a with | true => b | false => true"),
    ("nimplyB", "nimplyB a b = andB a (notB b)",
     "def nimplyB (a b : Bool) : Bool := andB a (notB b)"),
    ("eqB", "eqB a b = case a of { True -> b; False -> notB b }",
     "def eqB (a b : Bool) : Bool := match a with | true => b | false => notB b"),
    ("and3", "and3 a b c = andB a (andB b c)",
     "def and3 (a b c : Bool) : Bool := andB a (andB b c)"),
    ("or3", "or3 a b c = orB a (orB b c)",
     "def or3 (a b c : Bool) : Bool := orB a (orB b c)"),
    ("xor3", "xor3 a b c = xorB a (xorB b c)",
     "def xor3 (a b c : Bool) : Bool := xorB a (xorB b c)"),
    ("majority3", "majority3 a b c = orB (andB a b) (orB (andB a c) (andB b c))",
     "def majority3 (a b c : Bool) : Bool := orB (andB a b) (orB (andB a c) (andB b c))"),
    # --- Nat: простые ---
    _plus("inc", 1),
    _plus("plus2", 2),
    _plus("plus3", 3),
    _plus("plus4", 4),
    _plus("plus5", 5),
    _plus("plus6", 6),
    _plus("plus7", 7),
    _plus("plus8", 8),
    ("idn", "idn n = n",
     "def idn (n : MyNat) : MyNat := n"),
    ("czero", "czero n = Zero",
     "def czero (n : MyNat) : MyNat := MyNat.zero"),
    ("predn", "predn n = case n of { Zero -> Zero; Succ m -> m }",
     "def predn (n : MyNat) : MyNat := match n with | MyNat.zero => MyNat.zero | MyNat.succ m => m"),
    # --- Nat: рекурсивные ---
    ("add", "add a b = case a of { Zero -> b; Succ m -> Succ (add m b) }",
     "def add (a b : MyNat) : MyNat := match a with | MyNat.zero => b | MyNat.succ m => MyNat.succ (add m b)"),
    ("mul", "mul a b = case a of { Zero -> Zero; Succ m -> add b (mul m b) }",
     "def mul (a b : MyNat) : MyNat := match a with | MyNat.zero => MyNat.zero | MyNat.succ m => add b (mul m b)"),
    # --- Nat: производные ---
    ("double", "double n = add n n",
     "def double (n : MyNat) : MyNat := add n n"),
    ("triple", "triple n = add n (add n n)",
     "def triple (n : MyNat) : MyNat := add n (add n n)"),
    ("quad", "quad n = double (double n)",
     "def quad (n : MyNat) : MyNat := double (double n)"),
    ("addThree", "addThree a b c = add a (add b c)",
     "def addThree (a b c : MyNat) : MyNat := add a (add b c)"),
    ("addFour", "addFour a b c d = add (add a b) (add c d)",
     "def addFour (a b c d : MyNat) : MyNat := add (add a b) (add c d)"),
    ("square", "square n = mul n n",
     "def square (n : MyNat) : MyNat := mul n n"),
    ("cube", "cube n = mul n (mul n n)",
     "def cube (n : MyNat) : MyNat := mul n (mul n n)"),
    ("sextuple", "sextuple n = add (triple n) (triple n)",
     "def sextuple (n : MyNat) : MyNat := add (triple n) (triple n)"),
    ("mulThree", "mulThree a b c = mul a (mul b c)",
     "def mulThree (a b c : MyNat) : MyNat := mul a (mul b c)"),
    ("addMul", "addMul a b = add a (mul a b)",
     "def addMul (a b : MyNat) : MyNat := add a (mul a b)"),
    ("sumSquares", "sumSquares a b = add (square a) (square b)",
     "def sumSquares (a b : MyNat) : MyNat := add (square a) (square b)"),
    ("doubleInc", "doubleInc n = Succ (double n)",
     "def doubleInc (n : MyNat) : MyNat := MyNat.succ (double n)"),
    ("quadInc", "quadInc n = Succ (quad n)",
     "def quadInc (n : MyNat) : MyNat := MyNat.succ (quad n)"),
    # --- Nat -> Bool ---
    ("isZero", "isZero n = case n of { Zero -> True; Succ m -> False }",
     "def isZero (n : MyNat) : Bool := match n with | MyNat.zero => true | MyNat.succ m => false"),
    ("notZero", "notZero n = notB (isZero n)",
     "def notZero (n : MyNat) : Bool := notB (isZero n)"),
    ("isOne", "isOne n = case n of { Zero -> False; Succ m -> isZero m }",
     "def isOne (n : MyNat) : Bool := match n with | MyNat.zero => false | MyNat.succ m => isZero m"),
    ("isTwo", "isTwo n = case n of { Zero -> False; Succ m -> isOne m }",
     "def isTwo (n : MyNat) : Bool := match n with | MyNat.zero => false | MyNat.succ m => isOne m"),
]
