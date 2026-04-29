import time
from generator import generate_events
from db import save_raw, run_micro_batch
from analyze import analyze_all
from visualize import plot_event_type_count, plot_hourly_trend, plot_error_ratio, plot_top_users


def wait_for_db(retries=10, delay=3):
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    from db import engine
    for i in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[main] DB connected.")
            return
        except OperationalError:
            print(f"[main] Waiting for DB... ({i+1}/{retries})")
            time.sleep(delay)
    raise RuntimeError("Could not connect to DB after retries.")


if __name__ == "__main__":
    wait_for_db()

    events = generate_events()
    print(f"[main] {len(events)} events generated.")

    save_raw(events)
    run_micro_batch()
    analyze_all()

    plot_event_type_count()
    plot_hourly_trend()
    plot_error_ratio()
    plot_top_users()
    print("[main] charts saved.")

    print("[main] Done.")
