# Claude Code → OTel Collector → Sysdig Monitor

Claude Code emits OpenTelemetry metrics natively. Pointing it at the local
collector adds Claude Code session metrics (tokens, cost, request duration,
session count) on top of any GenAI app metrics.

## Setup

Run the collector first:

```bash
cd ../..      # repo root
docker compose up -d otelcol
```

Then start Claude Code with OTLP enabled:

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_METRIC_EXPORT_INTERVAL=10000    # 10s — useful for demos
export OTEL_SERVICE_NAME=claude-code-cli

claude
```

Use Claude Code normally. Metrics flow:

```
claude  ──OTLP──>  otelcol :4317  ──Remote Write──>  Sysdig Monitor
                          └──Prometheus :9464──>  (optional Sysdig Agent scrape)
```

## Metrics emitted

| Metric (Prometheus name)                        | Type      | Key labels                                   |
|-------------------------------------------------|-----------|----------------------------------------------|
| `claude_code_token_usage_total`                 | Counter   | `type` (input/output/cacheRead/cacheCreation), `model` |
| `claude_code_cost_usage_total`                  | Counter   | `model`                                      |
| `claude_code_api_request_duration_milliseconds` | Histogram | `model`                                      |
| `claude_code_session_count_total`               | Counter   |                                              |
| `claude_code_active_time_total`                 | Counter   |                                              |

## Verify locally

```bash
curl -s localhost:9464/metrics | grep claude_code_
```

## Verify in Sysdig Monitor

```promql
# Token rate by type
sum by (type) (rate(claude_code_token_usage_total[5m]))

# Cumulative cost in last hour
sum(increase(claude_code_cost_usage_total[1h]))

# Cache hit ratio (cache-read tokens / total input-like tokens)
sum(rate(claude_code_token_usage_total{type="cacheRead"}[5m]))
  /
sum(rate(claude_code_token_usage_total{type=~"input|cacheRead"}[5m]))
```
