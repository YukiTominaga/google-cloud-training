---
name: add-feature
description: "`/add-feature <機能の説明>` で呼ぶ。調査 → 仕様策定 → ユーザー承認 → 実装 → 検証 → レビュー → 評価 → ドキュメント更新までを、サブエージェントを順に起動して仕様駆動で進める。"
---

# add-feature

`/add-feature <機能の説明>` で新機能を仕様駆動で追加する。`specs/` が唯一の正であり、仕様にない振る舞いは追加しない。コマンドは uv 経由と `agents-cli eval` のみ。

## 手順

1. **調査（並列）**: `explorer` と `gcp-inspector` を同時に起動する。
   - explorer: 既存の仕様・ステップ定義のパターンと変更対象ファイルを調べさせる。
   - gcp-inspector: 必要な API やリソースの有無と、Given に使える実値を調べさせる。
2. **仕様策定と承認**: 両者の結果を `spec-writer` に渡し、`specs/<機能名>.md` と `tests/features/<機能名>.feature` を書かせる。Scenario 一覧と未確定事項をユーザーに提示し、**承認を待つ。承認前に実装へ進まない。**
3. **実装**: 承認後、Scenario を `implementer` に割り当てる。
   - 独立した Scenario は別の implementer で並列に実行する。
   - 同じファイルを触る Scenario は1つの implementer にまとめる。
   - 起動時のメッセージは必ず「`specs/<機能名>.md` の Scenario N を実装して」の形にする（自然言語の説明のみで起動しない）。
4. **検証とレビュー**: `spec-verifier` → `reviewer` の順に実行する。FAIL や high の指摘は該当 Scenario の implementer に差し戻し、再度 spec-verifier から実行する。
5. **評価**: `evaluator` に評価データセットとメトリクスを作らせて実行する。未達があれば原因に応じて implementer（実装）か evaluator（メトリクス説明）に戻す。
6. **ドキュメント**: `doc-writer` に README と `specs/` の「決定の記録」を更新させる。
7. **最終報告**: 次の表を1つにまとめ、どのサブエージェントが何をしたかを時系列で要約する。

| Scenario 番号 | 実装担当 | spec-verifier の結果 | reviewer の指摘数 | evaluator のスコア |
|---|---|---|---|---|

## 注意
- 仕様と異なる判断が必要になったら、コードより先に仕様を更新し、ユーザーに差分を提示する。
- `specs/` の Gherkin と `tests/features/` の `.feature` は同一文言を保つ。
- 完了条件: 全 Scenario が spec-verifier で PASS、reviewer に high なし、evaluator が目標スコア到達、README と仕様が最新。
