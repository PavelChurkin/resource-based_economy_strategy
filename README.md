# resource-based_economy_strategy

Симуляция ресурсно-ориентированной экономики в игровой форме.

Версия `0.01` в этом репозитории начинается с проверяемого Python-ядра:

- нет денег, валюты и рыночных цен, только ресурсы;
- один такт симуляции равен одному игровому дню;
- люди ежедневно потребляют еду и воду, а в холоде требуют тепло;
- здания производят, потребляют и перерабатывают ресурсы через рецепты;
- перенос ресурсов ограничен дневной логистической емкостью людей;
- технология колеса увеличивает логистику после появления досок и круглого
  леса;
- погода влияет на солнечную, ветровую и водную генерацию;
- `fast_forward()` пропускает несколько дней и возвращает статистику
  удовлетворения потребностей;
- управляемый запуск игры идёт через один файл входа:
  `python -m resource_based_economy_strategy`;
- игра завершается при смерти всех жителей или при вводе пользователем `0`;
- генерация стартового мира может учитывать зерно `--seed`.

Подробное описание механик находится в
[`docs/version-0.01-design.md`](docs/version-0.01-design.md).
Планетарный слой, климат, время и дерево технологий описаны в
[`docs/issue-3-design.md`](docs/issue-3-design.md).

## Запуск

Проект не требует внешних Python-зависимостей.

```bash
python -m resource_based_economy_strategy --days 30 --people 6 --seed 42
```

Для автоматического прогона без ожидания ввода:

```bash
python -m resource_based_economy_strategy --days 30 --people 6 --seed 42 --auto
```

Дополнительные демонстрации:

```bash
python examples/run_day_simulation.py
python examples/run_planet_tour.py
python examples/run_time_control.py
```

## Проверка

```bash
python -m unittest discover -s tests
python -m compileall resource_based_economy_strategy examples tests
```
