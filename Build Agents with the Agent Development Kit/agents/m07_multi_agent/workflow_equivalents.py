# =====================================================================
# M7 → M8 への橋渡し：3 テンプレートを Workflow で書き直すと？
# ---------------------------------------------------------------------
# 非推奨の 3 テンプレートが、ADK 2.0 の Workflow ではどう書けるかの
# 対応表です。詳しい説明は M8 で行います（adk web には読み込まれません）。
#
#   Sequential → edges のタプルにノードを並べるだけ
#                各ノードの戻り値が次のノードの入力に自動で渡る
#                （output_key / state を経由する必要すらない）
#   Parallel   → 同じソースから複数ノードへ辺を張る（fan-out）
#                合流は JoinNode（ブランチの出力をノード名キーでまとめる）
#   Loop       → グラフの back-edge でも書けるが「回数上限が無い」。
#                回数で確実に止めたいなら @node の dynamic workflow で
#                普通の Python の for ループを書く（下の例）
# =====================================================================

import os

from google.adk import Agent, Context, Workflow
from google.adk.workflow import JoinNode, node

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


def _agent(name: str, instruction: str) -> Agent:
    """グラフのノード用 Agent を作る小さなヘルパー。

    Workflow のノードとして使う Agent は mode="single_turn" を指定する
    （ADK 2.9.2 時点の正解。詳細は M8）。
    """
    return Agent(name=name, model=MODEL, instruction=instruction, mode="single_turn")


# ---------------------------------------------------------------------
# Sequential の置き換え：("START", a, b, c) と並べるだけ
# ---------------------------------------------------------------------
sequential_equivalent = Workflow(
    name="order_pipeline_wf",
    edges=[
        (
            "START",
            _agent("validate", "注文依頼（商品と数量）を正規化してください。"),
            _agent("pricing", "受け取った注文の価格を、1 個あたり 10 USD で計算してください。"),
            _agent("confirm", "受け取った内容について、短い注文確認文を書いてください。"),
        ),
    ],
)

# ---------------------------------------------------------------------
# Parallel の置き換え：fan-out ＋ JoinNode
# ---------------------------------------------------------------------
_inventory = _agent(
    "inventory", "商品の在庫があるかどうかを答えてください（在庫ありと仮定してよい）。"
)
_promotions = _agent(
    "promotions", "現在実施中のもっともらしいキャンペーンを 1 つ紹介してください。"
)
_join = JoinNode(name="join")
parallel_equivalent = Workflow(
    name="lookup_wf",
    edges=[
        ("START", _inventory),
        ("START", _promotions),
        (_inventory, _join),
        (_promotions, _join),
        (_join, _agent("gather", "受け取った入力を 1 つの返信にまとめてください。")),
    ],
)

# ---------------------------------------------------------------------
# Loop の置き換え：@node を付けた関数の中で for ループを書く
# ---------------------------------------------------------------------
# ctx.run_node(ノード, node_input=...) で、関数の中から別のノードを
# 動的に実行し、その結果を await で受け取れる。
# 回数上限（max_iterations 相当）は普通の range() で表現できる。
_drafter = _agent(
    "drafter",
    "受け取った苦情に対する、短く丁寧な返信を書いてください（既にあれば改善してください）。",
)
_reviewer = _agent(
    "reviewer",
    "受け取った返信案をレビューしてください。丁寧で 200 文字以内であれば 'APPROVED' とだけ返し、"
    "そうでなければフィードバックを 1 文で返してください。",
)

MAX_ITERATIONS = 5


@node(
    name="refine_loop", rerun_on_resume=True
)  # run_node を使うノードは rerun_on_resume=True が必須
async def refine_loop(ctx: Context, node_input: str) -> str:
    """draft → review を最大 MAX_ITERATIONS 回くり返す dynamic workflow。"""
    draft = await ctx.run_node(_drafter, node_input=node_input)
    for _ in range(MAX_ITERATIONS - 1):
        verdict = await ctx.run_node(_reviewer, node_input=draft)
        if "APPROVED" in str(verdict):
            break  # 脱出条件（LoopAgent の exit_loop に相当）
        draft = await ctx.run_node(_drafter, node_input=f"Draft: {draft}\nFeedback: {verdict}")
    return draft


loop_equivalent = Workflow(name="refine_wf", edges=[("START", refine_loop)])
