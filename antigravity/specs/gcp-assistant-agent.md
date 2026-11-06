# 仕様書: gcp_assistant ADK エージェント本体

## 1. 背景

Google Cloud 研修受講者が Google ADK（`google-adk`）によるカスタムエージェント開発を学習・実践するためのベースラインとして、エージェント本体（`root_agent`）の安全かつ標準的な構成が必要である。

ADK 2.0 では、複数のエージェントや処理ステップを明示的なグラフ構造でオーケストレーションする Graph API（`Workflow`）が提供されている。ADK Web（`uv run adk web`）によるローカル対話実行や、`agents-cli eval` による品質評価を行うため、`gcp_assistant/agent.py` にエントリーポイントとなる `root_agent`（`Workflow`）を定義し、`gcp_assistant/__init__.py` からインポート可能にする必要がある。

本エージェントは Google Cloud 環境の安全な調査・支援を担当するため、不用意なリソース変更や機密情報の漏洩を防ぐ厳格なシステム指示（instruction）を備えた `LlmAgent` ノード（`gcp_assistant_node`）をグラフに組み込み、現在のアクティブな GCP プロジェクト ID を安全に特定するツール（`get_current_gcp_project`）と連携して動作する。使用するモデルは `"gemini-4-argon"` に統一する。

## 2. 技術設計

### モジュール配置と公開シンボル

- `gcp_assistant/agent.py`:
  - `root_agent: Workflow`: ADK Web や評価ツールが参照する既定のエージェントインスタンス（`google.adk.workflow.Workflow`）。
  - `create_gcp_assistant_agent(model: str | None = None) -> Workflow`: `Workflow` インスタンスを生成するファクトリ関数。
  - `get_agent_info() -> dict[str, Any]`: エージェントの構成情報を取得・検証するための辞書返却関数（ADK 規約準拠）。
- `gcp_assistant/__init__.py`:
  - `root_agent`、`create_gcp_assistant_agent`、`get_agent_info` をエクスポートし、パッケージトップレベルから利用可能にする。

### ワークフローグラフ構成 (`Workflow` + `LlmAgent`)

- **ワークフロー名 (`name`)**: `"gcp_assistant"`（型: `google.adk.workflow.Workflow`）
- **内包ノード (`LlmAgent`)**:
  - **ノード名 (`name`)**: `"gcp_assistant_node"`（型: `google.adk.agents.LlmAgent`）
  - **モデル名 (`model`)**: `"gemini-4-argon"`（固定・既定値）
  - **登録ツール (`tools`)**: `[get_current_gcp_project]`
  - **システム指示 (`instruction`)**:
    以下の原則を明示的に含む日本語プロンプトとする：
    1. **プロジェクト特定**: GCP プロジェクト ID を確認・特定する際は、推測を行わず必ず登録された `get_current_gcp_project` ツールを使用すること。
    2. **読み取り専用の原則**: リソースの調査・確認など読み取り専用（read-only）の操作のみを行い、リソースの作成・変更・削除等の変更系操作は一切行わないこと。
    3. **機密情報の秘匿**: アクセストークン、ID トークン、サービスアカウント秘密鍵、API キー等の機密情報を会話ログや出力に含めないこと。
- **グラフエッジ (`edges`)**:
  - `edges=[("START", llm_node)]`
  - `Workflow` 初期化時にグラフが自動コンパイルされ、開始点 `"START"` から `"gcp_assistant_node"` へ接続される。

### エージェントファクトリ (`create_gcp_assistant_agent`)

- **シグネチャ**:
  ```python
  def create_gcp_assistant_agent(model: str | None = None) -> Workflow:
      """ADK 2.0 Graph API (Workflow) による gcp_assistant インスタンスを生成する。"""
  ```
- **振る舞い**:
  - `model` に文字列が渡された場合、前後の空白を除去（strip）してモデル名として採用する（例: `"  gemini-4-argon  "` が渡された場合は `"gemini-4-argon"` を設定）。
  - `model` が `None`、空文字（`""`）、または空白文字のみ（例: `"   "`）の場合は、既定モデル `"gemini-4-argon"` にフォールバックする。
  - 指定またはフォールバックされたモデル名（`"gemini-4-argon"`）、`tools=[get_current_gcp_project]`、および規定の `instruction` を持つ `LlmAgent(name="gcp_assistant_node", ...)` を生成する。
  - そのノードを `edges=[("START", llm_node)]` で接続した `Workflow(name="gcp_assistant", ...)` を生成して返却する。

### 構成情報取得関数 (`get_agent_info`)

- **シグネチャ**:
  ```python
  def get_agent_info() -> dict[str, Any]:
      """エージェントの構成情報辞書を取得する。"""
  ```
- **戻り値**:
  - **成功時**:
    ```python
    {
        "status": "success",
        "name": "gcp_assistant",
        "agent_type": "Workflow",
        "node_name": "gcp_assistant_node",
        "model": "gemini-4-argon",
        "tools": ["get_current_gcp_project"],
        "edges": [("START", "gcp_assistant_node")],
        "instruction": "<システム指示文字列>",
    }
    ```
  - **失敗時**:
    ```python
    {
        "status": "error",
        "error": "<エラーメッセージ>",
    }
    ```

### 失敗時の振る舞い

1. **ツールの失敗伝播**:
   - ツール `get_current_gcp_project` がエラー（`{"status": "error", "error": "<詳細>"}`）を返した場合、エージェントはツールのエラー結果を正しく認識し、プロジェクトが未設定または取得不能である旨を伝播する。
2. **モデル引数の異常値**:
   - 空文字や空白文字列に対して例外を送出せず、既定モデル `"gemini-4-argon"` へ安全にフォールバックする。

### 呼び出す外部コマンド

- エージェント自身は直接外部コマンドを実行しない。
- エージェントにバインドされた `get_current_gcp_project` ツール経由で `["gcloud", "config", "get-value", "project"]` のみを呼び出す。

### セキュリティ制約

1. **最小権限・読み取り専用**:
   - システム指示（instruction）によりリソース変更・作成・削除の禁止を徹底する。
2. **安全なプロセス実行**:
   - バインドされるツールは `shell=False` かつ有限タイムアウト（5秒）で `gcloud` コマンドを実行する。
3. **機密情報の保護**:
   - システム指示においてトークンや秘密鍵の出力を明示的に禁止する。

## 3. バージョン固定

| パッケージ / ツール | バージョン | 備考 |
| :--- | :--- | :--- |
| **Python** | `3.11.18` | ランタイム (>=3.11) |
| **google-adk** | `2.13.0` | Google Agent Development Kit |
| **pytest-bdd** | `9.0.1` | 仕様駆動テスト（BDD）フレームワーク |
| **pytest** | `9.2.0` | テストランナー |
| **ruff** | `0.17.3` | Linter / Formatter |

## 4. シナリオ (Gherkin)

```gherkin
Feature: GCP Assistant Agent
  As a Google Cloud developer
  I want a root AI assistant configured with safe GCP project inspection capabilities
  So that I can interactively inspect my Google Cloud environment securely

  Scenario 1: Verify root workflow agent configuration with default parameters
    Given the gcp_assistant agent module is loaded
    When root_agent is inspected
    Then the agent name should be "gcp_assistant"
    And the agent type should be "Workflow"
    And the workflow should contain node "gcp_assistant_node"
    And the node model should be "gemini-4-argon"
    And the node tools should contain "get_current_gcp_project"
    And the workflow edges should contain from "START" to "gcp_assistant_node"
    And the node instruction should require using "get_current_gcp_project" for project identification

  Scenario 2: Verify agent metadata via get_agent_info
    Given the gcp_assistant agent module is loaded
    When get_agent_info is called
    Then the result status should be "success"
    And the result agent name should be "gcp_assistant"
    And the result agent type should be "Workflow"
    And the result node name should be "gcp_assistant_node"
    And the result agent model should be "gemini-4-argon"
    And the result agent tools should contain "get_current_gcp_project"
    And the result edges should contain from "START" to "gcp_assistant_node"

  Scenario 3: Propagate tool failure when gcloud CLI is not installed
    Given gcloud CLI is not installed
    When the agent invokes get_current_gcp_project tool
    Then the tool result status should be "error"
    And the tool result error should contain "not installed"

  Scenario 4: Propagate tool failure when GCP project is unset
    Given gcloud CLI is installed
    And gcloud command succeeds with output "(unset)"
    When the agent invokes get_current_gcp_project tool
    Then the tool result status should be "error"
    And the tool result error should contain "not set"

  Scenario 5: Agent factory falls back to default model when model is empty
    Given a model name is specified as ""
    When create_gcp_assistant_agent is called with the model name
    Then the created agent type should be "Workflow"
    And the created agent name should be "gcp_assistant"
    And the created agent node model should be "gemini-4-argon"

  Scenario 6: Agent factory falls back to default model when model is whitespace
    Given a model name is specified as "   "
    When create_gcp_assistant_agent is called with the model name
    Then the created agent node model should be "gemini-4-argon"

  Scenario 7: Agent factory trims whitespace when model name has surrounding spaces
    Given a model name is specified as "  gemini-4-argon  "
    When create_gcp_assistant_agent is called with the model name
    Then the created agent type should be "Workflow"
    And the created agent name should be "gcp_assistant"
    And the created agent node model should be "gemini-4-argon"

  Scenario 8: Agent instruction enforces read-only operations and confidentiality
    Given the root_agent node instruction is inspected
    Then the instruction should require read-only operations
    And the instruction should prohibit modifying or deleting resources
    And the instruction should prohibit outputting tokens or private keys

  Scenario 9: Verify tool execution security with active project utaha-io
    Given gcloud CLI is installed
    And gcloud config has active project "utaha-io" and calls are recorded
    When the agent invokes get_current_gcp_project tool
    Then the tool result status should be "success"
    And the tool result project should be "utaha-io"
    And gcloud should have been invoked without a shell
    And gcloud should have been invoked with a finite timeout
```

## 5. 決定の記録

- `2026-11-05`: `explorer` と `gcp-inspector` の調査結果に基づき初版作成。ADK エージェント本体 `root_agent` および構成検証関数 `get_agent_info`・ファクトリ関数 `create_gcp_assistant_agent` を定義。空文字・空白文字列のフォールバック動作、実在プロジェクト `utaha-io` による動作検証、読み取り専用・機密情報秘匿のセキュリティ制約を規定。
- `2026-11-05`: ユーザーの明示的な指定に基づき、既定モデルを `gemini-3.8-flash` に更新。
- `2026-11-05`: ユーザーの指定に基づき、ADK 2.0 Graph API（`google.adk.workflow.Workflow` および `google.adk.agents.LlmAgent`）構成へ刷新。`root_agent` を `Workflow` とし、`edges=[("START", llm_node)]` で `gcp_assistant_node`（`LlmAgent`）を接続する仕様に改定。
- `2026-11-05`: ユーザーの指定に基づき、使用するモデル名を `gemini-4-argon` にすべて統一。Scenario 7 は前後に空白を含む `"  gemini-4-argon  "` の空白トリムを検証するエッジケースシナリオに改定。
- `2026-11-05`: ADK 2.0 Graph API の内部ノード挙動として、`Workflow(edges=[("START", llm_node)])` の開始ノードが内部で `__START__` として保持されるため、`get_agent_info()` で `"START"` に正規化して返却する設計判断。
- `2026-11-05`: `specs/` および `tests/features/` の `Scenario N:` 構文を pytest-bdd が認識できるよう、`tests/conftest.py` で Gherkin dialect (`DIALECTS['en']['scenario']`) を拡張する設計判断。
- `2026-11-05`: 全9シナリオの実装完了（`gcp_assistant/agent.py`、`__init__.py`、`tests/step_defs/test_gcp_assistant_agent.py`）。`spec-verifier` による検証で全9シナリオ PASS、`reviewer` によるコードレビューで High 指摘 0 件、`evaluator` による品質評価で全メトリクス目標スコア 1.0000 達成を記録。

