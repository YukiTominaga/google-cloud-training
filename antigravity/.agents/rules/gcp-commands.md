# GCP コマンド実行ルール

本プロジェクトにおいて、エージェントが `gcloud` コマンドを実行する際の安全基準および権限境界を定めます。

---

## 1. 自動実行してよい gcloud コマンド（読み取り系）
以下の読み取り専用コマンドは、ユーザーへの事前確認なしに自動実行して構いません。
- `gcloud config list`
- `gcloud config get-value`
- `gcloud auth list`
- `gcloud projects describe`
- `gcloud services list`
- 任意の GCP サービスの `list` および `describe` サブコマンド（例: `gcloud compute instances list`, `gcloud run services describe` 等）

## 2. 必ず事前確認する gcloud コマンド（変更・作成・削除系）
以下の操作を含むコマンドは、実行前に**必ずコマンド全文をユーザーに提示**し、明示的な承認を得てから実行してください。
- `create`（リソースの新規作成）
- `delete`（リソースの削除）
- `update`（リソースの更新）
- `deploy`（アプリケーションやサービスのデプロイ）
- `set`（設定やポリシーの変更）
- `enable` / `disable`（サービスや機能の有効化・無効化）
- `iam` 系全般（ロール・権限の付与や剥奪、サービスアカウントの操作・バインド等）

## 3. 対象プロジェクトの扱い
- 対象プロジェクトは必ず `gcloud config get-value project` で取得されるローカル設定値を使用してください。
- 原則として `--project` フラグ等で別プロジェクトを明示指定して実行してはなりません。

## 4. 実行禁止コマンド
以下のコマンドはセキュリティおよび認証情報保護のため、いかなる場合も実行を禁止します。
- `gcloud auth print-access-token`
- `gcloud auth print-identity-token`
- 鍵ファイルを出力・生成・エクスポートするコマンド（例: `gcloud iam service-accounts keys create` 等）

## 5. 出力時の機密情報保護
- コマンドの出力結果にアクセストークン、ID トークン、秘密鍵、シークレット等が含まれていた場合、それらを会話ログや画面出力に貼り付けてはなりません。
- 「トークンや鍵が含まれていた」という事実のみをユーザーに報告してください。
