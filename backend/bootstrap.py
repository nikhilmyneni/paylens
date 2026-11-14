"""Migrate, then optionally initialize a completely empty synthetic demo."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session
from db import DATABASE_URL, engine, initialize_database
from models import Employee


def bootstrap(seed=False, scale="starter", output="/tmp/compass-seed"):
    initialize_database(engine)
    with Session(engine) as session:
        populated = bool(session.scalar(select(func.count()).select_from(Employee)))
    if not seed or populated:
        print("Schema current; existing data preserved." if populated else "Schema current; no seed requested.")
        return
    if os.getenv("DEMO_MODE", "true").lower() != "true":
        raise RuntimeError("Automatic synthetic seeding requires DEMO_MODE=true")
    # Never insert a baseline into a partially populated master-data database.
    with engine.connect() as connection:
        for table in inspect(engine).get_table_names():
            if table == "alembic_version":
                continue
            count = connection.exec_driver_sql(f'SELECT COUNT(*) FROM "{table}"').scalar()
            if count:
                raise RuntimeError(f"Refusing seed: {table} contains data; use a fresh database")
    subprocess.run([sys.executable, str(Path(__file__).with_name("generate.py")), "--scale", scale,
                    "--database-url", DATABASE_URL, "--output", output], check=True)
    print("Synthetic dataset initialized; subsequent starts preserve it.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--scale", choices=("starter", "full"), default="starter")
    parser.add_argument("--output", default="../data/generated/starter")
    args = parser.parse_args()
    bootstrap(args.seed, args.scale, args.output)
