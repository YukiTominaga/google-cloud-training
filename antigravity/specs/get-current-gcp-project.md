# 仕様書: get_current_gcp_project ツール

## 背景（なぜ）

クラウド環境を操作・支援する AI エージェント（`gcp_assistant`）が、ユーザーの意図しない Google Cloud プロジェクトに対して誤った問い合わせやリソース操作を行う事故を防ぐため、現在アクティブになっている GCP プロジェクト ID を安全かつ確実に特定する必要がある。

Google Cloud SDK（`gcloud` CLI）のローカル設定値（`gcloud config get-value project`）を取得することで、ローカル環境のアクティブプロジェクトを自律的に確認し、ユーザーへの確認や後続ツールへの入力として利用できるようにする。

## 技術設計（ツールのシグネチャ、戻り値、失敗時の振る舞い、セキュリティ制約）

### ツールのシグネチャ

```python
def get_current_gcp_project() -> dict[str, str]:
    """Retrieves the currently configured GCP project ID from the local gcloud configuration."""
```

### 戻り値

- **成功時**: `{"status": "success", "project": "<PROJECT_ID>"}`
  - 例: `{"status": "success", "project": "my-sample-project"}`
- **失敗時**: `{"status": "error", "error": "<ERROR_MESSAGE>"}`
  - 例: `{"status": "error", "error": "gcloud CLI is not installed or not found in PATH"}`

### 失敗時の振る舞い

1. **`gcloud` CLI 未インストール / 未検出 (`FileNotFoundError`)**:
   - `{"status": "error", "error": "gcloud CLI is not installed or not found in PATH"}` を返す。例外を送出せず、エージェントがハンドリング可能な辞書形式で通知する。
2. **`gcloud` コマンド実行失敗（非ゼロ終了コード / stderr 出力 / 空出力）**:
   - プロジェクト未設定（`(unset)` など）や認証未完了等でコマンドが失敗した場合、stderr またはエラーメッセージを含めた `{"status": "error", "error": "<詳細>"}` を返す。
3. **コマンド実行タイムアウト (`subprocess.TimeoutExpired`)**:
   - 外部プロセスのハングを防ぐため、タイムアウト発生時は速やかに処理を打ち切り、`{"status": "error", "error": "Command execution timed out"}` を返す。

### セキュリティ制約

- **シェルインジェクションの防止**:
  - `subprocess.run` 実行時に `shell=True` は一切使用しない。引数はリスト形式 `["gcloud", "config", "get-value", "project"]` で安全に渡す。
- **タイムアウト設定**:
  - 外部プロセスのハングによるエージェント全体の応答不能を回避するため、必ず有限のタイムアウト（例: `timeout=5` 秒）を設定する。
- **機密情報の保護**:
  - 認証トークンや不要なシステム環境変数などの機密情報は取得せず、プロジェクト ID のみを抽出して返却する。

## バージョン固定（Python、google-adk、pytest-bdd の実際のバージョン）

本プロジェクトで利用する主要ツールの固定バージョンは以下の通りである：

| パッケージ / ツール | バージョン | 備考 |
| :--- | :--- | :--- |
| **Python** | `3.11.18` | ランタイム (>=3.11) |
| **google-adk** | `2.13.0` | Google Agent Development Kit |
| **pytest-bdd** | `9.0.1` | 仕様駆動テスト（BDD）フレームワーク |
| **pytest** | `9.2.0` | テストランナー |
| **ruff** | `0.17.3` | Linter / Formatter |

## シナリオ（Gherkin）

```gherkin
Feature: Get current GCP project
  As an AI assistant
  I want to retrieve the currently active GCP project ID
  So that I can safely interact with the intended GCP resources

  Scenario: Successfully retrieve the active GCP project
    Given gcloud CLI is installed
    And gcloud config has active project "my-sample-project"
    When get_current_gcp_project is called
    Then the result status should be "success"
    And the result project should be "my-sample-project"

  Scenario: Fail to retrieve GCP project when gcloud command fails
    Given gcloud CLI is installed
    And gcloud command fails with error "No project set"
    When get_current_gcp_project is called
    Then the result status should be "error"
    And the result error message should contain "No project set"

  Scenario: Fail to retrieve GCP project when gcloud is not installed
    Given gcloud CLI is not installed
    When get_current_gcp_project is called
    Then the result status should be "error"
    And the result error message should contain "not installed"

  Scenario: Fail to retrieve GCP project when command times out
    Given gcloud CLI is installed
    And gcloud command times out
    When get_current_gcp_project is called
    Then the result status should be "error"
    And the result error message should contain "timed out"
```
