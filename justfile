# research-ir — единая точка сборки (Python + Haskell + Lean)
# Запуск:  just <recipe>   |   just  (покажет список)

default:
    @just --list

# --- Python ---------------------------------------------------------------

# Лёгкая установка: только dev/test тулинг (без torch/transformers).
install:
    poetry install --only dev

# Полная установка, включая ML-стек.
install-ml:
    poetry install --with dev

# Тесты общего IR / Python-слоя.
test:
    poetry run pytest

# Прогнать произвольную команду в poetry-окружении:  just py -c "..."
py *ARGS:
    poetry run python {{ARGS}}

# --- Frontends ------------------------------------------------------------

hs_dir := "frontends/haskell"

# Собрать Haskell-frontend (GHC Core -> общий IR).
build-haskell:
    cd {{hs_dir}} && cabal build -v0

# Прогнать frontend на примере:  just run-haskell examples/Add.hs
run-haskell file:
    cd {{hs_dir}} && cabal run -v0 core-to-ir -- {{file}}

# Перегенерировать golden-фикстуру add.cir из реального вывода.
gen-haskell: build-haskell
    cd {{hs_dir}} && cabal run -v0 core-to-ir -- examples/Add.hs > ../../fixtures/add.cir
    @echo "regenerated fixtures/add.cir"

# Golden: вывод frontend должен совпасть с зафиксированной фикстурой байт-в-байт.
test-haskell: build-haskell
    cd {{hs_dir}} && cabal run -v0 core-to-ir -- examples/Add.hs | diff - ../../fixtures/add.cir && echo "OK: haskell frontend matches golden"

# Lean-frontend: дамп Expr -> общий IR (без lake, одним файлом).
run-lean:
    cd frontends/lean && lean Dump.lean | grep '^(module'

# Перегенерировать Lean-фикстуру.
gen-lean:
    cd frontends/lean && lean Dump.lean | grep '^(module' > ../../fixtures/lean_inc.cir
    @echo "regenerated fixtures/lean_inc.cir"

# --- ML -------------------------------------------------------------------

# Собрать датасет: корпус -> оба frontend'а -> пары (Haskell-IR, Lean-код).
dataset:
    PYTHONPATH=. poetry run python ml/build_dataset.py

# Обучить baseline char-GRU seq2seq IR -> Lean (нужен ML-стек: just install-ml).
train:
    PYTHONPATH=. poetry run python ml/train.py

# Дообучить предобученный CodeT5-small (сильнее, нужен интернет для весов).
train-t5:
    PYTHONPATH=. poetry run python ml/train_t5.py

# Сгенерировать самодостаточный Kaggle-ноутбук (весь код инлайн, нужен только dataset.json).
kaggle-nb:
    poetry run python ml/make_kaggle_notebook.py
