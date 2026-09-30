#!/usr/bin/env bash
# OpenTelemetry → Google Cloud 転送デモ用 curl まとめ
#
# 使い方:
#   ./scripts/otel-demo.sh [log|trace|slow|metric|all]   (省略時は all)
#
# 環境変数:
#   BASE_URL  送信先（デフォルト: Cloud Run のデモサービス）
set -euo pipefail

BASE_URL="${BASE_URL:-https://google-cloud-training-103175005729.asia-northeast1.run.app}"

# リクエストごとに W3C traceparent を生成し、Cloud Logging と Cloud Trace を紐付けて見られるようにする
new_traceparent() {
  echo "00-$(openssl rand -hex 16)-$(openssl rand -hex 8)-01"
}

# レスポンスを表示（jq があれば整形）
show() {
  if command -v jq >/dev/null 2>&1; then jq .; else cat; echo; fi
}

call() {
  local method="$1" path="$2" body="${3:-}"
  local tp
  tp="$(new_traceparent)"
  echo "==> ${method} ${path}"
  echo "    traceparent: ${tp}"
  if [[ -n "$body" ]]; then
    curl -sS -X "$method" "${BASE_URL}${path}" \
      -H "Content-Type: application/json" \
      -H "traceparent: ${tp}" \
      -d "$body" | show
  else
    curl -sS -X "$method" "${BASE_URL}${path}" \
      -H "traceparent: ${tp}" | show
  fi
  echo
}

# 構造化ロギング（Cloud Logging / Error Reporting）
demo_log() {
  call POST /logging/structure '{"userId": "123", "action": "login"}'
  call POST /logging/test/info '{"message": "info sample", "value": 42}'
  call POST /logging/test/warn '{"message": "warn sample", "value": 42}'
  call POST /logging/test/error '{"message": "error sample", "value": 42}'
}

# トレース（Telemetry API 経由で Cloud Trace へ）
demo_trace() {
  call GET /telemetry/basic
  call GET /telemetry/attributes
  call GET /telemetry/nested
  call GET /telemetry/error
}

# 応答まで約 10 秒かかる長時間処理（親 span + 4 つの子 span、Cloud Trace のウォーターフォール確認用）
demo_slow() {
  call GET /trace/slow
}

# カスタム指標（Telemetry API 経由で Cloud Monitoring へ）
demo_metric() {
  call POST /monitoring/custom-metrics \
    '{"metricType": "application/request_count", "value": 42, "labels": {"environment": "training"}}'
  call POST /monitoring/custom-metrics/sample
}

case "${1:-all}" in
  log) demo_log ;;
  trace) demo_trace ;;
  slow) demo_slow ;;
  metric) demo_metric ;;
  all)
    demo_log
    demo_trace
    demo_slow
    demo_metric
    ;;
  *)
    echo "Usage: $0 [log|trace|slow|metric|all]" >&2
    exit 1
    ;;
esac
