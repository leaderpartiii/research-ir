# research-ir

**Proof of concept: перевод функциональных языков (Haskell ↔ Lean) через общий IR + NLP — без LLVM.**

Идея из *Code Translation with Compiler Representations* (Szafraniec et al., ICLR 2023), где
C++/Java/Rust/Go переводят друг в друга, используя **LLVM IR** как общий семантический пивот.
Здесь то же самое для **функциональных языков**, которые в LLVM не ложатся: вместо LLVM берём
**нативные IR компиляторов** (GHC Core, Lean `Expr`) и нормализуем их в один общий IR, поверх
которого нейросеть учится переводить.

```
исходник --frontend--> нативный IR --> общий IR --[seq2seq + attention]--> код на другом языке
.hs / .lean            Core / Expr      (sexpr)        ОБУЧЕНИЕ                 (перевод)
```

---

## Результаты

Всё воспроизводится в **[`notebooks/demo.ipynb`](notebooks/demo.ipynb)** и  **[`notebooks/research-ir-notebook.ipynb`](notebooks/research-ir-notebook.ipynb)**(более полный ноутбук) — откройте и запустите с помощью **Run All**.
Ноутбук уже содержит **сохранённые outputs** последнего прогона; цифры ниже — оттуда.

### Главный результат — обучение перевода `IR → код`

seq2seq (GRU encoder-decoder с attention) получает на вход наш **общий IR** и выдаёт **код на
Lean**. Это и есть реализация перевода `Haskell → IR → Lean`.

Корпус из 11 функций над `Nat`, обучение из ноутбука:

```
vocab=49  pairs=11  обучаем seq2seq IR->Lean ...
  epoch    1   loss 3.9122
  epoch  100   loss 0.0874
  epoch  200   loss 0.0310
  epoch  400   loss 0.0062
exact match: 11/11
```

**11/11 точных переводов**, включая нетривиальные случаи. Например, рекурсивный `add`
(вход — Haskell-IR, выход — корректный код Lean, сгенерированный моделью):

```
ВХОД  (Haskell-IR):  (module (def add ... (case (var a) (alt (pcon Zero ()) (var b))
                       (alt (pcon Succ (m)) (app (const Succ) (app (app (var add) (var m)) (var b)))))))

ВЫХОД (модель, Lean): def add : MyNat -> MyNat -> MyNat
                        | MyNat.zero, b => b
                        | MyNat.succ m, b => MyNat.succ (add m b)
```

Так же корректно переводятся `predn` (через `match`), `double`/`quad` (ссылки на другие функции)
и остальные.

> Это PoC: корпус маленький, модель **переобучается**. Цель — доказать **механизм**
> (нейросеть читает наш IR и порождает код целевого языка), а не достичь генерализации.

### Вспомогательный результат — один IR для двух компиляторов

Чтобы перевод был возможен, IR из разных компиляторов должен быть согласован. Функция
`inc n = Succ n`, пройдя через GHC Core и Lean `Expr`, даёт структурно идентичный IR:

```lisp
Haskell (GHC Core):  (lam (n (const Nat))   (app (const Succ) (var n)))
Lean    (Expr)    :  (lam (n (const MyNat)) (app (const succ) (var _bv0)))
```

Отличаются только имена; структурный скелет совпадает (`shape()` в ноутбуке → `True`).

---

## Демо-ноутбук

```sh
just install-ml                 # один раз: torch + nbconvert + ipykernel
poetry run jupyter lab notebooks/demo.ipynb   # открыть и Run All
```

Ноутбук сам собирает датасет (гоняет оба frontend'а) и обучает модель; outputs ячеек сохранены.

---

## Структура

| Слой | Файлы |
|---|---|
| Спецификация общего IR | `docs/common-ir.md` |
| Python-слой (читает IR) | `research_ir/ir.py` — AST, `loads`/`dumps`/`shape` |
| Haskell-frontend (GHC API) | `frontends/haskell/` — Core → IR |
| Lean-frontend (метапрограмма) | `frontends/lean/Dump.lean` — Expr → IR |
| Сборка датасета | `ml/build_dataset.py` → `ml/dataset.json` |
| **Обучение перевода** | `ml/train.py` — seq2seq IR → код |
| Демо | `notebooks/demo.ipynb` |
| Тесты | `tests/` |

## Команды (justfile)

```sh
just install        # лёгкая установка (без torch)
just test           # тесты IR + кросс-языковой тест
just build-haskell  # собрать Haskell-frontend
just test-haskell   # golden: реальный GHC Core == зафиксированный IR
just run-lean       # дамп Lean Expr → IR
just install-ml     # полный стек (torch и пр.)
just dataset        # корпус → оба frontend'а → пары (IR, код)
just train          # обучить seq2seq IR → Lean и показать переводы
```

## Требования

GHC 9.6, Lean 4.30, Python ≥3.12, `just`, `poetry`.

---

## Ограничения (PoC) и что дальше

- Корпус — 11 функций над `Nat`, модель переобучается. Это доказательство механизма, не SOTA.
- Рекурсия кодируется по-разному (Haskell — прямой self-call, Lean — `brecOn`); нормализация
  рекурсии — следующий шаг.
- Типы пока сырой атом, не разобраны в `pi`-структуру.
- Дальше: больше корпуса, трансформер вместо GRU (или дообучение CodeT5), вспомогательные
  задачи `код↔IR` как в статье, языки Coq/Arend тем же контрактом.
