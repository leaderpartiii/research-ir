# Common IR — спецификация

Общий промежуточный язык, в который **нормализуются нативные IR** функциональных языков
(GHC Core для Haskell, `Expr` для Lean; позже Coq/Arend). Это **символьное** представление
(текст, не нейросеть). Кодировка — S-выражения.

Граница контракта:
- frontends (Haskell, Lean) — **пишут** этот формат;
- Python-слой — **читает** его (для токенизации / графа / ML).

## Грамматика

```
Module  ::= (module <Def>...)
Def     ::= (def <name> <Term> <Term>)          ; name  type  body

Term    ::= (var   <name>)                       ; локальная переменная
          | (const <name>)                       ; глобальная ссылка
          | (lit   <value> <kind>)               ; литерал, kind ∈ {nat,int,str,...}
          | (app   <Term> <Term>)                ; применение (каррированное)
          | (lam   (<name> <Term>) <Term>)       ; λ (x : T) . body
          | (pi    (<name> <Term>) <Term>)       ; Π (x : T) . body  / тип-функция, ∀
          | (let   (<name> <Term> <Term>) <Term>); let (x : T = v) in body
          | (case  <Term> <Alt>...)              ; разбор по образцу
          | (con   <name> (<Term>...))           ; применённый конструктор
          | (sort  <name>)                       ; Type / Prop / вселенная

Alt     ::= (alt <Pattern> <Term>)
Pattern ::= (pcon <name> (<name>...))            ; C x1 ... xn
          | (plit <value> <kind>)
          | (pwild)                              ; _
```

Один синтаксический класс `Term` и для значений, и для типов — так как языки зависимо
типизированы (для Lean это обязательно; для Haskell System FC это тоже корректно).

## Инварианты

- Весь синтаксический сахар снят на стороне frontend (do-нотация, list-comprehensions,
  операторы → `app`/`const`, where → `let`, и т.п.).
- Имена связанных переменных сохраняются как есть (alpha-эквивалентность — забота downstream).
- Round-trip: `parse(text)` и затем `dumps(...)` дают семантически тот же терм.

## Пример: factorial

См. `fixtures/factorial.cir` — эталон, который должны независимо породить и Haskell-, и
Lean-frontend (с точностью до имён). Совпадение их выходов — главный sanity-тест PoC.
