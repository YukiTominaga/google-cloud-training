"""image_edit_studio — Nano Banana 2 で画像を編集する応用アプリ。

adk web でユーザーが画像を添付し、「帽子を足して」「背景を広げて」のように指示すると、
ツールが Nano Banana 2（Gemini の画像モデル）で編集し、結果を **artifact** として返します。
adk web の画面でビフォー/アフターを確認できます。

このサンプルで学べる、ここまでの教材に無かった要素:
  - マルチモーダル入力（添付画像を `tool_context.user_content` から取得）
  - 画像生成 / 編集ツール（inpaint_image / outpaint_image）
  - artifact（生成画像を `save_artifact` で返し、adk web で表示）

実行:
    uv run adk web   # ドロップダウンで image_edit_studio を選び、画像を添付して指示する
"""

from __future__ import annotations

import os

from google.adk.agents import Agent

from .tools import inpaint_image, outpaint_image

# 推論（どちらのツールを使うか等の判断）に使うモデル。マルチモーダルで添付画像も読めます。
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

root_agent = Agent(
    name="image_edit_studio",
    model=MODEL,
    description="添付画像を編集（inpainting / outpainting）する画像スタジオ。",
    instruction=(
        "あなたは画像編集アシスタントです。ユーザーが添付した画像を編集します。"
        "画像の内側の追加・置換・削除など局所的な編集には inpaint_image を、"
        "画像の外側へシーンを広げる拡張には outpaint_image を使ってください。"
        "編集が終わったら、ツールが返した artifact 名をユーザーに伝えてください。"
        "画像が添付されていない場合は、画像を添付してから指示するよう促してください。"
    ),
    tools=[inpaint_image, outpaint_image],
)
