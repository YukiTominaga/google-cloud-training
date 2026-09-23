# =====================================================================
# M4 Code 1 / Code 4. 関数が schema になる
# ---------------------------------------------------------------------
# ADK が Python 関数から自動生成する「tool の schema」を画面に出して
# 見せるためのスクリプトです（モデル呼び出しは行いません）。
#
# 実行方法（agents/ フォルダで）:
#   python -m m04_tools.show_schema
#
# 見せたいポイント
#   ・name        ← 関数名（ルール 1）
#   ・description ← docstring 全文（ルール 2）
#   ・type        ← 型ヒント（ルール 3）。型ヒントが無い bad() では
#                   "type" が出てこない ＝ モデルは何を渡せばよいか分からない
#   ・required    ← 既定値の無い引数だけが入る
# =====================================================================

import json

from google.adk.tools import FunctionTool


# ---------------------------------------------------------------------
# ✅ Code 1 の関数：型ヒントと docstring が揃っている
# ---------------------------------------------------------------------
def lookup_account(account_id: str, include_history: bool = False) -> dict:
    """顧客アカウントの現在の残高とステータスを返す。

    残高や支払いに関する質問に答える前に、これを使うこと。

    Args:
        account_id: 顧客アカウントの一意な ID。例: "A-1001"。
        include_history: True の場合、直近 3 件の支払いも返す。

    Returns:
        dict: 'status' は "success" または "error"。成功時は 'balance'（float）
              と 'account_status'（str）。エラー時は 'message'（str）に理由が入る。
    """
    ...


# ---------------------------------------------------------------------
# ❌ Code 4 の関数：型ヒントも docstring も無い
# ---------------------------------------------------------------------
def bad(id) -> dict:  # 型ヒントなし
    ...


def show(func) -> None:
    """FunctionTool で包み、モデルに渡される宣言（schema）を JSON で表示する。"""
    # FunctionTool(...) は tools=[func] と書いたときに ADK が内部で行う変換と同じ。
    # _get_declaration() は内部 API なので、講義での可視化用途に限って使う。
    declaration = FunctionTool(func)._get_declaration()
    print(f"----- {func.__name__} -----")
    print(json.dumps(declaration.model_dump(exclude_none=True), indent=2, ensure_ascii=False))
    print()


if __name__ == "__main__":
    show(lookup_account)  # properties に "type" が付き、required は account_id だけ
    show(bad)  # properties.id に "type" が無い ← ここを指し示す
