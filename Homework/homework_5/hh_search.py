"""Подбор кандидатов: что умеет язык фильтров из модуля 2.

Скрипт решает прикладную задачу на базе hh: подобрать кандидатов под
требования вакансии, посмотреть, сколько резюме проходит каждое требование
по отдельности, найти подходящие вакансии и проверить данные на пропуски,
неверные типы и несогласованные поля.

    cd scripts
    python3 hh_search.py

    docker compose run --rm python scripts/hh_search.py    # в контейнере
"""

import os
from datetime import datetime

from pymongo import MongoClient

client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/"))
hh = client["hh"]
resumes = hh["resumes"]
vacancies = hh["vacancies"]
interviews = hh["interviews"]


def title(text):
    print("\n" + text)
    print("─" * len(text))


# ── 1. Требования вакансии ────────────────────────────────────────────────
NAVYKI = ["Python", "SQL"]
GOROD = "Ярославль"
POTOLOK = 100000
OPYT_MESYACEV = 6

title("1. Требования")
print(f"  навыки: {' и '.join(NAVYKI)}")
print(f"  город: {GOROD} или готовность к переезду")
print(f"  зарплата: не больше {POTOLOK}")
print(f"  опыт: место работы от {OPYT_MESYACEV} месяцев")

# ── 2. Каждое требование по отдельности ───────────────────────────────────
title("2. Сколько резюме проходит каждое требование")

kriterii = [
    ("навыки $all", {"skills": {"$all": NAVYKI}}),
    ("город или переезд $or", {"$or": [{"city": GOROD}, {"ready_to_move": True}]}),
    ("зарплата $lte", {"salary": {"$lte": POTOLOK}}),
    ("опыт $elemMatch", {"experience": {"$elemMatch": {"months": {"$gte": OPYT_MESYACEV}}}}),
    ("есть контакты $exists", {"contacts": {"$exists": True}}),
]
for nazvanie, filtr in kriterii:
    print(f"  {nazvanie:24} {resumes.count_documents(filtr):2} из {resumes.count_documents({})}")

# ── 3. Все требования сразу ───────────────────────────────────────────────
title("3. Кандидаты, проходящие все требования")

filtr = {
    "skills": {"$all": NAVYKI},
    "salary": {"$lte": POTOLOK},
    "experience": {"$elemMatch": {"months": {"$gte": OPYT_MESYACEV}}},
    "$or": [{"city": GOROD}, {"ready_to_move": True}],
}
print(f"  {'ФИО':18} {'город':16} {'зарплата':>9}  навыки")
for doc in resumes.find(filtr).sort("salary", 1):
    print(f"  {doc['fio']:18} {doc['city']:16} {doc['salary']:>9}  {', '.join(doc['skills'])}")
print(f"  подошло: {resumes.count_documents(filtr)}")

# ── 4. Поиск по части строки ──────────────────────────────────────────────
title("4. Должности, начинающиеся с Junior")

for doc in resumes.find({"position": {"$regex": "^junior", "$options": "i"}},
                        {"_id": 0, "fio": 1, "position": 1}):
    print(f"  {doc['fio']:18} {doc['position']}")

# ── 5. Подходящие вакансии ────────────────────────────────────────────────
title("5. Вакансии под ожидание 90 000")

OZHIDANIE = 90000
vilka = {"salary.from": {"$lte": OZHIDANIE}, "salary.to": {"$gte": OZHIDANIE}}
for doc in vacancies.find(vilka, {"_id": 0, "title": 1, "company": 1, "city": 1, "salary": 1}):
    zarplata = doc["salary"]
    print(f"  {doc['title']:26} {doc['company']:16} {doc['city']:16} "
          f"{zarplata['from']}–{zarplata['to']}")
print(f"  подходит вакансий: {vacancies.count_documents(vilka)}")

# ── 6. Собеседования за неделю ────────────────────────────────────────────
title("6. Собеседования с 21 по 27 сентября")

nedelya = {"when": {"$gte": datetime(2026, 9, 21), "$lt": datetime(2026, 9, 28)}}
print(f"  всего за неделю: {interviews.count_documents(nedelya)}")
for etap in ("скрининг", "техническое", "финальное"):
    print(f"    {etap:12} {interviews.count_documents({**nedelya, 'stage': etap}):2}")
print(f"  очно: {interviews.count_documents({**nedelya, 'format': 'очно'})}, "
      f"видеозвонком: {interviews.count_documents({**nedelya, 'format': 'видеозвонок'})}")

# ── 7. Проверка данных ────────────────────────────────────────────────────
title("7. Проверка данных")

proverki = [
    ("резюме без даты обновления", resumes, {"updated": {"$exists": False}}),
    ("зарплата записана не числом", resumes, {"salary": {"$not": {"$type": "number"}}}),
    ("пустой список мест работы", resumes, {"experience": {"$size": 0}}),
    ("нет ни одного навыка", resumes, {"skills.0": {"$exists": False}}),
    ("перевёрнутая вилка", vacancies, {"$expr": {"$gt": ["$salary.from", "$salary.to"]}}),
    ("вакансия закрыта", vacancies, {"is_open": {"$ne": True}}),
]
for nazvanie, col, filtr in proverki:
    skolko = col.count_documents(filtr)
    print(f"  {nazvanie:30} {skolko:2}" + ("  ← проверить" if skolko else ""))

# ── 8. Кто не подошёл и почему ────────────────────────────────────────────
title("8. Кто не прошёл отбор")

for doc in resumes.find({}, {"_id": 0, "fio": 1, "skills": 1, "salary": 1, "city": 1,
                             "ready_to_move": 1, "experience": 1}):
    prichiny = []
    if not set(NAVYKI) <= set(doc.get("skills", [])):
        prichiny.append("нет навыков")
    if doc["salary"] > POTOLOK:
        prichiny.append("зарплата выше потолка")
    if doc["city"] != GOROD and not doc.get("ready_to_move"):
        prichiny.append("другой город без переезда")
    if not any(m.get("months", 0) >= OPYT_MESYACEV for m in doc.get("experience", [])):
        prichiny.append("мало опыта")
    if prichiny:
        print(f"  {doc['fio']:18} {'; '.join(prichiny)}")

client.close()