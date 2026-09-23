#!/usr/bin/env bash
# =====================================================================
# M13 素材 5. 権限まわりの 3 つの論点
# ---------------------------------------------------------------------
# ① OAuth：agent がユーザー本人の権限で外部サービス（Drive, Jira 等）に
#    アクセスする場合は、先に「認可リソース」を作り、登録時に紐づける。
#    （下の curl は概略。-d の中身は OAuth クライアントの設定になる）
# ② プロジェクトまたぎ：app（プロジェクト A）と reasoningEngine
#    （プロジェクト B）が別プロジェクトの場合、A 側のサービスエージェントに
#    B 側でロールを付与する必要がある。
#       プロジェクト A                    プロジェクト B
#       ┌────────────────────┐           ┌────────────────────┐
#       │ Gemini Enterprise  │  ← ロール │ Agent Runtime      │
#       │ app                │  付与が   │ reasoningEngine    │
#       └────────────────────┘  必要     └────────────────────┘
# ③ 共有先：個人 / メールグループ / identity pool / 組織全体
#    （③ は Gemini Enterprise の管理画面で設定する）
# =====================================================================
set -euo pipefail
: "${PROJECT_NUMBER:?PROJECT_NUMBER を設定してください}"
: "${LOCATION:=global}"
: "${AUTH_ID:=support-agent-oauth}"

# 認可リソースを作る（概略）
# リクエスト本文（OAuth クライアント ID・シークレット・認可／トークン URI など）は
# 講師ガイドでも「概略」扱い。項目名は Gemini Enterprise の Authorization
# リソースのドキュメントに従って oauth_config.json に書き、ここでは読み込むだけにする。
# （シークレットをスクリプトに直書きしないためにも、別ファイルに分けておく）
: "${OAUTH_CONFIG_FILE:=oauth_config.json}"
[ -f "$OAUTH_CONFIG_FILE" ] || { echo "${OAUTH_CONFIG_FILE} を用意してください"; exit 1; }

curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_NUMBER}/locations/${LOCATION}/authorizations?authorizationId=${AUTH_ID}" \
  -d @"${OAUTH_CONFIG_FILE}"   # { ... OAuth の設定 ... }
