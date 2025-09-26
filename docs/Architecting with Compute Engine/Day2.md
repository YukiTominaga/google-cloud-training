Architecting with Google Compute Engine - Day 2

# データベースとストレージ

## Cloud Storage

バケットというリソースを作成し、ファイルをなんでも保存できます。
近年の機能拡張により、ファイルを保存しておくという側面以外に、コンテナにファイルシステムとしてマウントできます。
参考: [Cloud Run サービスに対して Cloud Storage のボリューム マウントを構成する](https://cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts?hl=ja)

### Storage Class

アクセス頻度の低いオブジェクトの保存コストを抑えて保存する機能のことです。
アクセス頻度の高い順から `Standard`、`Nearline(月に1回)`、`Coldline(3か月に1回)`、`Archive(1年に1回)`があります。
ライフサイクルを利用して保存してから一定期間経過したらオブジェクトのStorage Classを変更することができます。
Autoclassというものも最近登場していて、Storage Classの制御を自動でできます。

Storage Classはオブジェクトごとに定義でき、バケット作成時にはデフォルトのStorage Classを指定します。

### バケットのリージョンについての考慮

AsiaのMulti regionはアジア圏の中から選ばれるので、日本国外にデータが保存される可能性が高いです。
データの可用性を高く保ち日本国内にデータを保存するには、東京と大阪のデュアルリージョンがおすすめです。

### アクセス制御

ACLを用いたオブジェクトごとのアクセス制御は管理が煩雑なためなるべく利用しないようにアーキテクチャを考慮したいです。
バケットレベルでIAMによる制御に絞ることが運用簡素化のために重要です。

### 署名付きURL

Google Cloudへの認証をしないユーザーがCloud Storageにオブジェクトをアップロードしたりダウンロードできる時間制限付きのURLのことです。
どんなファイルでもアップロードできないように、ポリシードキュメントを利用してアップロードするファイルに制限をかけられます。

### バージョニング

オブジェクトの変更履歴を残し、過去の更新前のオブジェクトを取得できます。
ライフサイクル管理と併用すれば、最新いくつのバージョンを保存するのかを制御できます。

### PubSub Notifications

バケット内のオブジェクトの変更をPubSubに通知する機能です。
PubSubに通知されれば任意のプログラムコードで変更イベントを処理できます。

### Cloud Storageへのデータ転送

`gcloud storage`コマンドは最も簡易的な方法で、ローカルPCやGoogle Cloud内部の小規模なデータ転送に利用します。
Google Cloud外部からの大規模なデータ転送には、Storage Transfer Serviceを利用します。
ネットワークを経由したデータ転送が現実的に不可能な容量であれば、Google Cloud Storage Transfer Applianceを利用して物理ディスクを転送します。

### 保持ポリシー(説明で触れなかったこと)

データが誤って削除されないように、任意の期間を指定してオブジェクトの存在を保証する機能です。
保持ポリシーを設定したオブジェクトは、その期間中は削除できません。

### ラボ Cloud Storage

Cloud Storageの各種機能を体験します。
このラボの中で特に重要なのは、ライフサイクル管理、バージョニングです。

### gcloud storageコマンド利用例

CSEK(顧客指定の暗号鍵)を設定してオブジェクトをアップロードします。

```bash
gcloud storage cp --encryption-key=xxx \
    <ローカルファイル> gs://<バケット名>/<オブジェクト名>
```

オブジェクトの暗号鍵を更新します。
(元々の暗号鍵`xxx`を指定してdecryptしながら新しい暗号鍵`yyy`で保存し直します)

```bash
gcloud storage objects update gs://<バケット名>/<オブジェクト名> \
    --encryption-key=yyy \
    --decryption-keys=xxx
```

ライフサイクル管理
`life.json`というライフサイクル定義ファイルがあったとします。

```bash
gcloud storage buckets update gs://<バケット名> \
    --lifecycle-file=life.json
```

バージョニング

```bash
gcloud storage buckets update gs://<バケット名> --versioning
```

## Cloud SQL

### 接続パターン

1. SQLインスタンスの外部IPアドレス宛に接続します
   外部IPアドレス経由の接続には、SQLインスタンスに接続元のCIDRを指定して接続元を制限することができます。
   接続元IPアドレスは極力指定せず、外部IP + 後述するCloud SQL Auth Proxyによる接続を推奨します。

2. SQLインスタンスの内部IPアドレス宛にVPCネットワークから接続します
   VPCネットワーク上のCompute Engineインスタンスからの接続はもちろん、Cloud Runなどのサーバーレス環境からも接続できます(Serverless VPC Access という機能を利用して、サーバーレスプロダクトを特定のVPCネットワークに接続することが可能です)。
   ただし、実際にはProxyを経由した接続を行う場面が多いため、内部IPアドレス経由で接続することは稀です。

3. Cloud SQL Proxyを利用して接続します(Very Good)
   あらゆる場所からProxy経由での接続を推奨します。
   この方法はIAMによる接続制御が可能であり、通信が暗号化される点が非常に優れています。

### ラボ Implementing Cloud SQL

今自分がどこからどのような方法で接続しようとしているのかを意識することが重要です。

### ポイント

- 外部IPアドレス経由の場合は承認済みネットワークを設定してアクセス元IPアドレスを許可します
- 内部IPアドレス経由の場合は接続可能なVPC Networkを指定します
- Cloud SQL ProxyがSQLインスタンスに接続するためには、実行環境の認証アカウントに`Cloud SQL Client`の役割が必要です

### 内部IP接続の仕組み

内部IPアドレスで接続するためには、VPC Network内のネットワークルートにCloud SQLの内部IPアドレス向けのルーティングルールと、その疎通のための設定が必要です。

途中のラボの手順でコネクションを作成していた部分がまさにその両方をやってくれていて、ピアリングによってCloud SQLインスタンスとの通信が可能になっています。

VPC NetworksメニューからRoutesを選択すると、Cloud SQLの内部IPアドレス向けのルーティングルールが作成されていることが確認できます。
この時、Routeの宛先(Next hop)は `servicenetworking-googleapis-com`となっていて、これが自動で作成されたピアリングです。

最初から何もせずに内部IPアドレス経由で接続できるわけではなく、裏では必要なネットワーク設定をいい感じにやってくれていることを知っておくと、「こいつ、できる...!!」と思われるかもしれません(知らなくても運用と開発上特に問題はありませんが...)。

## Cloud Spanner

参考 [Cloud Spanner の誤解を打ち破る](https://cloud.google.com/blog/ja/products/databases/cloud-spanner-myths-busted)

## リソース管理

### 組織、フォルダ、プロジェクト、リソース

IAMはすべて組織からリソースに向かって継承されます。
フォルダの`owner`であれば、そのフォルダ内に作成されたすべてのプロジェクトの`owner`となります。

## 予算とアラート

予算を設定すると、予算に対して任意のしきい値をベースにアラートを飛ばすことが可能です。

## ラベル

リソースにkey,value形式のラベルを付与しておくと、ラベルごとに請求額を閲覧できます。

## Quota

各種APIの管理ページ(例えば、検索欄に `Compute Engine API`と入力すると出てきます)からQuotaの上限と消費量を確認できます。
もし上限を引き上げたい場合は、割り当ての増加を理由を添えて申請できます。

### ラボ BigQueryを使った課金データの調査

請求データのBigQuery Exportが有効になっていれば任意のBIツールでダッシュボードを作成できます。

# リソースモニタリング

## Google Cloudのオペレーションスイート

「オペレーションスイート」という言葉を普段使うことはありません。
LoggingやMonitoringなどの総称として定義されています。

## Monitoring

リソースの使用状況を計測し、状況に応じたアラートを設定できます。
基本的にはダッシュボードを作成し、Metrics Exploreで指標を確認し、ダッシュボードに追加していきます。

### カスタム指標

任意のkey,value,labelをCloud Monitoringに送信し、アプリケーション固有の値をMonitoringに送信できます。

## Logging

様々なリソースが自動で出力するログに加え、Cloud Run, GKEで実行されるコンテナの標準出力が自動で転送されます。
デフォルトでは保存期間は30日間ですが、Cloud StorageやBigQueryに転送することで永続保存が可能となります。

### 構造化ロギング

Cloud Loggingは[構造化ロギング](https://cloud.google.com/logging/docs/structured-logging?hl=ja)を知るところから始まる、と言っても過言ではありません。
任意のJSONをLoggingに出力することにより、検索性が非常に向上したり、便利なことをいろいろできます。

### ログの親子化

便利なことのうちの1つです。
例えばCloud Runであれば、リクエストログとアプリケーションログはそれぞれ別々のログエントリとして登録されます。
このとき、リクエストログとアプリケーションログを階層化し、どのリクエストに対してどのようなアプリケーションログが出力されるのかを確認しやすくなります。

### Error Reportingとの連携

ログがError Reportingに出力されるにはいくつかの[条件](https://cloud.google.com/error-reporting/docs/formatting-error-messages?hl=ja)があります。
Error Reportingにログを登録する際にも構造化ロギングの作法が必要不可欠となります。

# ネットワークの相互接続

## Cloud VPN

オンプレミスネットワーク、他のパブリッククラウドネットワーク、他のVPCネットワークとの相互接続のために利用されます。
静的ルートと動的ルートの2種類があり、動的ルートではBGPを利用したルーティング情報の交換を行うことで、
新たなサブネットの追加を接続先に反映させることができます。

可用性を期待する場合はHA VPNと呼ばれるVPNトンネルを2つ接続する方式を利用します。

## Cloud Interconnect

Cloud VPNはインターネットを経由した接続であるのに対して、Interconnectは専用線によるVPCネットワークへの直接接続を提供します。

Dedicated Interconnectは専用線を完全に占有できる一方で導入コストが高く柔軟性も低いです。
Partner Interconnectはサードパーティプロバイダを経由しますが、導入コストが安く柔軟性も高いです。

## ピアリング

Interconnectとは異なり、VPCネットワークに直接接続するわけではありません。
GoogleのパブリックIPアドレスにより高速に接続する必要があるような場合に利用します。

## VPCネットワークの共有

### 共有VPC

1つのホストGoogle Cloudプロジェクトを用意し、他のサービスプロジェクトを接続することで、異なるプロジェクトのVPCネットワーク同士が内部IPアドレスで接続できるようになります。
ただし、同一の組織内のプロジェクトに限る点に注意してください。

### VPCピアリング

VPCピアリングは、同一の組織である必要はありません。
異なるVPCネットワーク同士を接続し、内部IPアドレスでのトラフィック送受信を可能にします。
