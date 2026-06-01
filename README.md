# Paragonka CRM — backend

Backend wielomodułowej platformy SaaS dla małych firm pracujących na zamówienia z konkretnym terminem realizacji. System łączy rejestr klientów, katalog produktów i materiałów, zamówienia, paragony oraz analitykę finansową w jednym środowisku. Dane są izolowane między organizacjami (multi-tenancy).

## Informacje o projekcie dyplomowym

| Pole | Wartość |
|---|---|
| Autor | Savelii Efremov |
| Uczelnia | Uczelnia VIZJA, Wydział Informatyki |
| Kierunek | Informatyka |
| Nr albumu | 40762 |
| Rok | 2026 |
| Promotor | dr inż. Marcin Kacprowicz |

## Zakres backendu

- REST API w FastAPI (71 operacji / 50 ścieżek pod `/api/v1`) z automatyczną dokumentacją OpenAPI/Swagger.
- Opcjonalny interfejs SSR oparty o Jinja2, HTMX, Tailwind CSS i daisyUI.
- Uwierzytelnianie JWT w ciasteczkach `httpOnly` (`access 60 min` / `refresh 30d`), odświeżanie sesji i zarządzanie organizacjami oraz zaproszeniami.
- CRUD klientów z wyszukiwaniem, filtrami, paginacją kursorową (keyset, `limit` domyślnie 50, maks. 200), polami EAV i polami lokalnymi; eksport/import CSV (`/export.csv` + `/import`).
- Produkty typu `good`, `service` i `material`, ceny, koszty, zdjęcia oraz kontrola stanu magazynowego; eksport/import CSV.
- Zamówienia z pozycjami, statusami, terminem realizacji, kalendarzem, rozchodem materiałów oraz polami EAV i zdjęciami; eksport CSV.
- Paragony wprowadzane ręcznie lub importowane z plików JPK_KASA; eksport CSV.
- Analityka finansowa: przychody, wydatki i PnL w ujęciu miesięcznym (`GET /finances/summary`, `months` domyślnie 12, zakres 1–60).
- Przechowywanie zdjęć w magazynie zgodnym z S3 (lokalnie MinIO, PostgreSQL 17, 14 tabel), lokalizacja PL/EN/RU oraz obsługa zgód RODO.

## Technologie

| Obszar | Technologie |
|---|---|
| Język i API | Python 3.13+, FastAPI 0.141.1, Uvicorn 0.52.4 / Granian 2.8.2 |
| Baza danych | PostgreSQL 17, SQLAlchemy 2.0.52 async, asyncpg 0.30+, 14 tabel / 20 FK |
| Migracje | Alembic 1.19.1 |
| Interfejs serwerowy | Jinja2, HTMX, Tailwind CSS, daisyUI |
| Pliki | MinIO / S3, presigned URLs (walidacja magic bytes, 10 MB, 5 zdjęć/encję) |
| Bezpieczeństwo | JWT (access 60 min / refresh 30d), `httpOnly` cookies, bcrypt, walidacja Pydantic |
| Testy i jakość | pytest 9 + httpx + xdist, pytest-asyncio, Ruff, Pyright |
| API | 71 operacji / 50 ścieżek pod `/api/v1` (Swagger `/docs`) |

## Architektura

Kod jest zorganizowany w pionowe moduły funkcjonalne (Vertical Slice Architecture):

```text
app/
├── core/       # konfiguracja, baza danych, bezpieczeństwo, middleware
├── shared/     # wspólne narzędzia, filtrowanie, S3, i18n
└── features/   # auth, orgs, clients, products, orders, receipts, ...
```

Każdy moduł może zawierać modele, schematy Pydantic, repozytorium, serwis oraz router API i web. Logika biznesowa znajduje się w warstwie serwisów, transakcje są zarządzane przez `AppUnitOfWork`, a repozytoria pozostają cienką warstwą dostępu do danych.

### Moduły funkcjonalne

Każdy moduł jest samodzielnym pionowym wycinkiem funkcjonalnym (Vertical Slice Architecture) w katalogu `app/features/<nazwa>/`:

| Moduł | Opis |
|---|---|
| `auth` | JWT autoryzacja: rejestracja, logowanie, refresh, logout, zmiana hasła |
| `users` | Model użytkownika i schematy Pydantic |
| `orgs` | Zarządzanie organizacjami, ustawieniami i zaproszeniami |
| `clients` | CRUD klientów z filtrowaniem, polami EAV i archiwizacją |
| `products` | Ujednolicony model produktu (towar/usługa/materiał), stany magazynowe, zdjęcia |
| `orders` | Zamówienia z pozycjami, statusami, kalendarzem i spisaniem materiałów |
| `receipts` | Paragony ręczne i import JPK_KASA |
| `eav` | Entity-Attribute-Value: własne atrybuty dla klientów, produktów i zamówień |
| `finances` | Analityka finansowa: PnL, przychody, wydatki |
| `media` | Przechowywanie i obsługa zdjęć przez S3 (MinIO) |
| `home` | Strona startowa (landing page) |
| `legal` | Strony prawne i zgody RODO |

## Uruchomienie lokalne

Wymagane są Python 3.13+, Docker z Docker Compose oraz `uv`.

```bash
cd backend
cp .env.example .env
uv sync
docker compose -f docker-compose.local.yml up -d db minio
uv run alembic upgrade head
uv run python run_dev.py
```

Po uruchomieniu:

- aplikacja i web UI: <http://localhost:8000>;
- Swagger: <http://localhost:8000/docs>;
- kontrola zdrowia: `curl http://localhost:8000/health` → `{"status":"OK"}`;
- MinIO API: <http://localhost:9000>, konsola: <http://localhost:9001>.

Plik `.env.example` używa PostgreSQL na `localhost:5432`. Jeżeli frontend działa na `localhost:5173` i korzysta z bezpośredniego adresu API, należy ustawić `CORS_ORIGINS=http://localhost:5173`.

`docker-compose.local.yml` służy w tym scenariuszu do uruchomienia infrastruktury developerskiej (`db` i `minio`). Aplikacja backendowa działa z lokalnego środowiska `uv`, dzięki czemu hot reload i budowanie CSS działają tak samo jak przy bezpośrednim uruchomieniu.

> **Uwaga:** serwis `db` jest budowany z `../db/Dockerfile` (postgres:17 + pg_cron — sprzątanie wygasłych sesji `refresh_sessions` co godzinę, zadanie `purge-refresh-sessions` tworzy migracja Alembic `a4b5c6d7e8f9`). Przy pierwszym uruchomieniu po zmianie obrazu wykonaj `docker compose -f docker-compose.local.yml up -d --build db`, a następnie `uv run alembic upgrade head`.

## Testy i kontrola jakości

```bash
uv run pytest tests/ -v
make check
```

Zebrano **482 testy** (pytest 9 + pytest-xdist, `paragonka_test`): **482 zebrane, 463 passed, 19 skipped, 0 failed — stabilne**. Po poprawce conftest (drop_all przed create_all, retry TRUNCATE) i unikalnych e-mailach w user_org oraz semaforze w teście wyścigu — 3 kolejne przebiegi: 463 passed, 19 skipped, 0 failed. Historycznie: bezpieczeństwo **31 PASS**.

Testy integracyjne wymagają działającego PostgreSQL 17. `make check` uruchamia lintowanie, sprawdzanie typów, testy oraz audyt zależności. Swagger: `/docs` — 71 operacji / 50 ścieżek.

## Liczby projektu

| Metryka | Wartość |
|---|---|
| Python | 3.13+ |
| FastAPI | 0.141.1 |
| PostgreSQL | 17 (14 tabel / 20 FK, pg_cron `purge-refresh-sessions`) |
| JWT | access 60 min / refresh 30d (httpOnly cookies) |
| API | 71 operacji / 50 ścieżek pod `/api/v1` |
| Paginacja | keyset, `limit` domyślnie 50, maks. 200 |
| CSV | `GET /export.csv` + `POST /import` (clients/products/orders/receipts, `FEATURE_CSV`) |
| Finanse | `GET /finances/summary`, `months` domyślnie 12, zakres 1–60 |
| Testy backend | 482 zebrane, 463 passed, 19 skipped, 0 failed — stabilne |
| Migracje | Alembic 1.19.1 |

- Główna dokumentacja projektu: `paragonka-documentation.md`
