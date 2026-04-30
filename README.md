수행한 과제 : 필수과제, 선택과제 A, 선택과제 B

# 이벤트 로그 파이프라인

웹 서비스 이벤트를 생성 → 저장 → 분석 → 시각화하는 파이프라인입니다.

---

## 실행 방법

필요한 도구: Docker, Docker Compose

```bash
# 전체 스택 실행
docker compose up --build
```

실행 후 접속
- Grafana 대시보드: http://localhost:3000 (admin / admin)
- matplotlib 차트 이미지: `./output/` 폴더

처음 실행하거나 DB를 초기화할 때는 볼륨까지 삭제 후 재실행해야 합니다.
```bash
docker compose down -v
docker compose up --build
```

---

## 이벤트 설계

| 타입 | 설명 | 주요 필드 |
|---|---|---|
| `page_view` | 페이지 조회 | page, referrer, duration_ms |
| `purchase` | 구매 완료 | product_id, amount |
| `error` | 에러 발생 | page, error_code |
| `login` | 로그인 | page, duration_ms |
| `logout` | 로그아웃 | page |

공통 필드(event_id, user_id, session_id, timestamp 등)는 모든 타입이 공유하고, 타입별 전용 필드는 해당 없으면 NULL로 저장합니다.

---

## 스키마

Bronze/Silver 2-레이어 구조로 설계했습니다.

### Bronze: `raw_events`
원본 이벤트를 JSONB로 그대로 보존합니다. 재처리가 필요할 때 이 테이블을 기준으로 다시 변환할 수 있습니다.

```sql
CREATE TABLE raw_events (
    id          BIGSERIAL    PRIMARY KEY,
    received_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    payload     JSONB        NOT NULL
);
```

### Silver: `events`
분석에 최적화된 정제 테이블입니다. timestamp 기준 월별 파티셔닝을 적용해 데이터가 쌓여도 쿼리 성능을 유지합니다.

```sql
CREATE TABLE events (
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
```

### `etl_checkpoint`
micro-batch 처리 시 마지막으로 처리한 `raw_id`를 기록합니다. 실패 시 해당 청크부터 재처리할 수 있습니다.

### 이 구조를 선택한 이유

raw_events에 원본을 보존하면 변환 로직이 바뀌어도 언제든 재처리할 수 있습니다. events 테이블은 분석 쿼리에 최적화된 구조로 변환해서 적재합니다. 골드 레이어(집계 마트 테이블)는 이 과제에서 Silver에서 바로 SQL 집계로 분석하는 구조라 별도로 만들지 않았습니다.

PostgreSQL을 선택한 이유: 필드 구분 저장, SQL 집계 쿼리, UUID/INET/TIMESTAMPTZ 전용 타입, 파티셔닝 지원.

---

## 데이터 처리 흐름

```
generate_events()
      │
      ▼
save_raw()         → raw_events (JSONB 원본 보존)
      │
      ▼
run_micro_batch()  → BATCH_SIZE(100)건씩 청크 처리
  chunk 1 (1~100)  → transform → events 파티션 적재 → checkpoint 업데이트
  chunk 2 (101~200)→ transform → events 파티션 적재 → checkpoint 업데이트
  ...
```

---

## 분석 쿼리

```sql
-- 1. 이벤트 타입별 발생 횟수
SELECT event_type, COUNT(*) AS count
FROM events GROUP BY event_type ORDER BY count DESC;

-- 2. 유저별 총 이벤트 수 (Top 10)
SELECT user_id, COUNT(*) AS total_events
FROM events GROUP BY user_id ORDER BY total_events DESC LIMIT 10;

-- 3. 시간대별 이벤트 추이
SELECT date_trunc('hour', timestamp) AS time, COUNT(*) AS count
FROM events GROUP BY time ORDER BY time;

-- 4. 에러 이벤트 비율
SELECT event_type, COUNT(*) AS count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM events GROUP BY event_type ORDER BY count DESC;
```

---

## 시각화

두 가지 방식으로 시각화했습니다.

### matplotlib (이미지 파일)
`docker compose up` 실행 후 `./output/` 폴더에 저장됩니다.

| 파일 | 내용 |
|---|---|
| `event_type_count.png` | 이벤트 타입별 발생 횟수 |
| `hourly_trend.png` | 시간대별 이벤트 추이 |
| `event_distribution.png` | 이벤트 타입 비율 |
| `top_users.png` | 이벤트 수 상위 10명 |

### Grafana (대시보드)
`http://localhost:3000` 접속 시 PostgreSQL 데이터소스와 대시보드가 자동으로 프로비저닝됩니다. 별도 설정 없이 바로 확인할 수 있습니다.

대시보드 구성은 `grafana/provisioning/dashboards/event_pipeline.json`에 정의돼 있고, 데이터소스는 `grafana/provisioning/datasources/postgres.yaml`에서 자동 연결됩니다.

---

## 구현하면서 고민한 점

**Bronze/Silver 레이어 분리**
raw_events에 원본을 보존하고 events에 정제된 데이터를 적재하는 구조로 설계했습니다. 골드 레이어는 집계 마트 테이블인데, 이 과제에서는 Silver에서 바로 SQL 집계로 분석하는 구조라 별도로 만들지 않았습니다. 대규모 서비스에서 대시보드 성능이 중요해지면 그때 추가할 것 같습니다.

**micro-batch checkpoint**
500건을 한 번에 처리하다가 실패하면 전체를 재처리해야 합니다. BATCH_SIZE(100)씩 나눠서 처리하고 청크마다 checkpoint를 업데이트하면, 실패해도 해당 청크부터 재시작할 수 있습니다.

**패스워드 특수문자 문제**
`Passw@rd` 같은 패스워드를 SQLAlchemy URL에 넣으면 `@`가 host 구분자로 파싱돼서 연결이 깨졌습니다. URL 방식 대신 `creator` 파라미터로 `psycopg2.connect()`를 직접 넘기는 방식으로 해결했습니다.

**DB 초기화 타이밍**
`docker compose down`만 하면 볼륨이 남아서 `init.sql`이 재실행되지 않습니다. PostgreSQL 공식 이미지는 볼륨이 비어있을 때만 초기화 스크립트를 실행하기 때문입니다. `docker compose down -v`로 볼륨까지 삭제해야 합니다.

---

## Kubernetes (선택 과제 A)

### 작성한 manifest 파일

| 파일 | 리소스 | 역할 |
|---|---|---|
| `k8s/namespace.yaml` | Namespace | 파이프라인 전용 격리 공간 |
| `k8s/configmap.yaml` | ConfigMap | 비민감 환경변수 관리 |
| `k8s/secret.yaml` | Secret | DB 패스워드 등 민감 정보 |
| `k8s/postgres/pvc.yaml` | PersistentVolumeClaim | DB 데이터 영속성 스토리지 |
| `k8s/postgres/deployment.yaml` | Deployment | PostgreSQL 파드 배포 |
| `k8s/postgres/service.yaml` | Service (ClusterIP) | 클러스터 내부 DB 접근용 DNS |
| `k8s/app/deployment.yaml` | Deployment | 이벤트 생성기 앱 배포 |
| `k8s/app/cronjob.yaml` | CronJob | 매 시간 정각 이벤트 자동 생성 |

### 리소스 선택 이유

**PVC**
쿠버네티스에서 파드가 재시작되면 컨테이너 내부 파일시스템은 초기화됩니다. PVC 없이 PostgreSQL을 올리면 파드가 죽을 때 DB 데이터도 같이 사라집니다. PVC는 파드 외부에 스토리지를 따로 요청해서 파드 생명주기와 데이터 생명주기를 분리합니다.

**Deployment vs CronJob**
Deployment는 파드가 죽으면 자동으로 다시 띄워주는 self-healing이 핵심입니다. PostgreSQL처럼 항상 떠있어야 하는 서비스에 적합합니다. CronJob은 주기적으로 실행하고 종료되는 일회성 잡에 씁니다. 이벤트 생성기는 실행 → 이벤트 생성 → DB 저장 → 종료 흐름이라 CronJob이 맞습니다.

**ConfigMap vs Secret**
ConfigMap은 평문으로 저장되어 값이 그대로 노출됩니다. DB 호스트, 포트, 이벤트 타입 목록처럼 노출돼도 문제없는 값을 여기에 넣었습니다. Secret은 RBAC으로 조회 권한 자체를 제한할 수 있어서 DB 패스워드처럼 노출되면 안 되는 값만 분리했습니다.

**Namespace**
모든 리소스를 `event-pipeline` 네임스페이스 안에 격리했습니다. 다른 서비스와 리소스 이름 충돌을 막고, `kubectl get all -n event-pipeline`으로 이 파이프라인 관련 리소스만 한 번에 조회할 수 있습니다.

---

## AWS 아키텍처 (선택 과제 B)

이 파이프라인을 AWS에서 운영한다면 아래와 같이 구성합니다.

### 아키텍처 구성도

![AWS 아키텍처](라이브클래스아키텍처.drawio.png)

### 데이터 흐름

```
EC2 (이벤트 생성)
        ↓
Kinesis Data Streams   → 이벤트 수신 및 버퍼링
        ↓
Kinesis Firehose       → S3에 JSON 자동 배치 저장
        ↓
S3 Bronze              → 원본 JSON 보존
        ↓
AWS Glue               → JSON → Parquet ETL 변환
        ↓
S3 Silver              → 정제 데이터 Parquet 저장
        ↓
Athena                 → S3 쿼리, SQL 집계 분석
        ↓
Grafana                → 대시보드 시각화
```

### AWS 서비스 역할 차이

RDS와 S3+Athena는 비슷해 보이지만 용도가 다릅니다. RDS는 트랜잭션이 중요한 서비스 운영용 DB고, S3+Athena는 대용량 로그 데이터를 저렴하게 저장하고 분석하는 구조입니다. 이벤트 로그는 한 번 쓰고 주로 읽기만 하는 특성이 있어서 RDS보다 S3+Athena가 적합합니다. RDS는 인스턴스가 항상 떠있어야 해서 비용이 고정으로 나오지만, Athena는 쿼리할 때만 비용이 발생하고 스토리지도 S3 요금만 내면 돼서 로그처럼 데이터가 무한히 쌓이는 경우에 유리합니다.

### 가장 고민한 부분

**저장소 선택 - PostgreSQL vs S3+Athena**
로컬에서는 docker compose up 하나로 실행 가능한 PostgreSQL이 적합했습니다. 하지만 운영 환경에서는 이벤트 로그처럼 데이터가 무한히 쌓이는 특성상 S3+Athena가 비용과 확장성 면에서 유리하다고 판단했습니다. RDS는 인스턴스가 항상 떠있어야 하지만 Athena는 쿼리할 때만 비용이 발생하기 때문입니다.

**Bronze/Silver 레이어 분리 - 데이터 재사용성**
원본을 Bronze에 보존하면 Glue 변환 로직이 바뀌어도 언제든 재처리할 수 있습니다. 처음부터 Parquet으로만 저장하면 원본이 사라져서 재처리가 불가능합니다. 이 구조는 로컬 파이프라인에도 동일하게 적용했습니다.

---

## 마치며

데이터 파이프라인 구축은 처음 도전해본 영역이라 구현하면서 각 개념을 하나씩 이해하는 데 집중했습니다. Grafana는 평소에 관심 있게 공부했던 도구라 Provisioning 자동화까지 구현했습니다. 선택 과제에서는 로컬 스택을 AWS로 옮기는 과정에서 S3+Athena가 이벤트 로그에 적합한 이유, Kinesis가 필요한 이유를 직접 고민하며 설계했습니다.
