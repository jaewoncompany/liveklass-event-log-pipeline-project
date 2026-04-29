import os
import random
import uuid
from datetime import datetime, timezone
from faker import Faker

fake = Faker()

EVENT_TYPES = os.getenv("EVENT_TYPES").split(",")
PAGES       = os.getenv("PAGES").split(",")
PRODUCTS    = os.getenv("PRODUCTS").split(",")
ERROR_CODES = [int(c) for c in os.getenv("ERROR_CODES").split(",")]
USER_COUNT  = int(os.getenv("USER_COUNT"))
EVENT_COUNT = int(os.getenv("EVENT_COUNT"))

EVENT_FIELDS = {
    "page_view": lambda: {
        "page":        random.choice(PAGES),
        "referrer":    random.choice(PAGES + [None]),
        "duration_ms": random.randint(100, 10000),
        "error_code":  None,
        "product_id":  None,
        "amount":      None,
    },
    "purchase": lambda: {
        "page":        "/checkout",
        "referrer":    "/cart",
        "duration_ms": None,
        "error_code":  None,
        "product_id":  random.choice(PRODUCTS),
        "amount":      round(random.uniform(5.0, 500.0), 2),
    },
    "error": lambda: {
        "page":        random.choice(PAGES),
        "referrer":    None,
        "duration_ms": None,
        "error_code":  random.choice(ERROR_CODES),
        "product_id":  None,
        "amount":      None,
    },
    "login": lambda: {
        "page":        "/login",
        "referrer":    random.choice(PAGES),
        "duration_ms": random.randint(200, 3000),
        "error_code":  None,
        "product_id":  None,
        "amount":      None,
    },
    "logout": lambda: {
        "page":        "/logout",
        "referrer":    None,
        "duration_ms": None,
        "error_code":  None,
        "product_id":  None,
        "amount":      None,
    },
}


def generate_event():
    event_type = random.choice(EVENT_TYPES)
    event = {
        "event_id":   str(uuid.uuid4()),
        "event_type": event_type,
        "user_id":    f"user_{random.randint(1, USER_COUNT)}",
        "session_id": str(uuid.uuid4()),
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "ip_address": fake.ipv4(),
        "user_agent": fake.user_agent(),
    }
    event.update(EVENT_FIELDS[event_type]())
    return event


def generate_events(n=None):
    count = n or EVENT_COUNT
    return [generate_event() for _ in range(count)]
