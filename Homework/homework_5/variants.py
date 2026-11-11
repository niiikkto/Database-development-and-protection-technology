"""Помощник для таблицы ДЗ-5: считает, сколько резюме проходит все требования
при разных значениях четырёх переменных. Только читает базу hh.

    python3 lesson_05/variants.py

Это проверка для таблицы. Скриншоты и выводы в отчёт берутся из запуска
самого scripts/hh_search.py с изменённой переменной.
"""
import os

from pymongo import MongoClient

resumes = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/"))["hh"]["resumes"]

# Исходные требования из scripts/hh_search.py
BASE = dict(navyki=["Python", "SQL"], gorod="Ярославль", potolok=100000, opyt=6)


def kriterii(navyki, gorod, opyt, potolok=None):
    filtr = {
        "skills": {"$all": navyki},
        "experience": {"$elemMatch": {"months": {"$gte": opyt}}},
        "$or": [{"city": gorod}, {"ready_to_move": True}],
    }
    if potolok is not None:
        filtr["salary"] = {"$lte": potolok}
    return filtr


def podoshli(**izmeneniya):
    p = {**BASE, **izmeneniya}
    filtr = kriterii(p["navyki"], p["gorod"], p["opyt"], p["potolok"])
    return [d["fio"] for d in resumes.find(filtr).sort("salary", 1)]


# По одной переменной, остальные исходные. Значения для примера — подставьте свои.
VARIANTY = [
    ("ничего, исходные требования", {}),
    ("навыки: Python", {"navyki": ["Python"]}),
    ("город: Москва", {"gorod": "Москва"}),
    ("потолок зарплаты: 150000", {"potolok": 150000}),
    ("срок работы: 12 месяцев", {"opyt": 12}),
]

print("| Что изменено | Подошло | Кто |")
print("|---|---|---|")
for nazvanie, izm in VARIANTY:
    kto = podoshli(**izm)
    print(f"| {nazvanie} | {len(kto)} | {', '.join(kto) or '—'} |")

# Минимальный потолок, при котором подходят хотя бы трое.
bez_potolka = list(resumes.find(kriterii(BASE["navyki"], BASE["gorod"], BASE["opyt"])).sort("salary", 1))
print("\nПрошли всё, кроме зарплаты (по возрастанию зарплаты):")
for d in bez_potolka:
    print(f"  {d['fio']:18} {d['salary']:>8}")
if len(bez_potolka) >= 3:
    print(f"\nПотолок для трёх кандидатов: {bez_potolka[2]['salary']}")
else:
    print("\nИ без потолка набирается меньше трёх: смягчать нужно другое требование.")