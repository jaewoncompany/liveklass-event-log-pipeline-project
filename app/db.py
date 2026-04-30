import os
import json
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from psycopg2 import connect as pg_connect

BATCH_SIZE = int(os.getenv("BATCH_SIZE", 100))

def _creator():
    return pg_connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

engine = create_engine(
    "postgresql+psycopg2://",
    creator=_creator,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=2,
    pool_pre_ping=True,
)


def save_raw(events: list[dict]):
    rows = [{"payload": json.dumps(e)} for e in events]
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO raw_events (payload) VALUES (:payload)"),
            rows,
        )


def get_checkpoint() -> int:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT last_raw_id FROM etl_checkpoint WHERE id = 1"))
        return result.scalar()


def update_checkpoint(last_raw_id: int):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE etl_checkpoint SET last_raw_id = :id, updated_at = now() WHERE id = 1"),
            {"id": last_raw_id},
        )


def transform_chunk(from_id: int, to_id: int):
    sql = text("""
        INSERT INTO events (
            raw_id, event_id, event_type, user_id, session_id, timestamp,
            ip_address, user_agent, page, referrer,
            duration_ms, error_code, product_id, amount
        )
        SELECT
            id,
            (payload->>'event_id')::uuid,
            payload->>'event_type',
            payload->>'user_id',
            (payload->>'session_id')::uuid,
            (payload->>'timestamp')::timestamptz,
            (payload->>'ip_address')::inet,
            payload->>'user_agent',
            payload->>'page',
            payload->>'referrer',
            (payload->>'duration_ms')::integer,
            (payload->>'error_code')::smallint,
            payload->>'product_id',
            (payload->>'amount')::numeric
        FROM raw_events
        WHERE id > :from_id AND id <= :to_id
        ON CONFLICT DO NOTHING;
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"from_id": from_id, "to_id": to_id})


def run_micro_batch():
    last_id = get_checkpoint()

    with engine.connect() as conn:
        max_id = conn.execute(text("SELECT MAX(id) FROM raw_events")).scalar()

    if not max_id or max_id <= last_id:
        print("[batch] No new events to process.")
        return

    total = 0
    current = last_id
    while current < max_id:
        next_id = min(current + BATCH_SIZE, max_id)
        transform_chunk(current, next_id)
        update_checkpoint(next_id)
        total += next_id - current
        print(f"[batch] {current+1}~{next_id} done")
        current = next_id

    print(f"[batch] {total} events transformed.")
