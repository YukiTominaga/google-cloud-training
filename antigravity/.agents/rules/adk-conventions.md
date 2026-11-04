# ADK 実装規約

本プロジェクトにおける Google ADK（Python）を用いたエージェント実装および開発規約を定めます。

## 1. ADK ツール関数の実装ルール
- **型ヒントの徹底**: すべてのツールの引数および戻り値に型ヒントを必ず付与してください。
- **戻り値のフォーマット**: 戻り値は必ず辞書（`dict[str, Any]`）形式とし、`"status"` キーを含めてください。
  - 成功時: `{"status": "success", ...}`
  - 失敗時: `{"status": "error", "error": "<エラーメッセージ>", ...}`
- **docstring とコメント**: 日本語で簡潔かつ正確に記述し、関数の目的・引数・戻り値を明記してください。

```python
def my_tool(param: str) -> dict[str, Any]:
    """ツールの説明（日本語）.

    Args:
        param: 引数の説明

    Returns:
        実行結果を含む dict
    """
    try:
        # 処理
        return {"status": "success", "result": "..."}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

## 2. 外部プロセスの実行 (subprocess)
- `subprocess.run` 等で外部コマンドを実行する場合は、予期せぬハングアップを防ぐため必ず `timeout` 引数（秒単位）を指定してください。
- ユニットテスト（pytest）では実際の外部コマンドを呼び出さず、`monkeypatch` や `unittest.mock` を用いて確実にモックしてください。

## 3. 依存関係の管理 (uv)
- パッケージの追加・更新・削除は必ず `uv` コマンドを使用してください。
  - 本番依存の追加: `uv add <package>`
  - 開発用依存の追加: `uv add --dev <package>`
- `pyproject.toml` や lock ファイルを手作業で直接編集してはなりません。

## 4. ドキュメント同期
- `root_agent` に新規ツールを追加、または既存ツールの仕様を変更した際は、必ず `README.md` のツール一覧および利用例を同期して更新してください。
