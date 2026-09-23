#!/usr/bin/env bash
# =====================================================================
# M12 Code 2 / Code 3. 経路 A ― ADK CLI でデプロイする
# ---------------------------------------------------------------------
# 前提
#   gcloud auth application-default login
#   export PROJECT_ID=my-project
#   export LOCATION_ID=us-central1
# 実行場所：agents/ フォルダ（最後の引数が agent フォルダ名）
#   bash m12_deploy/deploy_adk_cli.sh
# =====================================================================
set -euo pipefail   # どこかで失敗したらそこで止める

: "${PROJECT_ID:?PROJECT_ID を設定してください}"
: "${LOCATION_ID:=us-central1}"

# ---------------------------------------------------------------------
# Code 3. 非推奨フラグ（講師から先に言う）
# ---------------------------------------------------------------------
#   adk deploy agent_engine --help で確認すると、
#   --staging_bucket : Deprecated. This argument is no longer required or used.
#
#   非推奨：--staging_bucket / --env_file / --requirements_file /
#           --adk_app / --adk_app_object / --trace_to_cloud /
#           --absolutize_imports / --validate-agent-import
#   → 設定は agent フォルダの .agent_engine_config.json にまとめる
#     （CLI フラグと両方あるときは CLI フラグが優先）
#   追加されたオプション例：--otel_to_cloud（--trace_to_cloud の後継）/
#     --worker_pool（VPC-SC・プライベートネットワークでは必須）/
#     --agent_engine_config_file / --extra_packages / --adk_version
#
# ※ スライドにある --staging_bucket は付けない。
#   （SDK の config キーとしての staging_bucket は現役。deploy_sdk.py 参照）

# ---------------------------------------------------------------------
# Code 2. デプロイ
# ---------------------------------------------------------------------
adk deploy agent_engine \
    --project="$PROJECT_ID" \
    --region="$LOCATION_ID" \
    --display_name="Support Coordinator" \
    m12_deploy

# 成功すると最後に次の形のリソース名が表示される。RESOURCE_ID（末尾の数値）を
# 控えておく → M11 の agentengine://RESOURCE_ID、M13 の登録で使う。
#   projects/PROJECT_ID/locations/LOCATION/reasoningEngines/RESOURCE_ID
