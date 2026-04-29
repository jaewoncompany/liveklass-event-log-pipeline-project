-- Bronze layer: 원본 데이터 보존
CREATE TABLE IF NOT EXISTS raw_events (
    id          BIGSERIAL    PRIMARY KEY,
    received_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    payload     JSONB        NOT NULL
);

-- Silver layer: 분석용 정제 테이블 (월별 파티셔닝)
CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL,
    raw_id      BIGINT       NOT NULL,
    event_id    UUID         NOT NULL,
    event_type  VARCHAR(50)  NOT NULL,
    user_id     VARCHAR(50)  NOT NULL,
    session_id  UUID         NOT NULL,
    timestamp   TIMESTAMPTZ  NOT NULL,
    ip_address  INET,
    user_agent  TEXT,
    page        VARCHAR(255),
    referrer    VARCHAR(255),
    duration_ms INTEGER,
    error_code  SMALLINT,
    product_id  VARCHAR(50),
    amount      NUMERIC(10, 2),
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- 파티션 (월별 자동 스캔 범위 축소)
CREATE TABLE IF NOT EXISTS events_2026_04 PARTITION OF events
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE TABLE IF NOT EXISTS events_2026_05 PARTITION OF events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE TABLE IF NOT EXISTS events_2026_06 PARTITION OF events
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

-- 인덱스 (파티션 테이블에 걸면 각 파티션에 자동 적용)
CREATE INDEX IF NOT EXISTS idx_events_type      ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_user_id   ON events (user_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp);

-- micro-batch checkpoint
CREATE TABLE IF NOT EXISTS etl_checkpoint (
    id            INT  PRIMARY KEY DEFAULT 1,
    last_raw_id   BIGINT NOT NULL DEFAULT 0,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO etl_checkpoint (id, last_raw_id) VALUES (1, 0)
    ON CONFLICT DO NOTHING;
