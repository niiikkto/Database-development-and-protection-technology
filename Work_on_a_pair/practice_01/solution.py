"""Практическая работа 01 — эталонное решение.

Две прикладные задачи на базе shop/sandbox:
  1. Витрина каталога: страница списка товаров, как её отдаёт бэкенд.
  2. Приёмка поставки: обновить остатки, завести новинки, снять с продажи.

Запуск:
    python3 solution.py                     # сервер на localhost:27017
    MONGO_URI=mongodb://host:27017 python3 solution.py

Перед запуском данные должны быть залиты: bash ../stend/load.sh
"""

import os
from pymongo import MongoClient
from pymongo.errors import BulkWriteError

URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(URI)

products = client["shop"]["products"]      # только читаем
box = client["sandbox"]["products"]        # здесь меняем


# ── Задача 1. Витрина каталога ───────────────────────────────────
def catalog_page(category=None, page=1, per_page=5, sort_field="price", desc=True):
    """Одна страница каталога — то, что бэкенд отдаёт фронтенду.

    Возвращает (items, total): список товаров и сколько их всего под фильтром.
    Число total нужно, чтобы нарисовать «страница 2 из 5».
    """
    query = {}
    if category:
        query["category"] = category

    total = products.count_documents(query)

    cursor = (products
              .find(query, {"_id": 0, "sku": 1, "title": 1, "price": 1, "rating": 1})
              # второй ключ сортировки делает порядок однозначным:
              # без него товары с одинаковой ценой прыгают между страницами
              .sort([(sort_field, -1 if desc else 1), ("sku", 1)])
              .skip((page - 1) * per_page)
              .limit(per_page))

    return list(cursor), total


def show_catalog():
    print("=" * 62)
    print("ЗАДАЧА 1 · витрина каталога")
    print("=" * 62)

    items, total = catalog_page(category="ноутбуки", page=1, per_page=3)
    pages = (total + 2) // 3
    print(f"\nНоутбуки, страница 1 из {pages} (всего {total}):")
    for item in items:
        print(f"  {item['price']:>7} ₽  {item['title']:<32} рейтинг {item['rating']}")

    items, _ = catalog_page(category="ноутбуки", page=2, per_page=3)
    print("\nСтраница 2:")
    for item in items:
        print(f"  {item['price']:>7} ₽  {item['title']:<32} рейтинг {item['rating']}")

    items, total = catalog_page(page=1, per_page=5)
    print(f"\nВесь каталог, топ-5 по цене (всего {total}):")
    for item in items:
        print(f"  {item['price']:>7} ₽  {item['title']}")

    # Пустая страница — обычное дело: запросили дальше, чем есть данных.
    items, total = catalog_page(category="ноутбуки", page=9, per_page=3)
    print(f"\nСтраница 9 из существующих {pages}: найдено {len(items)} товаров, "
          f"total по-прежнему {total}")
    return total


# ── Задача 2. Приёмка поставки ───────────────────────────────────
ARRIVED = {          # что приехало: артикул → сколько штук
    "SKU-NB-001": 5,
    "SKU-PH-006": 12,
    "SKU-PR-010": 3,
}

NEW_ITEMS = [        # новые позиции в каталоге
    {"_id": "p-101", "sku": "SKU-AC-101", "title": "Подставка для ноутбука",
     "brand": "OEM", "category": "аксессуары", "price": 2490, "reviews": 0},
    {"_id": "p-102", "sku": "SKU-AC-102", "title": "Чехол для планшета",
     "brand": "OEM", "category": "аксессуары", "price": 1890, "reviews": 0},
]

DISCONTINUED = ["SKU-CP-018"]   # снято с продажи


def receive_supply():
    print("\n" + "=" * 62)
    print("ЗАДАЧА 2 · приёмка поставки")
    print("=" * 62)

    report = {}

    # 1. Остатки: $inc прибавляет на сервере, не читая значение на клиент.
    #    Если поля qty_total нет — оно появится с этим значением.
    updated = 0
    for sku, qty in ARRIVED.items():
        result = box.update_one({"sku": sku}, {"$inc": {"qty_total": qty}})
        if result.matched_count == 0:
            print(f"  ВНИМАНИЕ: артикул {sku} не найден в каталоге")
        updated += result.modified_count
    report["остатки обновлены"] = updated

    # 2. Новинки: свой _id делает повторный запуск безопасным —
    #    вторая попытка упрётся в E11000, а не создаст дубли.
    try:
        result = box.insert_many(NEW_ITEMS, ordered=False)
        report["новых позиций"] = len(result.inserted_ids)
    except BulkWriteError as error:
        already = len(error.details["writeErrors"])
        report["новых позиций"] = len(NEW_ITEMS) - already
        print(f"  {already} позиций уже были в каталоге — пропущены")

    # 3. Снятие с продажи: сначала считаем, потом удаляем.
    query = {"sku": {"$in": DISCONTINUED}}
    to_remove = box.count_documents(query)
    print(f"\n  под снятие с продажи попало: {to_remove}")
    for doc in box.find(query, {"_id": 1, "title": 1, "price": 1}):
        print(f"    {doc}")
    report["снято с продажи"] = box.delete_many(query).deleted_count

    # 4. Бесплатная доставка для всей категории — одним запросом.
    query = {"category": "аксессуары"}
    print(f"\n  бесплатная доставка коснётся: {box.count_documents(query)} товаров")
    result = box.update_many(query, {"$set": {"free_shipping": True}})
    report["бесплатная доставка"] = result.modified_count

    report["итого в каталоге"] = box.count_documents({})

    print("\nОтчёт о приёмке:")
    for name, value in report.items():
        print(f"  {name:<24} {value}")
    return report


if __name__ == "__main__":
    show_catalog()
    receive_supply()
    client.close()
