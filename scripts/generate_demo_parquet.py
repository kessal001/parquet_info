from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def build_rows() -> list[dict[str, object]]:
    products = [
        ("A100", "Espresso Blend", "Milan", "ready"),
        ("A120", "Colombia Beans", "Turin", "ready"),
        ("B200", "Cold Brew Kit", "Rome", "backorder"),
        ("C310", "Matcha Tin", "Bologna", "ready"),
        ("D420", "Ceramic Cups", "Naples", "quality_hold"),
        ("E510", "Gift Box", "Florence", "ready"),
    ]
    customers = ["Northwind", "Contoso", "Bluebird", "Tailwind", "Alpine"]
    warehouses = ["WH-MI", "WH-RM", "WH-TO"]
    countries = ["IT", "FR", "DE", "ES", "NL"]
    rows: list[dict[str, object]] = []
    started_at = datetime(2026, 1, 5, 8, 30)

    for index in range(1, 121):
        sku, product_name, city, status = products[(index - 1) % len(products)]
        quantity = ((index * 7) % 90) - (5 if index % 17 == 0 else 0)
        reserved = (index * 3) % 22
        note = None
        if index % 11 == 0:
            note = "priority reorder"
        elif index % 13 == 0:
            note = "damaged box"
        elif index % 19 == 0:
            note = "review supplier"

        rows.append(
            {
                "row_id": index,
                "sku": sku,
                "product_name": product_name,
                "warehouse": warehouses[index % len(warehouses)],
                "city": city,
                "country": countries[index % len(countries)],
                "customer": customers[index % len(customers)],
                "lot": f"{sku}-{(index % 9) + 1:02d}",
                "quantity": quantity,
                "reserved": reserved,
                "net_quantity": quantity - reserved,
                "unit_price": round(4.5 + (index % 8) * 1.35, 2),
                "status": status,
                "is_fragile": sku in {"D420", "E510"},
                "updated_at": started_at + timedelta(hours=index * 6),
                "notes": note,
            }
        )

    return rows


def main() -> None:
    target = Path("examples") / "demo_inventory.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(build_rows())
    pq.write_table(table, target)
    print(f"Wrote {target} with {table.num_rows} rows and {table.num_columns} columns.")


if __name__ == "__main__":
    main()

