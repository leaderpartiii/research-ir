module Add where

-- Самодостаточный рекурсивный пример над собственным Nat:
-- никаких Int/тайпклассов -> Core без словарей и анбоксинга.

data Nat = Zero | Succ Nat

add :: Nat -> Nat -> Nat
add a b = case a of
  Zero   -> b
  Succ m -> Succ (add m b)

-- Нерекурсивный пример для чистого кросс-языкового сравнения с Lean.
inc :: Nat -> Nat
inc n = Succ n
