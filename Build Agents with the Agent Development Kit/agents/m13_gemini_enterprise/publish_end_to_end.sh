#!/usr/bin/env bash
# =====================================================================
# M13 素材 7. 通し題材 ― サポート agent を社内に公開する
# ---------------------------------------------------------------------
#   ① Deploy（M12） → ② Register（M13） → ③ Share（管理画面）
#
# 使い方（agents/ フォルダで）:
#   export PROJECT_ID=my-project
#   export APP_ID=my-gemini-enterprise-app
#   bash m13_gemini_enterprise/publish_end_to_end.sh
# =====================================================================
set -euo pipefail
: "${PROJECT_ID:?PROJECT_ID を設定してください}"
: "${APP_ID:?APP_ID を設定してください}"
REGION=us-central1   # us の app に登録するので us- のリージョンにデプロイする

# ---------------------------------------------------------------------
# ① Deploy（M12）
# ---------------------------------------------------------------------
# 出力の最終行付近に projects/.../reasoningEngines/9876543210 が出るので、
# ログから末尾の数値 ID を取り出す。
DEPLOY_LOG="$(mktemp)"
adk deploy agent_engine \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --display_name="Order Support Agent" \
    --description="Retail customer support coordinator." \
    m13_gemini_enterprise | tee "$DEPLOY_LOG"
# 出力例:
# projects/123456789/locations/us-central1/reasoningEngines/9876543210

RESOURCE_ID="$(grep -oE 'reasoningEngines/[0-9]+' "$DEPLOY_LOG" | tail -1 | cut -d/ -f2)"
: "${RESOURCE_ID:?デプロイ結果から RESOURCE_ID を取得できませんでした}"
echo "RESOURCE_ID=${RESOURCE_ID}"

# ---------------------------------------------------------------------
# ② Register（M13）
# ---------------------------------------------------------------------
# description は「何をするか／何をしないか」を明記する（素材 4）
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  "https://us-discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_ID}/locations/global/collections/default_collection/engines/${APP_ID}/assistants/default_assistant/agents" \
  -d "{
    \"displayName\": \"Order Support Agent\",
    \"description\": \"Handles order status, delivery estimates, billing questions, invoices, and return requests for retail customers. Does not handle HR, IT support, or product recommendations.\",
    \"adkAgentDefinition\": {
      \"provisionedReasoningEngine\": {
        \"reasoningEngine\": \"projects/${PROJECT_ID}/locations/${REGION}/reasoningEngines/${RESOURCE_ID}\"
      }
    }
  }"

# ---------------------------------------------------------------------
# ③ Share
# ---------------------------------------------------------------------
# Gemini Enterprise の管理画面から、対象のグループにロールを割り当てる。
echo "③ Share：Gemini Enterprise の管理画面で、共有先（個人／グループ／組織）を設定してください。"
