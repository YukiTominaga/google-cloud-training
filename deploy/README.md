# Cloud Run への継続的デプロイ

`main` ブランチにアプリ関連ファイル（`src/**`、`package*.json`、`tsconfig.json`、`Dockerfile`、
`deploy/service.yaml` など）の変更が push されると、[`.github/workflows/cd.yaml`](../.github/workflows/cd.yaml)
が以下を実行する。Actions タブの「Run workflow」から手動実行もできる。

1. Workload Identity 連携（Direct WIF・キーレス）で Google Cloud に認証
2. `Dockerfile` からイメージをビルドし、Artifact Registry に `:<コミットSHA>` で push（GitHub Actions キャッシュ利用）
3. [`service.yaml`](./service.yaml) のイメージをダイジェスト指定（`@sha256:...`）に置換し、`gcloud run services replace` で適用
4. 公開 URL の `/health` にスモークテスト

| 項目           | 値                                                                    |
| -------------- | --------------------------------------------------------------------- |
| プロジェクト   | `utaha-io`（`103175005729`）                                          |
| リージョン     | `asia-northeast1`                                                     |
| サービス       | `google-cloud-training`                                               |
| イメージ       | `asia-northeast1-docker.pkg.dev/utaha-io/utaha/google-cloud-training` |
| ランタイム SA  | `training@utaha-io.iam.gserviceaccount.com`                           |
| WIF プロバイダ | `utaha-pool/tominaga-provider`                                        |

## 運用上の注意

- `gcloud run services replace` は `service.yaml` の内容でサービス全体を上書きする。
  コンソールや `gcloud run services update` での手動変更は次回デプロイで消えるので、
  環境変数・リソース・スケーリング設定の変更は必ず `service.yaml` で行う。
- 起動プローブ（`/health`）に失敗したリビジョンにはトラフィックが切り替わらず、旧リビジョンが配信を続ける。
- 手動ロールバック:
  ```bash
  gcloud run revisions list --service google-cloud-training --region asia-northeast1
  gcloud run services update-traffic google-cloud-training --region asia-northeast1 \
    --to-revisions <REVISION>=100
  ```
  ※ 次回の CD 実行で `latestRevision: true` に戻る。

## 初回のみ: Google Cloud 側の前提設定

参照元（ocg-search-nextjs）と同じ Direct WIF 構成で、GitHub Actions のプリンシパルに直接ロールを付与する。

```bash
PROJECT_ID=utaha-io
PROJECT_NUMBER=103175005729
REGION=asia-northeast1
RUNTIME_SA=training@${PROJECT_ID}.iam.gserviceaccount.com
PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/utaha-pool/attribute.repository/YukiTominaga/google-cloud-training"
```

> `tominaga-provider` の属性条件（attribute condition）がこのリポジトリを許可しており、
> `attribute.repository` がマッピングされていることを確認すること。

### 1. デプロイ用プリンシパル（GitHub Actions）

```bash
# Artifact Registry（utaha リポジトリ）への push
gcloud artifacts repositories add-iam-policy-binding utaha \
  --project "$PROJECT_ID" --location "$REGION" \
  --member "$PRINCIPAL" --role roles/artifactregistry.writer

# Cloud Run サービスの作成・更新（invoker-iam-disabled の設定に run.admin が必要）
# プロジェクトのポリシーに条件付きバインディングがあるため --condition=None を明示する
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "$PRINCIPAL" --role roles/run.admin --condition=None

# ランタイム SA を Cloud Run に割り当てる（actAs）
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --project "$PROJECT_ID" \
  --member "$PRINCIPAL" --role roles/iam.serviceAccountUser
```

### 2. ランタイム SA（`training@`）

アプリが利用する API に合わせて付与する（既に付与済みならスキップ）。
Telemetry API（OTLP）へのトレース・メトリクス・ログ送信は `roles/telemetry.writer`、
DLP デモは `roles/dlp.user` と対象バケットへのアクセスが必要。

```bash
for role in \
  roles/telemetry.writer \
  roles/dlp.user; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "serviceAccount:${RUNTIME_SA}" --role "$role" --condition=None
done

# DLP デモで読み書きする GCS バケットに対して
gcloud storage buckets add-iam-policy-binding gs://<BUCKET> \
  --member "serviceAccount:${RUNTIME_SA}" --role roles/storage.objectUser
```
