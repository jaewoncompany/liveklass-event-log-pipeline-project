import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sqlalchemy import text
from db import engine

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def fetch(sql):
    with engine.connect() as conn:
        return conn.execute(text(sql)).fetchall()


def plot_event_type_count():
    rows = fetch("SELECT event_type, COUNT(*) FROM events GROUP BY event_type ORDER BY COUNT(*) DESC;")
    labels, values = zip(*rows)
    fig, ax = plt.subplots()
    ax.bar(labels, values, color="steelblue")
    ax.set_title("Event Count by Type")
    ax.set_xlabel("Event Type")
    ax.set_ylabel("Count")
    fig.tight_layout()
    fig.savefig(f"{OUTPUT_DIR}/event_type_count.png")
    plt.close(fig)


def plot_hourly_trend():
    rows = fetch("SELECT EXTRACT(HOUR FROM timestamp)::int AS hour, COUNT(*) FROM events GROUP BY hour ORDER BY hour;")
    hours, counts = zip(*rows)
    fig, ax = plt.subplots()
    ax.plot(hours, counts, marker="o", color="tomato")
    ax.set_title("Hourly Event Trend")
    ax.set_xlabel("Hour (UTC)")
    ax.set_ylabel("Count")
    ax.set_xticks(range(0, 24))
    fig.tight_layout()
    fig.savefig(f"{OUTPUT_DIR}/hourly_trend.png")
    plt.close(fig)


def plot_error_ratio():
    rows = fetch("SELECT event_type, COUNT(*) FROM events GROUP BY event_type ORDER BY COUNT(*) DESC;")
    labels, values = zip(*rows)
    fig, ax = plt.subplots()
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=140)
    ax.set_title("Event Type Distribution")
    fig.tight_layout()
    fig.savefig(f"{OUTPUT_DIR}/event_distribution.png")
    plt.close(fig)


def plot_top_users():
    rows = fetch("SELECT user_id, COUNT(*) AS total FROM events GROUP BY user_id ORDER BY total DESC LIMIT 10;")
    users, counts = zip(*rows)
    fig, ax = plt.subplots()
    ax.barh(users[::-1], counts[::-1], color="mediumseagreen")
    ax.set_title("Top 10 Users by Event Count")
    ax.set_xlabel("Event Count")
    fig.tight_layout()
    fig.savefig(f"{OUTPUT_DIR}/top_users.png")
    plt.close(fig)
