# Домашнее задание № 2 · модуль 1 справочника и базы курса
 
## Что сделано
 
1. Пройден модуль 1 справочника, главы 1.1–1.8: сервер, база и коллекция; документ и BSON;
   insert_one / insert_many; find и курсор; проекция; sort, limit, skip; обновление
   (`$set`, `$inc`, `$unset`); удаление.
2. Стенд курса поднят в Docker, развернулись четыре базы курса (`shop`, `hh`, `logs`, `org`)
   и песочница `sandbox`.
3. Compass подключён строкой `mongodb://localhost:27017`, число документов сверено с таблицей.
## Как поднят стенд
 
```
git clone https://github.com/MaximBytecamp/mongodb-practice.git
cd mongodb-practice
docker compose up -d
docker compose logs seed
```
 
Сервис `seed` при первом запуске сам загружает двенадцать файлов из `stend/seed`.
Если загрузка не прошла или числа не совпали, данные можно залить заново:
`bash stend/load.sh` (в Windows — `powershell -ExecutionPolicy Bypass -File stend\load.ps1`).
Проверка в Compass: Refresh в списке баз — должно быть восемь баз (пять баз курса и три служебные).
 
## Сколько документов
 
| База   | Должно быть                                           | У меня                                                |
| ------ | ----------------------------------------------------- | ----------------------------------------------------- |
| `shop` | products 21 · orders 120 · customers 20               | products 21 · orders 120 · customers 20               |
| `hh`   | resumes 9 · vacancies 8 · companies 8 · interviews 60 | resumes 9 · vacancies 8 · companies 8 · interviews 60 |
| `logs` | events 1200                                           | events 1200                                           |
| `org`  | employees 15 · categories 10                          | employees 15 · categories 10                          |