"""step_01_basic_agent — 最小構成の ADK エージェント。

このサンプルは ADK の「最小単位」を示します。ツール (tool) もコールバック
(callback) もなく、`Agent` を 1 つ定義するだけです。ここで押さえる点は次の 3 つです。

1. `root_agent` という変数名
   - ADK の CLI (`adk web` / `adk run`) は、ディレクトリ内から `root_agent`
     という名前の変数を自動で探してロードします。名前は必ず `root_agent` にします。

2. `description` と `instruction` の違い
   - `instruction`  … このエージェント自身への指示。振る舞い (口調・手順・制約) を決めます。
   - `description`  … 「このエージェントが何をする人か」の短い説明。単体では効果が見えにくい
     ですが、マルチエージェント (step_04_multi_agent) で親が「どの子に転送するか」を
     判断する材料になります。早い段階から書く習慣をつけます。

3. `generate_content_config`
   - モデルの生成パラメータ (temperature など) を `google.genai.types` で指定します。

対話方法 (詳細は README.md):
    uv run adk web              # ブラウザ UI。ドロップダウンで step_01_basic_agent を選ぶ
    uv run adk run step_01_basic_agent   # ターミナルで対話
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from google.genai import types

# モデル名はハードコードしません。リポジトリ直下の .env の GEMINI_MODEL で
# 全サンプルを一括して差し替えられます。未設定時の既定は gemini-3.5-flash です。
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

# `root_agent` という変数名が ADK の規約です (CLI がこの名前を探します)。
root_agent = Agent(
    name="basic_agent",
    model=MODEL,
    # description: このエージェントの役割を一言で。マルチエージェント時の転送判断に効きます。
    description="ADK の基本を学ぶための、ツールを持たない最小の対話エージェント。",
    # instruction: 振る舞いを決める指示。ここを書き換えると応答の性格が変わります。
    instruction=(
        "あなたは ADK の学習を助ける親切な日本語アシスタントです。"
        "専門用語はやさしく説明し、回答は簡潔にまとめてください。"
        "ツールは持っていないため、一般的な知識の範囲で答えてください。"
    ),
    # generate_content_config: モデルの生成パラメータ。
    # temperature を低めにすると回答が安定し、教材デモで再現しやすくなります。
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=1024,
    ),
)
