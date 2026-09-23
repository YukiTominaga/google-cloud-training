#!/usr/bin/env bash
# =====================================================================
# M13 素材 3. API から Gemini Enterprise app に agent を登録する
# ---------------------------------------------------------------------
# コンソール（素材 2）と同じ 4 項目を、REST API で渡す。
#   displayName / description / reasoningEngine のリソース名（＋任意で OAuth）
#
#   変数               | 値
#   -------------------+-----------------------------------------------
#   ENDPOINT_LOCATION  | us / eu / global（app のロケーション）
#   PROJECT_ID         | Gemini Enterprise app のあるプロジェクト
#   APP_ID             | Gemini Enterprise app の ID
#   RESOURCE_LOCATION  | Agent Runtime のリージョン（例: us-central1）
#   RESOURCE_ID        | M12 で控えた数値 ID
#   APP_LOCATION       | URL パス中の locations/…（講師ガイドの記載は global）
#
# ※ ホスト名とパス中のロケーションの組み合わせは app の作成場所で変わるため、
#   うまくいかないときは Gemini Enterprise のドキュメントで確認する。
# =====================================================================
set -euo pipefail
: "${PROJECT_ID:?PROJECT_ID を設定してください}"
: "${APP_ID:?APP_ID を設定してください}"
: "${RESOURCE_ID:?RESOURCE_ID を設定してください}"
: "${ENDPOINT_LOCATION:=us}"
: "${APP_LOCATION:=global}"
: "${RESOURCE_LOCATION:=us-central1}"
HOST="${ENDPOINT_LOCATION}-discoveryengine.googleapis.com"

# v1alpha … 2026年9月時点で agent 登録 API はアルファ版のパス
# X-Goog-User-Project … 課金・クォータを付けるプロジェクトの指定
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "https://${HOST}/v1alpha/projects/${PROJECT_ID}/locations/${APP_LOCATION}/collections/default_collection/engines/${APP_ID}/assistants/default_assistant/agents" \
  -d '{
    "displayName": "Order Support Agent",
    "description": "Handles order status, billing questions, and return requests for retail customers.",
    "adkAgentDefinition": {
      "provisionedReasoningEngine": {
        "reasoningEngine": "projects/'"${PROJECT_ID}"'/locations/'"${RESOURCE_LOCATION}"'/reasoningEngines/'"${RESOURCE_ID}"'"
      }
    }
  }'
