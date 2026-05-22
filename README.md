# sysdig-ai-token-observability

Observe AI / Coding-Agent **token usage** and **cost** in **Sysdig Monitor**, via OpenTelemetry — no code rewrite of your apps required.

[日本語版 README はこちら](./README.ja.md)

```
[Claude Code / OpenAI app / Cursor] ──OTLP──> [OTel Collector] ──Remote Write──> [Sysdig Monitor]
```

- **GenAI semantic conventions** (`gen_ai.client.token.usage`) — vendor-neutral, works with any OTel-instrumented LLM client.
- **Claude Code native metrics** — point Claude Code's OTLP exporter at the included collector.
- **Sysdig Monitor as the backend** — same place you already watch infra, K8s, and CVEs.

## Quick start (≈ 5 min)

### 1. Clone and configure

```bash
git clone https://github.com/higakikeita/sysdig-ai-token-observability.git
cd sysdig-ai-token-observability
cp .env.example .env
# edit .env -- set SYSDIG_API_TOKEN (Monitor token) and SYSDIG_MONITOR_URL
```

### 2. Start the collector

```bash
docker compose up -d otelcol
docker compose logs -f otelcol   # ctrl-c to stop tailing
```

### 3. Send one metric (Python OpenAI demo)

```bash
cd examples/python-openai
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
python app.py
```

Verify locally:

```bash
curl -s localhost:9464/metrics | grep gen_ai_client_token_usage
```

Expected:

```
gen_ai_client_token_usage_total{gen_ai_request_model="gpt-4o-mini",gen_ai_system="openai",gen_ai_token_type="input",service_name="ai-token-demo"} 42
gen_ai_client_token_usage_total{...,gen_ai_token_type="output",...} 81
```

### 4. Verify in Sysdig Monitor

Open **Sysdig Monitor → Explore → PromQL**:

```promql
sum by (gen_ai_request_model, gen_ai_token_type) (
  rate(gen_ai_client_token_usage_total[5m])
)
```

### 5. Import the dashboard

`sysdig/dashboard.json` is a v3 Sysdig dashboard. Import via:

```bash
curl -X POST "${SYSDIG_MONITOR_URL}/api/v3/dashboards" \
  -H "Authorization: Bearer ${SYSDIG_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d @sysdig/dashboard.json
```

Or use the UI: **Dashboards → ＋ → Import → upload `dashboard.json`**.

## Add Claude Code as a source

See [`examples/claude-code/README.md`](./examples/claude-code/README.md). TL;DR:

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_SERVICE_NAME=claude-code-cli
claude
```

Now you can watch your *own* coding-agent usage in Sysdig:

```promql
sum by (type, model)(rate(claude_code_token_usage_total[5m]))
sum(increase(claude_code_cost_usage_total[1h]))   # USD/hour
```

## What's in the box

```
.
├── docker-compose.yml         # one-shot collector
├── otelcol/config.yaml        # OTLP -> Prometheus + Sysdig Remote Write
├── examples/
│   ├── python-openai/         # GenAI semconv emitter (one HTTP call, two counters)
│   └── claude-code/           # env-var recipe for Claude Code OTLP
├── sysdig/
│   ├── dashboard.json         # v3 dashboard, 6 panels
│   └── promql-queries.md      # PromQL cookbook
└── docs/architecture.md       # diagram + design notes
```

## Sysdig regions

| Region   | `SYSDIG_MONITOR_URL`           |
|----------|--------------------------------|
| US East  | `https://us2.app.sysdig.com`   |
| US West  | `https://app.sysdig.com`       |
| EU       | `https://eu1.app.sysdig.com`   |
| AU       | `https://app.au1.sysdig.com`   |

Use the **Monitor** API token (not the Secure token).

## Production notes

- **Kubernetes:** instead of docker-compose, run the collector as a Deployment + Service; have the existing Sysdig Agent scrape `:9464` via `prometheus.io/scrape` annotations. See `docs/architecture.md`.
- **High cardinality:** the GenAI conventions are intentionally low-cardinality (model, token-type, service). Don't add per-user labels unless your billing model needs them — it will blow up your metric count.
- **Secret rotation:** the only secret is `SYSDIG_API_TOKEN`. Scope it to a Monitor-only team and rotate it via your secret manager of choice.
- **No prompt content** is captured — only counters and resource attributes.

## License

[Apache-2.0](./LICENSE)
