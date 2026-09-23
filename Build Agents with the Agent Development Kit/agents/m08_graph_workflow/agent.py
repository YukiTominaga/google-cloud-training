# =====================================================================
# M8 ― ADK 2.0 Graph Workflow
# Code 6. 通し題材 ― サポート workflow を組み立てる
# ---------------------------------------------------------------------
# ■ 前回（M7）から引き継ぐもの
#   billing / shipping / returns の 3 体の specialist。
# ■ 今回足すもの
#   非推奨になったテンプレート agent の代わりに、Workflow グラフに載せる。
#     ・条件分岐（router が route を返す）       … Code 2
#     ・想定外ラベルの受け皿 DEFAULT_ROUTE       … Code 3
#     ・並列 fan-out と JoinNode での合流        … Code 3 / Code 4
#     ・node 間のデータの流れ（Pydantic）        … Code 5
#   Code 1〜5 の単独の例は examples.py にあります。
#
# ■ 完成形のグラフ
#                                  ┌──▶ billing_gate  (→ billing_agent)  ─┐
#  START ─▶ classifier ─▶ router() ─┼──▶ shipping_gate (→ shipping_agent) ─┼──▶ join ─▶ synthesizer
#           [LLM]          [関数]    ├──▶ returns_gate  (→ returns_agent)  ─┘ (JoinNode)  [LLM]
#                                  └──▶ fallback_agent（どれにも当たらないとき）
#  ※ gate は「担当カテゴリなら specialist を呼び、担当外なら "N/A" を返す」関数ノード。
#    ガイドの書き方から変えた理由は router の下のコメントを参照。
#
# ■ 覚えておくこと
#   ・END ノードは存在しない。出ていく辺の無いノードに着いたら終了。
#   ・グラフの循環（back-edge）には自動の上限が無い。
#   ・ノードの中で広い except Exception を書くと、ADK の自動リトライが効かなくなる。
#   ・ADK 2.9.0 以降、resume 時に失敗ノードは「再実行」される。
#     返品登録・決済のような副作用のあるノードは冪等に書くこと。
# =====================================================================

import os

from google.adk import Agent, Context, Event, Workflow
from google.adk.workflow import DEFAULT_ROUTE, JoinNode, node
from pydantic import BaseModel, Field

from .specialists import billing_agent, returns_agent, shipping_agent

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


# ---------------------------------------------------------------------
# node 間で受け渡すデータの「型」（Code 5）
# ---------------------------------------------------------------------
# classifier の output_schema にすると、classifier の出力がこの形の JSON になり、
# それが辺に沿って router の node_input に渡る。
class Ticket(BaseModel):
    categories: str = Field(
        description='Comma-separated labels from BILLING, SHIPPING, RETURNS, e.g. "BILLING,SHIPPING".'
    )
    order_id: str = Field(description="The order or account ID mentioned, or an empty string.")


# ---------------------------------------------------------------------
# [LLM ノード] classifier：メッセージを分類し、ID を抜き出す
# ---------------------------------------------------------------------
classifier = Agent(
    name="classifier",
    model=MODEL,
    instruction=(
        "顧客のメッセージを読んでください。該当するカテゴリを BILLING, SHIPPING, "
        "RETURNS の中からカンマ区切りのリストで出力し、注文 ID が書かれていれば"
        "その ID も出力してください（書かれていなければ空文字列）。"
    ),
    output_schema=Ticket,
    mode="single_turn",  # ← グラフ内の Agent は必ず single_turn（講師から必ず言う 1 行）
)


# ---------------------------------------------------------------------
# [関数ノード] router：分類結果を route シグナルに変換する
# ---------------------------------------------------------------------
# ・普通の Python 関数がそのままノードになる（LLM を使わない＝速い・安い・確実）
# ・Event(route=...) の値が、次の辺の dict のキーと照合される
# ・output=... に渡した値が、発火した先のノードの入力になる
def _to_ticket(value: Ticket | dict) -> Ticket:
    """前段の出力が dict で届く場合にも備えて、Ticket に揃える。"""
    return value if isinstance(value, Ticket) else Ticket.model_validate(value)


def _categories(ticket: Ticket) -> set[str]:
    return {c.strip().upper() for c in ticket.categories.split(",") if c.strip()}


KNOWN_CATEGORIES = {"BILLING", "SHIPPING", "RETURNS"}


def router(node_input: Ticket | dict):
    """分類結果を route シグナルに変換する。

    1 つでも既知のカテゴリがあれば "SUPPORT"（3 つの gate へ fan-out）、
    無ければ DEFAULT_ROUTE（fallback_agent）へ。
    """
    ticket = _to_ticket(node_input)
    route = "SUPPORT" if _categories(ticket) & KNOWN_CATEGORIES else DEFAULT_ROUTE
    return Event(route=route, output=ticket)


# ---------------------------------------------------------------------
# [関数ノード] gate：該当カテゴリのときだけ specialist を呼ぶ
# ---------------------------------------------------------------------
# ⚠️ 講師ガイド Code 6 からの変更点（google-adk 2.9.2 で動作確認済みの挙動）
#   ガイドの書き方（router が Event(route=["BILLING", "SHIPPING"]) を返し、
#   発火した specialist だけが JoinNode に合流する）だと、
#   JoinNode は「つながっている前段ノードが“すべて”完了する」まで待つため、
#   3 つのうち一部しか発火しなかった場合に join が永遠に発火せず、
#   synthesizer が実行されない（3 カテゴリ全部に該当したときしか合流しない）。
#
#   そこで「3 つの gate には常に fan-out し、各 gate が
#   “自分の担当か” を判定して、担当なら specialist を呼び、
#   担当でなければ LLM を呼ばずに "N/A" を返す」形にしている。
#   → JoinNode には必ず 3 つの結果が揃い、無駄な LLM 呼び出しも発生しない。
#
#   ctx.run_node(...) は関数ノードの中から別のノード（ここでは Agent）を
#   動的に実行して結果を受け取る API。これを使うノードには
#   rerun_on_resume=True が必須（中断→再開時に親ノードごと再実行されるため）。
def _make_gate(category: str, specialist: Agent):
    @node(name=f"{category.lower()}_gate", rerun_on_resume=True)
    async def gate(ctx: Context, node_input: Ticket | dict):
        ticket = _to_ticket(node_input)
        if category not in _categories(ticket):
            return "N/A"  # 担当外：LLM を呼ばずに即終了
        # 担当：specialist を動的に実行し、その出力をこの gate の出力にする
        return await ctx.run_node(specialist, node_input=ticket)

    return gate


billing_gate = _make_gate("BILLING", billing_agent)
shipping_gate = _make_gate("SHIPPING", shipping_agent)
returns_gate = _make_gate("RETURNS", returns_agent)


# ---------------------------------------------------------------------
# [LLM ノード] fallback_agent：どの分類にも当たらなかったときの受け皿
# ---------------------------------------------------------------------
fallback_agent = Agent(
    name="fallback_agent",
    model=MODEL,
    description="Handles messages that do not fit any specialist category.",
    instruction="お詫びを述べ、質問を言い換えてもらうよう顧客にお願いしてください。",
    mode="single_turn",
)


# ---------------------------------------------------------------------
# [LLM ノード] synthesizer：JoinNode がまとめた各ブランチの出力を 1 つの返答にする
# ---------------------------------------------------------------------
# JoinNode は {"billing_gate": ..., "shipping_gate": ...} のように
# 「ノード名をキーにしたレコード」を作って次へ渡す。
# M7 のように output_key を揃えておく設計は不要になった。
synthesizer = Agent(
    name="synthesizer",
    model=MODEL,
    instruction=(
        "受け取った specialist の回答を、顧客への 1 つの返信にまとめてください。"
        '"N/A" の回答は無視してください。'
        "同じ情報を繰り返さないでください。"
    ),
    mode="single_turn",
)

# 合流点。発火したブランチがすべて終わるのを待ってから次へ進む
join = JoinNode(name="join")


# ---------------------------------------------------------------------
# グラフ本体：edges に「辺」を並べるだけ
# ---------------------------------------------------------------------
# ("START", a, b)          … START → a → b の逐次チェーン
# (router, {"X": n1, ...}) … router の route が "X" なら n1 へ（条件分岐）
# (a, join)                … a の出力を join へ（合流）
root_agent = Workflow(
    name="support_workflow",
    max_concurrency=3,  # 同時に走らせるノード数の上限（2.9.2 のフィールド。将来変更の可能性あり）
    edges=[
        ("START", classifier, router),
        # 条件分岐：既知カテゴリがあれば 3 つの gate へ、無ければ fallback へ
        (router, {"SUPPORT": billing_gate, DEFAULT_ROUTE: fallback_agent}),
        (router, {"SUPPORT": shipping_gate}),
        (router, {"SUPPORT": returns_gate}),
        # 合流：3 つの gate が揃ったら join が発火する
        (billing_gate, join),
        (shipping_gate, join),
        (returns_gate, join),
        (join, synthesizer),
        # fallback_agent からは辺を出さない → そこで終了（END ノードは無い）
    ],
)
