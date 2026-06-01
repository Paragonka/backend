"""Seed demo data for sovwva7@gmail.com's organization.

Usage: uv run python scripts/seed_demo.py
"""

import asyncio
import random
import uuid
from datetime import date, timedelta

import asyncpg
from uuid_extensions import uuid7

ORG_ID = "06a912c0-efba-7abc-8000-fc4f9a427d3e"
DB_URL = "postgresql://user:password@db:5432/paragonka_db"

rng = random.Random(42)  # noqa: S311 - детерминированный PRNG для воспроизводимых демо-данных

N_CLIENTS = 250
N_PRODUCTS = 300
N_ORDERS = 200


def u() -> str:
    return str(uuid7())


# ── Polish names ─────────────────────────────────────────────────────────────
FIRST_NAMES = [
    "Anna",
    "Piotr",
    "Maria",
    "Tomasz",
    "Katarzyna",
    "Marek",
    "Ewa",
    "Krzysztof",
    "Agnieszka",
    "Paweł",
    "Magdalena",
    "Jan",
    "Joanna",
    "Andrzej",
    "Barbara",
    "Michał",
    "Klaudia",
    "Łukasz",
    "Dorota",
    "Wojciech",
    "Monika",
    "Jakub",
    "Beata",
    "Adam",
    "Karolina",
    "Marcin",
    "Aleksandra",
    "Grzegorz",
    "Iwona",
    "Dariusz",
    "Patrycja",
    "Rafał",
    "Elżbieta",
    "Sebastian",
    "Małgorzata",
    "Bartosz",
    "Natalia",
    "Damian",
    "Kinga",
    "Kamil",
    "Ola",
    "Szymon",
    "Julia",
    "Filip",
    "Paulina",
    "Mikołaj",
    "Zuzanna",
    "Hubert",
    "Weronika",
    "Igor",
    "Nina",
    "Oskar",
    "Lena",
    "Antoni",
    "Amelia",
    "Wiktor",
    "Maja",
    "Leon",
    "Hanna",
    "Stanisław",
    "Zofia",
    "Franciszek",
    "Laura",
    "Aleksander",
    "Emilia",
    "Tymoteusz",
    "Michalina",
    "Ignacy",
    "Gabriela",
    "Janusz",
    "Renata",
    "Władysław",
    "Bożena",
    "Czesław",
    "Danuta",
    "Edward",
    "Feliks",
    "Genowefa",
    "Halina",
    "Irena",
    "Jerzy",
    "Kazimierz",
    "Lucyna",
    "Mirosław",
    "Nadzieja",
    "Olga",
    "Roman",
    "Sabina",
    "Tadeusz",
    "Urszula",
    "Wacław",
    "Zbigniew",
    "Adrian",
    "Blanka",
    "Cyprian",
    "Dagmara",
    "Eryk",
    "Faustyna",
]

SURNAMES = [
    "Kowalski",
    "Nowak",
    "Wiśniewski",
    "Wójcik",
    "Kowalczyk",
    "Kamiński",
    "Lewandowski",
    "Zieliński",
    "Szymański",
    "Woźniak",
    "Dąbrowski",
    "Kozłowski",
    "Jankowski",
    "Mazur",
    "Kwiatkowski",
    "Krawczyk",
    "Piotrowski",
    "Grabowski",
    "Nowakowski",
    "Pawłowski",
    "Michalski",
    "Nowicki",
    "Adamczyk",
    "Dudek",
    "Zając",
    "Wieczorek",
    "Jabłoński",
    "Król",
    "Majewski",
    "Olszewski",
    "Stępień",
    "Jaworski",
    "Malinowski",
    "Pawlak",
    "Witkowski",
    "Walczak",
    "Sikora",
    "Rutkowski",
    "Michalak",
    "Szewczyk",
    "Ostrowski",
    "Baran",
    "Tomaszewski",
    "Zalewski",
    "Wróbel",
    "Pietrzak",
    "Marciniak",
    "Wypych",
    "Sadowski",
    "Gajewski",
    "Wesołowski",
    "Włodarczyk",
    "Bąk",
    "Chmielewski",
    "Czarnecki",
    "Dudzic",
    "Górski",
    "Hoffman",
    "Jasiński",
    "Kaczmarek",
    "Lis",
    "Maciejewski",
    "Nawrocki",
    "Orłowski",
    "Piasecki",
    "Rogowski",
    "Sawicki",
    "Sokołowski",
    "Urbaniak",
    "Wasilewski",
    "Zawadzki",
    "Bielecki",
    "Cieślak",
    "Domański",
    "Grabarczyk",
    "Idzikowski",
    "Jędrzejewski",
    "Kalinowski",
    "Laskowski",
    "Matuszewski",
    "Niedzielski",
    "Osiński",
    "Pająk",
    "Ratajczak",
    "Sobczak",
    "Sowiński",
    "Twardowski",
    "Urbański",
    "Wierzbicki",
    "Zakrzewski",
    "Żurawski",
    "Baranowski",
    "Czajkowski",
    "Dębicki",
    "Falkowski",
    "Głowacki",
    "Krajewski",
    "Lipiński",
    "Musiał",
    "Olejniczak",
    "Przybylski",
    "Różycki",
    "Skrzypek",
    "Sroczyński",
]

NOTES = [
    "",
    "",
    "",
    "",
    "Stała klientka, lubi croissanty",
    "Zamawia co piątek",
    "Duże zamówienia na imprezy",
    "Preferuje bezglutenowe",
    "Firma Zielona Kawa",
    "Wegańska, pyta o roślinne mleko",
    "Organizuje wesela",
    "Nowy klient",
    "Zaleca się dzwonić przed dostawą",
    "Płatność gotówką",
    "Płatność przelewem",
    "Lubi kawę z mlekiem owsianym",
    "Zamawia torty urodzinowe",
    "Odbiór osobisty",
    "Współpraca od 2025",
    "Częste zamówienia hurtowe",
]


def gen_phone() -> str:
    prefix = rng.choice(
        [
            "501",
            "502",
            "503",
            "504",
            "505",
            "506",
            "507",
            "508",
            "509",
            "510",
            "511",
            "512",
        ]
    )

    return f"+48 {prefix} {rng.randint(100, 999)} {rng.randint(100, 999)}"


# ── Products ─────────────────────────────────────────────────────────────────
PRODUCT_TEMPLATES = [
    # (name, category, unit, product_type, min_price, max_price, min_cost, max_cost)
    ("Croissant", "Ciastka", "szt", "good", 10, 16, 3, 6),
    ("Croissant z czekoladą", "Ciastka", "szt", "good", 12, 18, 4, 7),
    ("Croissant migdałowy", "Ciastka", "szt", "good", 13, 18, 4, 7),
    ("Muffin borówkowy", "Ciastka", "szt", "good", 8, 12, 2.5, 5),
    ("Muffin czekoladowy", "Ciastka", "szt", "good", 8, 12, 2.5, 5),
    ("Ciasto marchewkowe (kawałek)", "Ciastka", "szt", "good", 9, 14, 3, 6),
    ("Sernik (kawałek)", "Ciastka", "szt", "good", 11, 16, 4, 7),
    ("Pączek z marmoladą", "Ciastka", "szt", "good", 5, 8, 1.5, 3),
    ("Pączek z kremem", "Ciastka", "szt", "good", 6, 9, 2, 3.5),
    ("Babeczka waniliowa", "Ciastka", "szt", "good", 7, 11, 2, 4),
    ("Ciasteczka owsiane", "Ciastka", "szt", "good", 6, 10, 1.5, 4),
    ("Beza z owocami", "Ciastka", "szt", "good", 10, 15, 3.5, 6),
    ("Bagietka", "Pieczywo", "szt", "good", 6, 10, 1.5, 3.5),
    ("Bagietka z masłem czosnkowym", "Pieczywo", "szt", "good", 8, 13, 2.5, 5),
    ("Chleb żytni", "Pieczywo", "szt", "good", 12, 18, 4.5, 8),
    ("Chleb pszenny", "Pieczywo", "szt", "good", 10, 15, 3.5, 6.5),
    ("Chleb orkiszowy", "Pieczywo", "szt", "good", 14, 20, 5, 9),
    ("Bułka maślana", "Pieczywo", "szt", "good", 4, 7, 1, 2.5),
    ("Bułka sezamowa", "Pieczywo", "szt", "good", 5, 8, 1.2, 3),
    ("Bułka grahamka", "Pieczywo", "szt", "good", 4, 7, 1, 2.5),
    ("Rogal maślany", "Pieczywo", "szt", "good", 5, 9, 1.5, 3.5),
    ("Paluch z makiem", "Pieczywo", "szt", "good", 6, 10, 2, 4),
    ("Focaccia z rozmarynem", "Pieczywo", "szt", "good", 15, 22, 5, 9),
    ("Ciabatta", "Pieczywo", "szt", "good", 8, 12, 2.5, 5),
    ("Kawa espresso", "Napoje", "szt", "good", 8, 12, 1.5, 3),
    ("Kawa americano", "Napoje", "szt", "good", 9, 13, 1.8, 3.5),
    ("Kawa latte", "Napoje", "szt", "good", 12, 17, 2.5, 5),
    ("Kawa latte waniliowa", "Napoje", "szt", "good", 13, 18, 3, 5.5),
    ("Cappuccino", "Napoje", "szt", "good", 12, 16, 2.5, 5),
    ("Flat white", "Napoje", "szt", "good", 12, 17, 2.5, 5),
    ("Espresso podwójne", "Napoje", "szt", "good", 10, 14, 2, 4),
    ("Kawa mrożona", "Napoje", "szt", "good", 14, 19, 3.5, 7),
    ("Herbata czarna", "Napoje", "szt", "good", 7, 10, 1, 2.5),
    ("Herbata zielona", "Napoje", "szt", "good", 7, 10, 1, 2.5),
    ("Herbata owocowa", "Napoje", "szt", "good", 8, 11, 1.2, 3),
    ("Kakao", "Napoje", "szt", "good", 10, 14, 2.5, 5),
    ("Sok pomarańczowy świeży", "Napoje", "szt", "good", 10, 15, 3, 6),
    ("Sok jabłkowy świeży", "Napoje", "szt", "good", 9, 14, 2.5, 5.5),
    ("Lemoniada domowa", "Napoje", "szt", "good", 11, 16, 3, 6),
    ("Woda mineralna", "Napoje", "szt", "good", 4, 6, 1, 2),
    ("Tort czekoladowy (cały)", "Torty", "szt", "good", 110, 160, 30, 50),
    ("Tort waniliowy (cały)", "Torty", "szt", "good", 100, 150, 28, 45),
    ("Tort malinowy (cały)", "Torty", "szt", "good", 120, 170, 35, 55),
    ("Tort orzechowy (cały)", "Torty", "szt", "good", 115, 165, 32, 52),
    ("Tort bezowy (cały)", "Torty", "szt", "good", 130, 180, 38, 58),
    ("Tort wegański (cały)", "Torty", "szt", "good", 125, 175, 36, 56),
    ("Tort śmietankowo-owocowy (cały)", "Torty", "szt", "good", 105, 155, 30, 48),
    ("Tort kawowy (cały)", "Torty", "szt", "good", 120, 170, 34, 54),
    ("Tiramisu (porcja)", "Desery", "szt", "good", 14, 19, 4, 7),
    ("Panna cotta (porcja)", "Desery", "szt", "good", 13, 18, 3.5, 6.5),
    ("Lody rzemieślnicze (gałka)", "Desery", "szt", "good", 6, 9, 1.5, 3.5),
    ("Sorbet owocowy (porcja)", "Desery", "szt", "good", 9, 13, 2.5, 5),
    ("Creme brulee (porcja)", "Desery", "szt", "good", 15, 20, 4.5, 8),
    ("Brownie z orzechami (kawałek)", "Desery", "szt", "good", 11, 15, 3.5, 6),
    ("Ciasteczka z białą czekoladą", "Desery", "szt", "good", 7, 11, 2, 4.5),
    ("Tarta cytrynowa (porcja)", "Desery", "szt", "good", 12, 17, 3.5, 6),
    ("Tarta jabłkowa (porcja)", "Desery", "szt", "good", 11, 15, 3, 5.5),
    ("Sałatka z kurczakiem", "Lunch", "szt", "good", 18, 26, 7, 12),
    ("Sałatka grecka", "Lunch", "szt", "good", 16, 22, 6, 10),
    ("Zupa dnia (porcja)", "Lunch", "szt", "good", 12, 17, 4, 8),
    ("Zupa krem z dyni (porcja)", "Lunch", "szt", "good", 13, 18, 4.5, 8.5),
    ("Kanapka z szynką i serem", "Lunch", "szt", "good", 14, 19, 5, 9),
    ("Kanapka wege z hummusem", "Lunch", "szt", "good", 13, 18, 5, 8.5),
    ("Panini z mozzarellą", "Lunch", "szt", "good", 17, 23, 6.5, 11),
    ("Wrap z łososiem", "Lunch", "szt", "good", 19, 26, 7.5, 12),
    ("Zapiekanka polska", "Lunch", "szt", "good", 15, 20, 5.5, 9.5),
    ("Deska serów (2 os.)", "Lunch", "szt", "good", 32, 45, 14, 22),
    ("Deska wędlin (2 os.)", "Lunch", "szt", "good", 30, 42, 13, 20),
    ("Zestaw śniadaniowy", "Lunch", "szt", "good", 24, 32, 9, 15),
    ("Owsianka z owocami", "Lunch", "szt", "good", 13, 18, 4, 8),
    ("Jajecznica na maśle", "Lunch", "szt", "good", 16, 22, 6, 10),
    ("Sernik na zimno (porcja)", "Lunch", "szt", "good", 12, 16, 3.5, 7),
    ("Catering śniadaniowy (os.)", "Catering", "os", "service", 25, 45, 12, 25),
    ("Catering lunchowy (os.)", "Catering", "os", "service", 35, 60, 18, 32),
    ("Catering kawowy (os.)", "Catering", "os", "service", 20, 35, 10, 20),
    ("Tort na zamówienie (kg)", "Catering", "kg", "service", 60, 90, 25, 45),
    ("Koszyk upominkowy", "Catering", "szt", "service", 45, 80, 20, 45),
    ("Obsługa eventu (godz.)", "Catering", "godz", "service", 50, 80, 25, 50),
    ("Dekoracja stołu", "Catering", "szt", "service", 30, 55, 12, 30),
    ("Dostawa (strefa 1)", "Catering", "szt", "service", 15, 25, 5, 12),
    ("Dostawa (strefa 2)", "Catering", "szt", "service", 25, 40, 10, 20),
    ("Mąka pszenna (kg)", "Składniki", "kg", "material", 3, 6, 1, 2.5),
    ("Mąka żytnia (kg)", "Składniki", "kg", "material", 4, 7, 1.5, 3),
    ("Masło (200 g)", "Składniki", "szt", "material", 8, 13, 4, 7),
    ("Jajka (10 szt)", "Składniki", "szt", "material", 9, 14, 4.5, 8),
    ("Cukier (kg)", "Składniki", "kg", "material", 4, 7, 1.5, 3),
    ("Mleko (1 l)", "Składniki", "szt", "material", 4, 7, 1.8, 3.5),
    ("Śmietana 36% (500 ml)", "Składniki", "szt", "material", 8, 13, 4, 7),
    ("Czekolada deserowa (kg)", "Składniki", "kg", "material", 25, 40, 14, 24),
    ("Drożdże (kg)", "Składniki", "kg", "material", 15, 25, 8, 14),
    ("Sól morska (kg)", "Składniki", "kg", "material", 5, 9, 2, 4.5),
    ("Oliwa z oliwek (500 ml)", "Składniki", "szt", "material", 18, 28, 10, 17),
    ("Ziarna kawy arabica (kg)", "Składniki", "kg", "material", 55, 90, 30, 55),
    ("Migdały (kg)", "Składniki", "kg", "material", 35, 55, 20, 35),
    ("Orzechy włoskie (kg)", "Składniki", "kg", "material", 30, 48, 17, 30),
    ("Miód (500 g)", "Składniki", "szt", "material", 18, 28, 10, 17),
    ("Truskawki świeże (kg)", "Składniki", "kg", "material", 15, 28, 8, 16),
    ("Maliny świeże (kg)", "Składniki", "kg", "material", 25, 45, 15, 28),
    ("Jabłka (kg)", "Składniki", "kg", "material", 4, 8, 1.5, 4),
    ("Cytryny (kg)", "Składniki", "kg", "material", 8, 14, 4, 8),
    ("Ser mascarpone (250 g)", "Składniki", "szt", "material", 9, 14, 5, 8),
]

STATUSES = [
    ("draft", 40),
    ("confirmed", 15),
    ("done", 35),
    ("cancelled", 10),
]

UNITS = {"szt", "os", "kg", "godz"}


def weighted_status() -> str:
    r = rng.random() * 100
    acc = 0

    for status, weight in STATUSES:
        acc += weight

        if r <= acc:
            return status

    return "draft"


async def seed() -> None:
    conn = await asyncpg.connect(DB_URL)

    try:
        # ── Clear old data ────────────────────────────────────────────────────
        await conn.execute(
            "DELETE FROM order_items WHERE order_id IN "
            "(SELECT id FROM orders WHERE org_id = $1)",
            ORG_ID,
        )
        await conn.execute("DELETE FROM write_offs WHERE org_id = $1", ORG_ID)
        await conn.execute("DELETE FROM orders WHERE org_id = $1", ORG_ID)
        await conn.execute("DELETE FROM receipts WHERE org_id = $1", ORG_ID)
        await conn.execute("DELETE FROM products WHERE org_id = $1", ORG_ID)
        await conn.execute("DELETE FROM clients WHERE org_id = $1", ORG_ID)

        # ── Clients ───────────────────────────────────────────────────────────
        client_ids = []
        phones = set()

        for _ in range(N_CLIENTS):
            cid = u()
            client_ids.append(cid)
            name = rng.choice(FIRST_NAMES)
            surname = rng.choice(SURNAMES)
            phone = gen_phone()

            while phone in phones:
                phone = gen_phone()

            phones.add(phone)
            notes = rng.choice(NOTES)
            await conn.execute(
                """
                INSERT INTO clients (
                    id, org_id, name, surname, phone, notes,
                    custom_fields, local_fields, created_at, updated_at
                )
                VALUES ($1,$2,$3,$4,$5,$6,'{}','{}',now(),now())
                """,
                uuid.UUID(cid),
                ORG_ID,
                name,
                surname,
                phone,
                notes,
            )

        print(f"✓ Clients: {N_CLIENTS}")

        # ── Products ──────────────────────────────────────────────────────────
        product_ids = []
        product_names = {}
        products = []
        pi = 0

        while pi < N_PRODUCTS:
            name, cat, unit, ptype, lo_p, hi_p, lo_c, hi_c = rng.choice(
                PRODUCT_TEMPLATES
            )

            if pi % 3 == 1:
                name = f"{name} (duży)"
            elif pi % 3 == 2:
                name = f"{name} (premium)"

            if name in products:
                continue

            products.append(name)
            pid = u()
            product_ids.append(pid)
            product_names[pid] = name
            price = rng.randint(int(lo_p), int(hi_p)) + rng.choice([0, 0.5, 0.9])
            cost = rng.randint(int(lo_c), int(hi_c)) + rng.choice([0, 0.5])
            stock = rng.randint(0, 500) if ptype == "good" and unit != "os" else None
            track = ptype in ("good", "material") and stock is not None
            is_sellable = ptype != "material"
            await conn.execute(
                """
                INSERT INTO products (
                    id, org_id, name, category, unit, product_type,
                    price, cost_price, stock_qty, track_inventory,
                    is_sellable, is_active, custom_fields, photos,
                    local_fields, created_at, updated_at
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,
                        true,'{}','[]','{}',now(),now())
                """,
                uuid.UUID(pid),
                ORG_ID,
                name,
                cat,
                unit,
                ptype,
                str(price),
                str(cost),
                stock,
                track,
                is_sellable,
            )
            pi += 1

        print(f"✓ Products: {N_PRODUCTS}")

        # ── Orders + items ────────────────────────────────────────────────────
        start = date(2026, 6, 1)
        end = date(2026, 8, 19)
        day_range = (end - start).days
        order_ids = []

        for _ in range(N_ORDERS):
            oid = u()
            order_ids.append(oid)
            client_id = uuid.UUID(rng.choice(client_ids))
            status = weighted_status()
            exec_date = (start + timedelta(days=rng.randint(0, day_range))).isoformat()
            notes = rng.choice(
                [
                    "",
                    "",
                    "",
                    "",
                    "Zamówienie hurtowe",
                    "Odbiór osobisty",
                    "Dostawa rano",
                ]
            )
            await conn.execute(
                """
                INSERT INTO orders (id, org_id, client_id, status, total,
                                    execution_date, notes, photos, local_fields,
                                    created_at, updated_at)
                VALUES ($1,$2,$3,$4,0,$5,$6,'[]','{}',now(),now())
                """,
                uuid.UUID(oid),
                ORG_ID,
                client_id,
                status,
                exec_date,
                notes,
            )

            n_items = rng.randint(1, 8)
            chosen = rng.sample(product_ids, k=min(n_items, len(product_ids)))
            total = 0

            for pid in chosen:
                iid = u()
                prod_id = uuid.UUID(pid)
                qty = rng.choice([1, 1, 1, 2, 2, 3, 5, 8, 10, 12])
                price = rng.randint(2, 60) + rng.choice([0, 0.5, 0.9])
                total += price * qty
                await conn.execute(
                    """
                    INSERT INTO order_items (id, order_id, product_id, name, price, qty,
                                             created_at, updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,now(),now())
                    """,
                    uuid.UUID(iid),
                    uuid.UUID(oid),
                    prod_id,
                    product_names[pid],
                    str(price),
                    str(qty),
                )

            await conn.execute(
                "UPDATE orders SET total = $1 WHERE id = $2",
                str(round(total, 2)),
                uuid.UUID(oid),
            )

        print(f"✓ Orders: {N_ORDERS}")

        # ── Summary ───────────────────────────────────────────────────────────
        for tbl in ("clients", "products", "orders"):
            cnt = await conn.fetchval(
                f"SELECT count(*) FROM {tbl} WHERE org_id=$1",  # noqa: S608 - tbl из фиксированного whitelist-кортежа
                ORG_ID,
            )
            print(f"  {tbl}: {cnt}")

        cnt = await conn.fetchval(
            "SELECT count(*) FROM order_items oi "
            "JOIN orders o ON o.id = oi.order_id WHERE o.org_id=$1",
            ORG_ID,
        )
        print(f"  order_items: {cnt}")

        orphan_orders = await conn.fetchval(
            "SELECT count(*) FROM orders WHERE org_id=$1 AND client_id IS NULL", ORG_ID
        )
        orphan_items = await conn.fetchval(
            "SELECT count(*) FROM order_items oi JOIN orders o ON o.id = oi.order_id "
            "WHERE o.org_id=$1 AND oi.product_id IS NULL",
            ORG_ID,
        )
        print(f"  orders without client: {orphan_orders}")
        print(f"  items without product: {orphan_items}")

        print("\n✓ Done!")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
