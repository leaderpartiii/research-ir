import Lean
open Lean Meta

/-- Пример, зеркальный к Haskell `Add.hs`: своя индуктивная Nat + рекурсивный add. -/
inductive MyNat where
  | zero : MyNat
  | succ : MyNat → MyNat

def add : MyNat → MyNat → MyNat
  | MyNat.zero,   b => b
  | MyNat.succ m, b => MyNat.succ (add m b)

/-- Нерекурсивный пример для чистого кросс-языкового сравнения с Haskell. -/
def inc (n : MyNat) : MyNat := MyNat.succ n

/-- Короткое имя (последний компонент), чтобы совпадать с occ-name из Haskell. -/
def short (n : Name) : String :=
  (toString n |>.splitOn ".").getLast!

/-- Безопасный атом sexpr: без пробелов и скобок. -/
def atom (s : String) : String :=
  String.ofList (s.toList.filter (fun c => c != ' ' && c != '(' && c != ')'))

/-- Lean `Expr` -> общий IR (sexpr). -/
partial def toIR : Expr → String
  | .bvar i        => s!"(var _bv{i})"
  | .fvar id       => s!"(var {atom (toString id.name)})"
  | .mvar _        => "(const _mvar)"
  | .sort _        => "(sort Type)"
  | .const n _     => s!"(const {atom (short n)})"
  | .app f a       => s!"(app {toIR f} {toIR a})"
  | .lam n t b _   => s!"(lam ({atom (toString n)} {toIR t}) {toIR b})"
  | .forallE n t b _ => s!"(pi ({atom (toString n)} {toIR t}) {toIR b})"
  | .letE n t v b _  => s!"(let ({atom (toString n)} {toIR t} {toIR v}) {toIR b})"
  | .lit (.natVal v) => s!"(lit {v} nat)"
  | .lit (.strVal v) => s!"(lit {atom v} str)"
  | .mdata _ e     => toIR e
  | .proj _ i e    => s!"(app (const _proj{i}) {toIR e})"

def dumpConst (name : Name) : MetaM String := do
  let some info := (← getEnv).find? name | throwError "not found: {name}"
  let some val := info.value? | throwError "no value: {name}"
  return s!"(module (def {short name} (const _ty) {toIR val}))"

#eval show MetaM Unit from do
  IO.println (← dumpConst ``inc)
