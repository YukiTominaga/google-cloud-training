#!/usr/bin/env bash
# =====================================================================
# M11 Code 3. adk web をプラットフォームのサービスに繋ぐ
# ---------------------------------------------------------------------
# コードを書かずに、adk web の起動オプションだけで
# session / memory / artifact の保存先をプラットフォームに切り替えられる。
# 1234567890 は Agent Runtime の reasoningEngine の数値 ID（M12 で得られる）。
# agents/ フォルダで実行する。
# =====================================================================

# 誤って丸ごと実行しないためのガード
echo "このファイルはコマンド集です。必要な行をコピーして実行してください。"; exit 0

adk web . \
  --session_service_uri="agentengine://1234567890" \
  --memory_service_uri="agentengine://1234567890" \
  --artifact_service_uri="gs://my-artifact-bucket"
