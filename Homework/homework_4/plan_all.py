"""Практикум «Онлайн-разбор запроса: explain и индексы».

Скрипт проходит все четыре задачи на базе logs.events и снимает шесть планов:
    plan-1.json, plan-2.json, plan-3a.json, plan-3b.json,
    plan-4-bez.json, plan-4.json
Файлы кладутся рядом со скриптом. В конце печатается сводная таблица.

Запуск (сервер стенда уже поднят, база сброшена командой reset):
    pip install pymongo
    python plan_all.py

Индексы коллекции events скрипт сам удаляет и создаёт; другие базы не трогает.
"""
import os
import sys

from bson import json_util
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
HERE = os.path.dirname(os.path.abspath(__file__))

client = MongoClient(URI, serverSelectionTimeoutMS=3000)
db = client["logs"]
events = db["events"]

# Запрос 1 (задачи 1–3): медленные ошибки платежей, от свежих к старым
FILTER_1 = {"service": "payments", "level": "error", "duration_ms": {"$gt": 500}}
SORT_1 = {"ts": -1}

# Запрос 2 (задача 4): десять самых долгих ошибок
FILTER_2 = {"level": "error"}
SORT_2 = {"duration_ms": -1}
LIMIT_2 = 10

# Индексы
INDEX_ESR = [("service", 1), ("level", 1), ("ts", -1), ("duration_ms", 1)]   # E, S, R
INDEX_A = [("duration_ms", 1), ("service", 1), ("level", 1), ("ts", -1)]     # R, E, S
INDEX_B = [("service", 1), ("level", 1), ("duration_ms", 1), ("ts", -1)]     # E, R, S
INDEX_4 = [("level", 1), ("duration_ms", -1)]                                # E, S


def explain(filt, sort, limit=0):
    """План выполнения find с executionStats — то же, что .explain("executionStats")."""
    find = {"find": events.name, "filter": filt, "sort": sort}
    if limit:
        find["limit"] = limit
    return db.command({"explain": find, "verbosity": "executionStats"})


def steps(plan):
    """Шаги плана снизу вверх: так выполняет сервер (COLLSCAN → SORT)."""
    node = plan["queryPlanner"]["winningPlan"]
    names = []
    while node:
        if "queryPlan" in node:          # план движка SBE хранит дерево внутри queryPlan
            node = node["queryPlan"]
        names.append(node["stage"])
        node = node.get("inputStage")
    return list(reversed(names))


def snimok(file_name, index_label, plan):
    """Сохраняет план в файл и возвращает строку сводной таблицы."""
    path = os.path.join(HERE, file_name)
    with open(path, "w", encoding="utf-8") as f:       # UTF-8 без BOM — сайт такой читает
        f.write(json_util.dumps(plan, ensure_ascii=False, indent=2))
    stats = plan["executionStats"]
    return {
        "file": file_name,
        "index": index_label,
        "returned": stats["nReturned"],
        "docs": stats["totalDocsExamined"],
        "keys": stats["totalKeysExamined"],
        "steps": " → ".join(steps(plan)),
    }


def reset_indexes():
    events.drop_indexes()      # удаляет всё, кроме _id_


def main():
    try:
        client.admin.command("ping")
    except ServerSelectionTimeoutError:
        sys.exit(f"Не удалось подключиться к {URI}: сервер не запущен?")

    total = events.count_documents({})
    print(f"logs.events: {total} документов")
    if total != 1200:
        sys.exit("Ожидалось 1200 документов. Сбросьте базы: docker compose run --rm reset")

    rows = []

    # Задача 1 · без индекса
    reset_indexes()
    print("Запрос 1, результат:", events.count_documents(FILTER_1), "записей")
    rows.append(snimok("plan-1.json", "нет", explain(FILTER_1, SORT_1)))

    # Задача 2 · индекс по ESR
    reset_indexes()
    events.create_index(INDEX_ESR)
    rows.append(snimok("plan-2.json", "service, level, ts, duration_ms",
                       explain(FILTER_1, SORT_1)))

    # Задача 3 · вариант А (R, E, S) и вариант Б (E, R, S)
    reset_indexes()
    events.create_index(INDEX_A)
    rows.append(snimok("plan-3a.json", "duration_ms, service, level, ts",
                       explain(FILTER_1, SORT_1)))

    reset_indexes()
    events.create_index(INDEX_B)
    rows.append(snimok("plan-3b.json", "service, level, duration_ms, ts",
                       explain(FILTER_1, SORT_1)))

    # Задача 4 · второй запрос без индекса и с индексом (E, S)
    reset_indexes()
    print("Запрос 2: всего ошибок в журнале:", events.count_documents(FILTER_2))
    rows.append(snimok("plan-4-bez.json", "нет", explain(FILTER_2, SORT_2, LIMIT_2)))

    events.create_index(INDEX_4)
    rows.append(snimok("plan-4.json", "level, duration_ms (-1)",
                       explain(FILTER_2, SORT_2, LIMIT_2)))

    # Сводная таблица
    print()
    print(f"{'файл':<16}{'индекс':<34}{'вернулось':>10}{'доков':>7}{'ключей':>8}  шаги")
    for r in rows:
        print(f"{r['file']:<16}{r['index']:<34}{r['returned']:>10}"
              f"{r['docs']:>7}{r['keys']:>8}  {r['steps']}")

    # Сверка с ориентирами из практикума
    expected = {
        "plan-1.json": (33, 1200, 0),
        "plan-2.json": (33, 33, 43),
        "plan-3a.json": (33, None, 378),
        "plan-3b.json": (33, None, 33),
        "plan-4-bez.json": (10, 1200, 0),
        "plan-4.json": (10, 10, 10),
    }
    print()
    for r in rows:
        want = expected[r["file"]]
        got = (r["returned"], r["docs"], r["keys"])
        ok = all(w is None or w == g for w, g in zip(want, got))
        print(f"{'✓' if ok else '✗'} {r['file']}: {got}" + ("" if ok else f", ожидалось {want}"))
    print("\nИндексы сейчас:", [ix["name"] for ix in events.list_indexes()])


if __name__ == "__main__":
    main()
