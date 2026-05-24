# sysdig-ai-token-observability

AI / Coding Agent の **トークン使用量** と **コスト** を、OpenTelemetry 経由で **Sysdig Monitor** から眺めるための最小サンプル。アプリ側の書き換えは不要。

[English README](./README.md)

```
[Claude Code / OpenAI app / Cursor] ──OTLP──> [OTel Collector] ──Remote Write──> [Sysdig Monitor]
```

- **GenAI semconv** (`gen_ai.client.token.usage`) — OTel 標準のため LLM プロバイダ非依存。
- **Claude Code native metrics** — Claude Code 自体の OTLP exporter をこの Collector に向けるだけ。
- **バックエンドは Sysdig Monitor** — Infra / K8s / CVE と同じ画面で AI コストを見る。

## 5 分で動かす

### 1. clone と設定

```bash
git clone https://github.com/higakikeita/sysdig-ai-token-observability.git
cd sysdig-ai-token-observability
cp .env.example .env
# .env を編集: SYSDIG_API_TOKEN (Monitor 用) と SYSDIG_MONITOR_URL
```

### 2. Collector 起動

```bash
docker compose up -d otelcol
docker compose logs -f otelcol
```

### 3. メトリクスを 1 本流す (Python OpenAI demo)

```bash
cd examples/python-openai
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
python app.py
```

ローカル確認:

```bash
curl -s localhost:9464/metrics | grep gen_ai_client_token_usage
```

期待:

```
gen_ai_client_token_usage_total{gen_ai_request_model="gpt-4o-mini",gen_ai_system="openai",gen_ai_token_type="input",service_name="ai-token-demo"} 42
gen_ai_client_token_usage_total{...,gen_ai_token_type="output",...} 81
```

### 4. Sysdig Monitor で確認

**Sysdig Monitor → Explore → PromQL**:

```promql
sum by (gen_ai_request_model, gen_ai_token_type) (
  rate(gen_ai_client_token_usage_total[5m])
)
```

データが出ない時は、まず取り込み済みかどうか:

```promql
{__name__=~"gen_ai_.*|claude_code_.*"}
```

### 5. ダッシュボードを取り込む

`sysdig/dashboard.json` (v3) を import:

```bash
curl -X POST "${SYSDIG_MONITOR_URL}/api/v3/dashboards" \
  -H "Authorization: Bearer ${SYSDIG_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d @sysdig/dashboard.json
```

UI からなら: **Dashboards → ＋ → Import → `dashboard.json` をアップロード**。

## Claude Code を観測対象に追加

[`examples/claude-code/README.md`](./examples/claude-code/README.md) 参照。要点だけ:

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_SERVICE_NAME=claude-code-cli
claude
```

自分の Coding Agent 利用量を Sysdig 側でそのまま観測:

```promql
sum by (type, model)(rate(claude_code_token_usage_tokens_total[5m]))
sum(increase(claude_code_cost_usage_USD_total[1h]))   # USD/hour
```

> メトリクス名に `_tokens_` / `_USD_` が挟まる理由は下の **ハマりどころ #1** 参照。

## API Key 無しでダッシュボードを試す

`examples/synthetic-demo/generate.py` が全 6 パネル分の合成メトリクスを送ります。OpenAI / Anthropic クレジットも Claude Code 本体もなしで、2 分でダッシュボードが全部埋まります。

```bash
python examples/synthetic-demo/generate.py            # 12 発 (2 分) で終了
python examples/synthetic-demo/generate.py --forever  # 連続送信
```

## ハマりどころ

### 0. 認証 / 接続まわり (まずここ)

| 症状 | 原因 / 対処 |
|---|---|
| Sysdig 側にデータが出ない | `SYSDIG_API_TOKEN` が **Secure** 用になっている。**Monitor** 用を発行する。 |
| `service_name` が label に出ない | `resource_to_telemetry_conversion: enabled: true` が exporter にあるか確認。 |
| 401 / 403 | Token のスコープ・region URL のズレ。`https://us2.app.sysdig.com` 等、region に合わせる。 |

### 1. OTel Prometheus exporter は unit を metric 名に付ける

`claude_code.token.usage` (unit: `tokens`) → on-the-wire 名は **`claude_code_token_usage_tokens_total`**。`_tokens_` が中に挟まる。

annotation 形式の unit (`{token}` のような中括弧つき) は剥がされるので、`gen_ai.client.token.usage` (unit: `{token}`) → `gen_ai_client_token_usage_total` (綺麗)。

PromQL では on-the-wire 名で書く:

| OTLP 側 | unit | Prometheus 側 |
|---|---|---|
| `claude_code.token.usage` | `tokens` | `claude_code_token_usage_tokens_total` |
| `claude_code.cost.usage`  | `USD`    | `claude_code_cost_usage_USD_total` |
| `claude_code.active_time` | `seconds`| `claude_code_active_time_seconds_total` |
| `gen_ai.client.token.usage` | `{token}` | `gen_ai_client_token_usage_total` |

### 2. Sysdig v3 dashboard schema の落とし穴

`POST /api/v3/dashboards` で:

- `inputFormat` / `minInputFormat` / `maxInputFormat` は **整数** (scale factor)。`1` が等倍。文字列 `"number"` 等は黙って null 扱いになる。
- `dashboard.version` を入れると "New dashboard can't have version id." で 422。新規作成時は外す。
- panel の `unit: "%"` と `inputFormat: 1` を併用すると "Format/Prefix does not match the unit"。比率パネルは `unit: "number"` にして軸ラベルで「ratio (0-1)」と書く。
- `axesConfiguration.right` と `legendConfiguration.{showCurrent,layout}` は使わなくても必須。

これらは全部この repo の `sysdig/dashboard.json` に反映済み。パネルを足すときはそこからコピーするのが安全。

### 3. 新規 custom metric は最初の数分間 Sysdig に消されることがある

Remote Write で初めて送る metric 名は ingestion 側で 30-90 秒ほど drop されるケースを確認しています。一度 metric 名が「登録」されれば後続は通る。**ダッシュボードが空のままなら 1-2 分待って再クエリ**。

最短で metric 名を Sysdig に覚えさせる方法は `examples/synthetic-demo/generate.py` を 1 回流すこと。これで Sysdig が学習した後、本物の Claude Code や Python アプリのデータが即座に見えるようになります。

## Sysdig region 一覧

| Region   | `SYSDIG_MONITOR_URL`           |
|----------|--------------------------------|
| US East  | `https://us2.app.sysdig.com`   |
| US West  | `https://app.sysdig.com`       |
| EU       | `https://eu1.app.sysdig.com`   |
| AU       | `https://app.au1.sysdig.com`   |

## ライセンス

[Apache-2.0](./LICENSE)
