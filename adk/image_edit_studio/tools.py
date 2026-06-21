"""image_edit_studio のツール。

Nano Banana 2（Gemini の画像モデル）で、ユーザーが adk web で添付した画像を編集します。

- inpaint_image  … 画像の内側を局所的に編集（追加 / 置換 / 削除）
- outpaint_image … 画像の外側へシーンを自然に拡張

編集結果は **artifact** として保存し、adk web 上でビフォー/アフターを確認できます。

ポイント:
- 添付画像は `tool_context.user_content` の `inline_data` Part として届きます（マルチモーダル入力）。
- 画像モデルの応答は `candidates[0].content.parts[].inline_data` に画像バイトが入ります。
- 想定エラー（画像未添付 / 画像が返らない）は error dict を返し、API 例外は素通しさせます
  （広い `except` は書きません。retry / HITL を壊さないため）。
"""

from __future__ import annotations

import os

from google import genai
from google.adk.tools.tool_context import ToolContext
from google.genai import types

# 画像編集に使うモデル（Nano Banana 2）。.env の IMAGE_MODEL で差し替え可能です。
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gemini-3.1-flash-image")


def _latest_uploaded_image(tool_context: ToolContext) -> types.Part | None:
    """現在のユーザーメッセージに添付された最新の画像 Part を返します（無ければ None）。"""
    content = tool_context.user_content
    parts = content.parts if content and content.parts else []
    for part in reversed(parts):
        inline = getattr(part, "inline_data", None)
        if inline and inline.data and (inline.mime_type or "").startswith("image/"):
            return part
    return None


def _extract_image(response: types.GenerateContentResponse) -> tuple[bytes, str] | None:
    """画像モデルの応答から、生成画像のバイトと mime タイプを取り出します。"""
    candidates = response.candidates or []
    if not candidates or not candidates[0].content:
        return None
    for part in candidates[0].content.parts or []:
        inline = getattr(part, "inline_data", None)
        if inline and inline.data:
            return inline.data, inline.mime_type or "image/png"
    return None


async def _edit(
    image_part: types.Part, instruction: str, *, outpaint: bool
) -> tuple[bytes, str] | None:
    """画像モデルを呼び、編集後の画像（バイト, mime）を返します。失敗時は None。"""
    if outpaint:
        prompt = (
            "次の画像の外側へ、シーンを自然に拡張（outpainting）してください。"
            "元の被写体や画風は保ったまま、周囲を描き足します。指示: " + instruction
        )
    else:
        prompt = (
            "次の画像を、指示に従って局所的に編集（inpainting）してください。"
            "指示した箇所以外はできるだけ変えないでください。指示: " + instruction
        )
    # genai.Client() は .env の GOOGLE_GENAI_USE_VERTEXAI / PROJECT / LOCATION を読み、
    # Vertex AI + ADC で動作します。非同期 API (client.aio) を使い event loop をブロックしません。
    client = genai.Client()
    response = await client.aio.models.generate_content(
        model=IMAGE_MODEL,
        contents=[image_part, types.Part(text=prompt)],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    return _extract_image(response)


async def _run_edit(
    instruction: str, tool_context: ToolContext, *, outpaint: bool, filename: str
) -> dict:
    """添付画像を編集し、結果を artifact として保存する共通処理。"""
    image_part = _latest_uploaded_image(tool_context)
    if image_part is None:
        return {
            "status": "error",
            "error_message": "編集する画像が見つかりません。画像を添付してから指示してください。",
        }
    result = await _edit(image_part, instruction, outpaint=outpaint)
    if result is None:
        return {
            "status": "error",
            "error_message": "画像が生成されませんでした。指示を変えて再試行してください。",
        }
    data, mime = result
    # 生成画像を artifact として保存すると、adk web の画面に表示されます。
    await tool_context.save_artifact(filename, types.Part.from_bytes(data=data, mime_type=mime))
    return {
        "status": "success",
        "artifact": filename,
        "note": f"編集結果を {filename} として保存しました。adk web の画面で確認できます。",
    }


async def inpaint_image(instruction: str, tool_context: ToolContext) -> dict:
    """添付画像の内側を局所的に編集します（inpainting: 追加 / 置換 / 削除）。

    Args:
        instruction: 編集内容の指示（例: "猫に赤い帽子を追加して", "背景の看板を消して"）。

    Returns:
        status と、成功時は artifact（保存した画像ファイル名）・note、
        失敗時は error_message を含む dict。
    """
    return await _run_edit(
        instruction, tool_context, outpaint=False, filename="inpaint_result.png"
    )


async def outpaint_image(instruction: str, tool_context: ToolContext) -> dict:
    """添付画像の外側へシーンを拡張します（outpainting）。

    Args:
        instruction: 拡張の方向や内容の指示（例: "背景を左右に広げて", "上に空を描き足して"）。

    Returns:
        status と、成功時は artifact（保存した画像ファイル名）・note、
        失敗時は error_message を含む dict。
    """
    return await _run_edit(
        instruction, tool_context, outpaint=True, filename="outpaint_result.png"
    )
