# GCP コマンド実行ルール

本プロジェクトにおいて、エージェントが `gcloud` コマンドを実行する際の安全基準を定めます。

## 1. 自動実行可能なコマンド（読み取り系）
以下の読み取り系コマンドは、ユーザーへの事前確認なしに自動実行して構いません。
- `gcloud config list`
- `gcloud config get-value`
- `gcloud auth list`
- `gcloud projects describe`
- `gcloud services list`
- 任意の GCP サービスの `list` および `describe` サブコマンド（例: `gcloud compute instances list`, `gcloud run services describe`）

## 2. 事前確認が必須のコマンド（変更・作成・削除系）
以下の操作を含むコマンドは、実行前に必ずコマンド全文を提示し、ユーザーの明示的な承認を得てから実行してください。
- `create`（リソースの新規作成）
- `delete`（リソースの削除）
- `update`（リソースの更新）
- `deploy`（アプリケーションやサービスのデプロイ）
- `set`（設定やポリシーの変更）
- `enable` / `disable`（サービスや機能の有効化・無効化）
- `iam` 系コマンド全般（ロール・権限の付与や剥奪、サービスアカウントの操作）

## 3. 対象プロジェクトの扱い
- 対象プロジェクトは必ず `gcloud config get-value project` で取得されるデフォルトプロジェクトを使用してください。
- 原則として `--project` フラグ等で別プロジェクトを明示指定して実行してはなりません。

## 4. 実行禁止コマンド
以下のコマンドはセキュリティおよび認証情報保護のため、いかなる場合も実行を禁止します。
- `gcloud auth print-access-token`
- `gcloud auth print-identity-token`
- サービスアカウントキーなどの鍵ファイルを出力・生成・エクスポートするコマンド（例: `gcloud iam service-accounts keys create`）

## 5. 認証情報・機密情報の取り扱い
- コマンドの出力にアクセストークン、シークレット、秘密鍵、各種認証情報が含まれていた場合、それらを会話ログや画面出力に貼り付けてはなりません。
- 「トークンや鍵情報が含まれていた」という事実のみをユーザーに報告してください。
