# =====================================================================
# M1 ― Agent Development Kit (ADK)
# Code 3. 最初の agent（このモジュールの本体）
# ---------------------------------------------------------------------
# ■ このファイルの位置づけ
#   コース全体で育てていく「注文サポート agent」の出発点です。
#   M1 では billing_agent を約 20 行で書きます。
#   → M4 で tool が増え、M5 で認可が入り、M7〜M8 でグラフに載り、
#     M9 で coordinator に束ねられ、M12〜M13 で社内に公開されます。
#
# ■ ディレクトリ構成（Code 2）
#   m01_adk/
#   ├── __init__.py   # from . import agent
#   ├── agent.py      # root_agent をここに定義（このファイル）
#   └── .env          # API キー（本サンプルでは agents/.env を共有）
#
# ■ 4 コンポーネントとの対応
#   Agent  … 下の Agent(...) そのもの
#   Model  … model=MODEL の文字列 1 個（既定 "gemini-flash-latest"、.env の GEMINI_MODEL で差し替え）
#   Tools  … tools=[lookup_account]
#   Runner … このファイルには「いない」。adk web / adk run を
#            実行した瞬間に ADK が裏で作る。自分では書かない。
#
# ■ 動かし方（Code 5）
#   cd agents
#   adk web            # ブラウザ UI（http://localhost:8000）。まずはこちら
#   adk run m01_adk    # ターミナルの REPL
#
# ■ 試すプロンプト（adk web / adk run で入力）
#   1. 「A-1001 の残高を教えて」
#      → lookup_account(account_id="A-1001") が呼ばれ、残高 128.50 と状態 active が返る
#   2. 「A-1002 のアカウントの状態は？」
#      → lookup_account が呼ばれ、残高 0.0 と状態 suspended が返る
#   3. 「A-9999 の残高は？」
#      → lookup_account が status "error" を返す。数字をでっち上げずに
#        エラーを伝えるか（instruction の最後の 1 文の効果）を確認する
# =====================================================================

import os

from google.adk import Agent

# .env の GEMINI_MODEL で差し替え可能
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")


# ---------------------------------------------------------------------
# Tool：tool の正体は「ただの Python 関数」
# ---------------------------------------------------------------------
# クラス継承もデコレータも不要。書いて tools=[...] に渡すだけです。
# ただし ADK は次の 3 つを読んで tool のスキーマを自動生成します。
#   1. 関数名        → tool の名前
#   2. docstring     → tool の説明（いつ使うか・引数・戻り値の意味）
#   3. 型ヒント      → 引数の型
# つまり docstring と型ヒントは「人間向けのコメント」ではなく
# 「モデル向けの仕様書」です（詳しくは M4）。
def lookup_account(account_id: str) -> dict:
    """指定したアカウントの現在の残高とステータスを返す。

    Args:
        account_id: 顧客アカウントの一意な ID。

    Returns:
        dict: 'status'（"success" または "error"）。成功時は
              'balance'（float）と 'account_status'（str）も含む。
    """
    # 本物の DB の代わりのダミーデータ
    accounts = {
        "A-1001": {"balance": 128.50, "account_status": "active"},
        "A-1002": {"balance": 0.0, "account_status": "suspended"},
    }

    # tool は例外を投げずに「エラーも戻り値として返す」のが ADK の定石。
    # 例外だと実行がそこで止まるが、dict で返せばモデルが
    # 「見つからなかったのでユーザーに伝える」と判断できる。
    if account_id not in accounts:
        return {"status": "error", "message": f"Account {account_id} not found."}

    # 成功時も必ず status を持たせる（モデルが結果を解釈しやすくなる）
    return {"status": "success", **accounts[account_id]}


# ---------------------------------------------------------------------
# Agent：変数名は必ず root_agent
# ---------------------------------------------------------------------
# adk web / adk run は agent.py の中の「root_agent」という
# モジュールレベル変数を探しに行きます。名前が違うと見つかりません。
# この約束事は M13 まで一度も変わりません。
root_agent = Agent(
    # name：agent の識別子。ログ・トレースにこの名前で出る。
    #       複数 agent を並べたとき（M7）に「誰が喋ったか」を見分ける鍵。
    name="billing_agent",
    # model：文字列 1 個。ここを差し替えるだけで推論エンジンが入れ替わる
    #        （tool も instruction も変えなくてよい = model-agnostic）。
    #        本番では "gemini-3.5-flash" のような固定バージョン指定を推奨。
    model=MODEL,
    # description：外から見た「看板」。いまはメモに見えるが、M7 で
    #              親 agent が「どの子に渡すか」を判断する材料になる。
    description="Answers billing and payment questions.",
    # instruction：モデルへの指示。最後の 1 文のように
    #              「失敗したときの振る舞い」まで書くのが作法。
    #              書かないとモデルは平気で数字をでっち上げる。
    instruction=(
        "あなたは請求担当のスペシャリストです。アカウント残高、支払い履歴、"
        "請求書に関する質問に答えてください。"
        "アカウント情報の取得には lookup_account tool を使ってください。"
        "tool がエラーを返した場合は、推測で答えず、エラーだったことを伝えてください。"
    ),
    # tools：関数オブジェクトをそのまま渡す（呼び出し () は付けない）
    tools=[lookup_account],
)
