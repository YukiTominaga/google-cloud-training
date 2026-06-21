# image_edit_studio — Nano Banana 2 で画像を編集する応用アプリ

`adk web` で画像を添付し、自然文で指示すると、Nano Banana 2（Gemini の画像モデル）が
inpainting / outpainting を行い、結果を **artifact** として返す応用デモです。

## 学べる概念（ここまでの教材に無かった要素）

- **マルチモーダル入力**: ユーザーが添付した画像を、ツールが `tool_context.user_content` から取得する
- **画像編集ツール**:
  - `inpaint_image` … 画像の内側を局所的に編集（追加 / 置換 / 削除）
  - `outpaint_image` … 画像の外側へシーンを自然に拡張
- **artifact**: 生成画像を `tool_context.save_artifact(...)` で返し、`adk web` の画面に表示する
- **Nano Banana 2**（`gemini-3.1-flash-image` / `gemini-3-pro-image`）を `google-genai` の
  `generate_content(response_modalities=["IMAGE"])` で呼ぶ
- 推論用モデル（`GEMINI_MODEL`）と画像編集用モデル（`IMAGE_MODEL`）を分けて使う

## 対応する講義モジュール

- 応用（M2 / M3 の発展）。ツール・artifact・マルチモーダルを組み合わせた完成形として位置づけます。

## ファイル構成

```
image_edit_studio/
├── agent.py      # root_agent（inpaint_image / outpaint_image を持つ LlmAgent）
├── tools.py      # 画像編集ツール（Nano Banana 2 呼び出し＋ save_artifact）
├── enable_paste.py  # adk web の配信 HTML に Cmd+V 画像貼り付けを注入（拡張機能不要・推奨）
├── paste_in_adk_web.user.js  # 同機能の Tampermonkey ユーザースクリプト / コンソール版
└── __init__.py
```

## セットアップ

リポジトリ直下で `uv sync` と `cp .env.example .env` を済ませてください。画像モデルを使うため、
**モデルへのアクセスが必要**です（`.env` で AI Studio の API キー、または Vertex AI + ADC を設定）。

`.env` の `IMAGE_MODEL`（既定 `gemini-3.1-flash-image`）で画像モデルを差し替えられます
（高品質にしたい場合は `gemini-3-pro-image`）。

## 実行コマンド

画像の添付が必要なため、**ブラウザ UI（`adk web`）で使います**。

```bash
uv run adk web      # ドロップダウンで image_edit_studio を選択 → 画像を添付して指示する
```

## クリップボードの画像を貼り付ける（adk web で Cmd+V を有効化）

`adk web` のチャット入力欄は、**標準ではクリップボード画像の貼り付け（Cmd+V）に対応していません**
（ファイル選択ボタンでの添付のみ）。Web 版 Gemini / ChatGPT のように「開くだけで Cmd+V」を使うには、
adk web の配信 HTML にペースト処理を 1 回注入します（下記の方法 1）。

### 方法 1: 配信 HTML に注入する（拡張機能・コンソール不要。推奨）

`enable_paste.py` が、ローカルにインストールされた adk web の `index.html` に小さな `<script>` を注入します。
これだけで、以後 `adk web` を開くと**自動で Cmd+V 画像貼り付けが有効**になります。

```bash
uv run python image_edit_studio/enable_paste.py            # 有効化
uv run python image_edit_studio/enable_paste.py --disable  # 元に戻す
```

その後 `uv run adk web` を開き直し、画像をコピーしてチャット欄で **Cmd+V** するだけです。

> 注: ローカルの google-adk 配信ファイル（site-packages 内）を書き換えます。`uv sync --reinstall` や
> google-adk のアップグレード後は消えるので、その場合は `enable_paste.py` を再実行してください（冪等です）。

### 方法 2: Tampermonkey（site-packages を触りたくない場合）

1. ブラウザに [Tampermonkey](https://www.tampermonkey.net/) 拡張を入れる。
2. Tampermonkey の「新規スクリプトを作成」を開き、`image_edit_studio/paste_in_adk_web.user.js` の中身を
   全部貼り付けて保存する。
3. 以後 `uv run adk web`（http://localhost:8000）を開くと**自動で有効**になります。画像をコピーして
   チャット欄で Cmd+V するだけです。
   - 別ポートで起動している場合は、スクリプト冒頭の `@match` のポート番号を合わせてください。

### 方法 3: コンソールに貼り付け（インストール不要・再読み込みごとに 1 回）

1. `uv run adk web` を開き、DevTools コンソールを開く（Mac: Option+Cmd+I → Console）。
2. （初回のみ）Chrome / Edge では **`allow pasting`** と入力して Enter（コンソールの貼り付け保護を解除）。
3. `paste_in_adk_web.user.js` の中身を貼り付けて実行する。`[adk-paste] 有効化しました` が出ればOK。
4. 画像をコピーしてチャット欄で Cmd+V。

> 再読み込みごとに方法 3 はやり直しが必要です。毎回やりたくない場合は方法 1（注入）か方法 2（Tampermonkey）を使ってください。

### 方法 4: ブックマークレット（インストール不要・1 クリック）

次の 1 行をブックマークに登録し、adk web を開くたびにクリックします（ページごとに 1 回）。

```text
javascript:(()=>{const f=()=>{const a=[...document.querySelectorAll('input[type=file]')];return a.find(i=>!((i.getAttribute('accept')||'').includes('json')))||a[0];};const g=b=>{const i=f();if(!i){alert('file input not found');return;}const n=new File([b],b.name||'pasted.png',{type:b.type||'image/png'});const d=new DataTransfer();d.items.add(n);i.files=d.files;i.dispatchEvent(new Event('change',{bubbles:true}));};document.addEventListener('paste',e=>{const t=(e.clipboardData&&e.clipboardData.items)||[];for(const x of t){if(x.kind==='file'&&x.type.startsWith('image/')){e.preventDefault();g(x.getAsFile());return;}}},true);alert('adk paste enabled');})();
```

うまくいかないときは、コンソールの `[adk-paste]` ログと `window.adkListInputs()` の出力を確認してください。

## サンプルクエリ（試してみる）

`adk web` で画像を 1 枚添付し、同じメッセージで次のように指示してみてください。

1. **（画像を添付して）「この写真の背景を夜空に変えてください」** — `inpaint_image` が呼ばれ、編集画像が artifact 表示されます。
2. **（画像を添付して）「左右に背景を広げて全体が見えるようにしてください」** — `outpaint_image` が呼ばれ、拡張画像が artifact 表示されます。

## 期待される挙動

- 画像＋指示を送ると、エージェントが内容に応じて `inpaint_image` か `outpaint_image` を選んで実行します。
- 編集結果は `inpaint_result.png` / `outpaint_result.png` という artifact として保存され、`adk web` の画面で
  ビフォー（添付画像）/アフター（生成画像）を確認できます。
- 画像を添付せずに指示した場合は、画像の添付を促します。

## メモ

- **inpaint と outpaint の違い**: inpaint は画像の*内側*の局所編集、outpaint は画像の*外側*への拡張です。
  Nano Banana（Gemini 画像モデル）では、どちらも「画像＋プロンプト」で指示します（厳密なマスク指定は任意）。
- **画像は同じメッセージに添付**してください。本サンプルは現在のメッセージの添付画像を対象に編集します。
- **レート制限**: 画像モデルにはクォータがあり、短時間に多数実行すると `429 RESOURCE_EXHAUSTED` になることがあります。
  少し待ってから再試行してください。
