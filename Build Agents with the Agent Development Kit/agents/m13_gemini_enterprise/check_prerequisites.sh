#!/usr/bin/env bash
# =====================================================================
# M13 素材 1. 登録の前提条件を確認する
# ---------------------------------------------------------------------
#   前提        | 内容
#   ------------+-----------------------------------------------
#   IAM ロール  | Gemini Enterprise Admin
#   API         | Discovery Engine API が有効
#   アプリ      | 既存の Gemini Enterprise app
#   リソース    | M12 のデプロイで得た reasoningEngine のリソース名
#
# ⚠️ agent のデプロイ先リージョンは、app のロケーションと整合している必要がある。
#    us の app は us- のリージョン、global の app はどのリージョンでも可。
#    食い違うと登録に失敗する。
#
# 使い方：export PROJECT_ID=my-project && bash check_prerequisites.sh
# =====================================================================
set -euo pipefail
: "${PROJECT_ID:?PROJECT_ID を設定してください}"

# ① Discovery Engine API が有効か（無効なら有効化する）
if gcloud services list --enabled --project="$PROJECT_ID" \
     --filter="config.name=discoveryengine.googleapis.com" --format="value(config.name)" | grep -q .; then
  echo "✅ Discovery Engine API は有効です"
else
  echo "⚠️ Discovery Engine API が無効です。有効化します"
  gcloud services enable discoveryengine.googleapis.com --project="$PROJECT_ID"
fi

# ② 自分に付いているロールを確認する（Gemini Enterprise Admin が必要）
ME="$(gcloud config get-value account 2>/dev/null)"
echo "--- ${ME} のロール ---"
gcloud projects get-iam-policy "$PROJECT_ID" \
  --flatten="bindings[].members" \
  --filter="bindings.members:user:${ME}" \
  --format="value(bindings.role)"

# ③ デプロイ済みの reasoningEngine（Agent Runtime）の一覧を確認する
#    ※ リージョンは M12 でデプロイしたものに合わせる
echo "--- reasoningEngines (us-central1) ---"
curl -s \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/us-central1/reasoningEngines" \
  | grep -E '"(name|displayName)"' || echo "（見つかりません）"
