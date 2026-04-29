from sqlalchemy import text
from db import engine


def run_query(title, sql):
    print(f"\n{'='*50}")
    print(f"[분석] {title}")
    print('='*50)
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        cols = list(result.keys())
        rows = result.fetchall()
    print(" | ".join(cols))
    print('-' * 50)
    for row in rows:
        print(" | ".join(str(v) for v in row))
    return cols, rows


def analyze_all():
    run_query(
        "이벤트 타입별 발생 횟수",
        "SELECT event_type, COUNT(*) AS count FROM events GROUP BY event_type ORDER BY count DESC;"
    )
    run_query(
        "유저별 총 이벤트 수 (Top 10)",
        "SELECT user_id, COUNT(*) AS total_events FROM events GROUP BY user_id ORDER BY total_events DESC LIMIT 10;"
    )
    run_query(
        "시간대별 이벤트 추이",
        "SELECT EXTRACT(HOUR FROM timestamp) AS hour, COUNT(*) AS count FROM events GROUP BY hour ORDER BY hour;"
    )
    run_query(
        "에러 이벤트 비율",
        """
        SELECT event_type, COUNT(*) AS count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
        FROM events GROUP BY event_type ORDER BY count DESC;
        """
    )
