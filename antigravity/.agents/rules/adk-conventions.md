# ADK 実装規約

本プロジェクトにおける Google ADK（Python）を用いたエージェント実装および開発規約を定めます。

---

## 1. ADK ツール関数の書き方
- **型ヒントの徹底**: ツールのすべての引数と戻り値に型ヒントを必ず付与してください。
- **戻り値の辞書形式**: 戻り値は必ず dict を返し、`"status"` キーを含めてください。
  - 成功時: `{"status": "success", ...}`
  - 失敗時: `{"status": "error", "error": "<エラーメッセージ>", ...}`
- **例外の送出禁止**: 処理中の例外は必ず `try...except` で捕捉し、例外を外部へ投げずに `{"status": "error", "error": ...}` の形式で返却してください。
- **日本語 docstring とコメント**: docstring とコードコメントは日本語で記述し、関数の目的・引数・戻り値を明確にしてください。会話応答も日本語で行います。

```python
from typing import Any

def my_tool(param: str) -> dict[str, Any]:
    """ツールの処理概要（日本語）.

    Args:
        param: 引数の説明

    Returns:
        実行結果を含む dict（必ず status キーを含む）
    """
    try:
        # 処理ロジック
        return {"status": "success", "result": "..."}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

## 2. 外部プロセスの実行 (`subprocess`)
- `subprocess.run` 等で外部コマンドを呼び出す場合は、予期せぬハングアップを防ぐため必ず有限の `timeout`（秒単位）を指定してください。
- シェルインジェクション防止のため `shell=True` は使用せず、引数はリスト形式で渡してください。
- テスト（pytest）では実際の外部コマンドを実行せず、`monkeypatch` や `unittest.mock` を用いて確実にモックしてください。

## 3. 依存関係の追加・管理 (`uv`)
- パッケージの追加は必ず `uv` コマンド経由で行い、`pyproject.toml` や lock ファイルを手作業で直接編集してはなりません。
  - 通常依存の追加: `uv add <package>`
  - 開発用依存の追加: `uv add --dev <package>`
- 依存関係を追加または更新した場合は、該当する `specs/<機能名>.md` の「バージョン固定」セクションにも反映・更新してください。

## 4. ドキュメント同期
- `root_agent` に新規ツールを追加、または既存ツールのシグネチャ・仕様を変更した際は、必ず `README.md` のツール一覧および利用例を同期して更新してください。
