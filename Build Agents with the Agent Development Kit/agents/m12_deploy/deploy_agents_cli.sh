#!/usr/bin/env bash
# =====================================================================
# M12 Code 4. 経路 B ― Agents CLI
# ---------------------------------------------------------------------
# Agents CLI は「プロジェクトの雛形作成 → ローカル実行 → 評価 →
# デプロイ構成の追加 → デプロイ」までを一続きで扱うツール。
# ADK CLI が「今ある agent フォルダを載せる」道具なのに対し、
# Agents CLI は「本番運用の枠組みごと作る」道具、と対比して説明する。
# 1 行ずつ手で実行する想定のコマンド集。
# =====================================================================

# 誤って丸ごと実行しないためのガード（playground は起動したまま戻らないため）
echo "このファイルはコマンド集です。必要な行をコピーして実行してください。"; exit 0

# セットアップ（uvx が推奨）
uvx google-agents-cli setup

# プロジェクトを作る（--prototype：最小構成の雛形。--yes：対話をスキップ）
agents-cli create support-agent --prototype --yes
cd support-agent && agents-cli install

# ローカルで動かす（http://localhost:8080、ホットリロード付き）
agents-cli playground

# 評価を回す
agents-cli eval run

# デプロイ先の構成を足す（ここでは Cloud Run）
agents-cli scaffold enhance --deployment-target cloud_run

# デプロイ
agents-cli deploy
