# Telegram Receipt Parser

Парсер фискальных чеков. Ссылки на чеки теперь хранятся в `link_data.json`.

## Работа со ссылками
- Добавляйте новые ссылки через Telegram‑бота или вручную редактируйте `link_data.json`.
- Для загрузки ссылок в парсер используется функция `utils.load_link_data()`.

## Запуск
```bash
python parser.py
```
Результат сохранится в `Result.xlsx`.
