# AdSignal — Competitive Ad Intelligence Platform

![CI](https://github.com/zahar-t/adsignal/actions/workflows/ci.yml/badge.svg)

> Spark · Iceberg · MongoDB · Prophet · Isolation Forest · LLM · Dagster · FastAPI

An end-to-end media intelligence platform that ingests publicly observable ad signals,
stores raw creative metadata in MongoDB, processes it at scale with PySpark into an
Apache Iceberg lakehouse, runs spend anomaly detection and trend forecasting, and uses
a local LLM (Ollama) or Anthropic API to generate analyst-grade competitive intelligence briefs.

**What makes this different:** The LLM layer is not a chatbot — it acts as an interpretation
layer over quantitative model outputs (Prophet trends + Isolation Forest anomalies),
generating structured analytical prose that a media buyer could act on.

## Stack

| Layer | Technology | Why |
|---|---|---|
| Raw Store | MongoDB 7.0 | Schema-flexible ad creative documents |
| Processing | PySpark 4.0 | Partitioned ETL at scale |
| Table Format | Apache Iceberg 0.9 | Time-travel brand comparisons |
| Catalog | Lakekeeper REST | S3-compatible, no JVM catalog |
| Forecasting | Prophet | Per-brand/channel spend trends |
| Anomaly Detection | Isolation Forest | Budget shift detection |
| LLM | Ollama (local) / Anthropic | Narrative generation over model outputs |
| Orchestration | Dagster | Full asset lineage |
| API | FastAPI | REST serving layer |
| Dashboard | Reflex | Interactive brand intelligence UI |

## Architecture

```
Data Sources (Meta Ad Library / Synthetic)
         ↓
    MongoDB (raw_creatives)
         ↓
    PySpark ETL
         ↓
    Apache Iceberg (MinIO + Lakekeeper)
      ├── brand_weekly_signals
      └── raw_creatives
         ↓
    ┌────────────────┐
    │ Prophet        │   ┌─────────────────────┐
    │ (forecasting)  │   │ Isolation Forest    │
    └───────┬────────┘   │ (anomaly detection) │
            └─────┬──────┘
                  ↓
           Signal Summary Builder
                  ↓
           LLM Narrative Engine
           (Ollama / Anthropic)
                  ↓
         ┌────────────────┐
         │  FastAPI REST  │    Reflex Dashboard
         │  /brief/{brand}│    - Brand selector
         │  /signals/...  │    - Spend trend charts
         │  /snapshots/.. │    - Channel mix donut
         └────────────────┘    - Time-travel slider
                               - LLM brief panel

Orchestration: Dagster wraps every layer as @asset with full lineage
```

## Quickstart

```bash
git clone https://github.com/zahar-t/adsignal
cd adsignal
cp .env.example .env

# Install dependencies (Python 3.11+ required)
make install

# Start Docker services (Docker Desktop required)
make up              # MinIO + MongoDB + Lakekeeper + Postgres

# Bootstrap Iceberg tables
make bootstrap       # creates ad_intelligence namespace + brand_weekly_signals table

# Populate with synthetic data
make seed            # ~20k docs across 5 brands, 16 weeks of history

# Run PySpark ETL (Java 17 required)
make etl

# Serve
make api             # FastAPI at http://localhost:8000/docs
make dashboard       # Reflex at http://localhost:3000
```

> **Local LLM:** Install [Ollama](https://ollama.ai), run `ollama pull llama3.2`, then set
> `LLM_PROVIDER=ollama` in `.env`. No API key required.

> **LM Studio:** Load a local model in LM Studio, start the local server, then set
> `LLM_PROVIDER=lmstudio`, `LMSTUDIO_BASE_URL=http://localhost:1234/v1`, and `LLM_MODEL`
> to the loaded model id.

> **Anthropic API:** Set `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=your-anthropic-key` in `.env`.

## Dagster Orchestration

```bash
make dagster   # http://localhost:3000
```

Asset groups:
- **ingestion** — `raw_ad_creatives`: fetch from Meta Ad Library or synthetic fallback
- **etl** — `iceberg_brand_signals`: PySpark ETL → Iceberg
- **models** — `brand_signal_summaries`: Prophet + Isolation Forest per brand
- **intelligence** — `brand_briefs`: LLM narrative generation

The `nightly_full_pipeline` schedule runs automatically at midnight UTC.
The `new_mongo_data_sensor` triggers the ETL-only job when new documents appear in MongoDB
(enable it in the Dagster UI to switch from schedule-based to event-driven).

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Service health check |
| `GET /brief/{brand}` | LLM competitive intelligence brief |
| `GET /signals/{brand}` | Weekly signal data (channel, spend, impressions) |
| `GET /snapshots/{table}` | Iceberg snapshot history for time-travel |

Query params: `?refresh=true` (brief), `?channel=video` (signals), `?limit=50` (signals)

## Iceberg Time-Travel

```bash
python scripts/demo_timetravel.py --brand nike
```

Each ETL run creates a new Iceberg snapshot. Use `GET /snapshots/brand_weekly_signals`
to list snapshots and compare spend posture across historical ETL runs.

## Requirements

- Python 3.11+
- Java 17+ (for PySpark 4.x) — `winget install Microsoft.OpenJDK.17`
- Docker Desktop (for MongoDB, MinIO, Lakekeeper)
- Ollama (optional, for local LLM) — [ollama.ai](https://ollama.ai)

## CV Bullets

- Built a media intelligence lakehouse ingesting ad creative metadata from the Meta Ad Library API
  (synthetic fallback via Faker) into MongoDB, processed at scale with PySpark 4.x, and persisted
  to Apache Iceberg via a Lakekeeper REST catalog on MinIO object storage
- Engineered PySpark ETL with partitioned Iceberg writes (brand + week_key), enabling time-travel
  queries to compare brand spend posture across arbitrary historical windows
- Trained per-brand Prophet spend forecasting models and Isolation Forest anomaly detectors on
  weekly aggregated signals; assembled structured signal summaries as LLM context
- Implemented a model-agnostic LLM narrative engine (Ollama local / Anthropic API) that generates
  3-sentence competitive intelligence briefs from quantitative model outputs
- Served intelligence via FastAPI REST endpoints and a Reflex dashboard with Iceberg snapshot
  selector; orchestrated end-to-end with Dagster asset lineage

## License

MIT
