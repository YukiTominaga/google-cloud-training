# =====================================================================
# M10 Code 2. 非構造化データの grounding ― 2 つの tool
# ---------------------------------------------------------------------
# grounding ＝ モデルの「記憶」ではなく、外部の情報源に基づいて答えさせること。
# 非構造化データ（Web ページ・社内文書）向けの組み込み tool は 2 つ。
#
#   google_search       … 公開 Web の最新情報（ニュース、運送会社の障害情報など）
#   VertexAiSearchTool  … 社内文書（規程、マニュアル、FAQ）を入れたデータストア
#
# ※ サービス名は「Agent Search on Gemini Enterprise Agent Platform」に改称済み。
#   Python のクラス名は VertexAiSearchTool のまま（ドキュメント検索時は新旧両方で）。
# adk web には読み込まれません（講義で見せるための例）。
# =====================================================================

import os

from google.adk import Agent
from google.adk.tools import VertexAiSearchTool, google_search

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

# ---------------------------------------------------------------------
# ① 公開 Web に grounding する
# ---------------------------------------------------------------------
research_agent = Agent(
    name="research_agent",
    model=MODEL,
    instruction="Google 検索を使って質問に答えてください。必ず出典を示してください。",
    tools=[google_search],  # 組み込み tool はインスタンスをそのまま渡す
)

# ---------------------------------------------------------------------
# ② 社内文書に grounding する
# ---------------------------------------------------------------------
# データストア ID はフルパスで指定する。PROJECT / DATASTORE を置き換える。
DATASTORE_ID = (
    "projects/PROJECT/locations/global/collections/default_collection/dataStores/DATASTORE"
)

internal_search_agent = Agent(
    name="internal_search_agent",
    model=MODEL,
    instruction="社内文書検索を使って答えてください。必ず出典を示してください。",
    tools=[VertexAiSearchTool(data_store_id=DATASTORE_ID)],
)
