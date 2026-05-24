# PromQL Cookbook for AI Token Observability

All queries assume metrics arrive via OpenTelemetry Collector and land in
Sysdig Monitor. Use them in **Explore → PromQL** or as dashboard panels.

## 0. Sanity / discovery

```promql
# Anything from OTel GenAI semconv or Claude Code?
{__name__=~"gen_ai_.*|claude_code_.*"}
```

## 1. GenAI semantic convention (`gen_ai.client.token.usage`)

### Token rate by model
```promql
sum by (gen_ai_request_model) (
  rate(gen_ai_client_token_usage_total[5m])
)
```

### Input vs Output token rate
```promql
sum by (gen_ai_token_type) (
  rate(gen_ai_client_token_usage_total[5m])
)
```

### 1-hour cumulative tokens per service
```promql
sum by (service_name) (
  increase(gen_ai_client_token_usage_total[1h])
)
```

### Top 5 consumers (last 24h)
```promql
topk(5,
  sum by (service_name) (
    increase(gen_ai_client_token_usage_total[24h])
  )
)
```

### Input:Output ratio per model
```promql
  sum by (gen_ai_request_model) (rate(gen_ai_client_token_usage_total{gen_ai_token_type="output"}[5m]))
/
  sum by (gen_ai_request_model) (rate(gen_ai_client_token_usage_total{gen_ai_token_type="input"}[5m]))
```

## 2. Claude Code native metrics

### Token rate by type
```promql
sum by (type, model) (
  rate(claude_code_token_usage_tokens_total[5m])
)
```

### Cache effectiveness (read vs total input-like)
```promql
sum(rate(claude_code_token_usage_tokens_total{type="cacheRead"}[5m]))
/
sum(rate(claude_code_token_usage_tokens_total{type=~"input|cacheRead"}[5m]))
```

### Estimated cost per hour (USD)
```promql
sum by (model) (
  increase(claude_code_cost_usage_USD_total[1h])
)
```

### Active session count
```promql
sum(rate(claude_code_session_count_total[15m]))
```

### Median API request duration
```promql
histogram_quantile(
  0.5,
  sum by (le, model) (
    rate(claude_code_api_request_duration_milliseconds_bucket[5m])
  )
)
```

## 3. Alert candidates

```promql
# Token burn rate > 100k/min for any service
sum by (service_name) (rate(gen_ai_client_token_usage_total[1m])) * 60 > 100000

# Hourly Claude Code spend > $5
sum(increase(claude_code_cost_usage_USD_total[1h])) > 5
```

## Notes

- OTel `gen_ai.client.token.usage` becomes Prometheus `gen_ai_client_token_usage_total` (dots → underscores, `_total` suffix added for counters).
- Resource attributes (`service.name`, `deployment.environment`, ...) are exposed as labels only when `resource_to_telemetry_conversion.enabled: true` is set on the exporter.
- GenAI semconv is still evolving; pin to a specific OTel SDK version if dashboards are mission critical.
