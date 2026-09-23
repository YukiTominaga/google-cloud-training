// ==UserScript==
// @name         adk web clipboard image paste (image_edit_studio)
// @namespace    adk-image-studio
// @version      1.0
// @description  adk web のチャット欄でクリップボード画像を Cmd+V 貼り付けできるようにする
// @match        http://localhost:8000/*
// @match        http://127.0.0.1:8000/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==
//
// 【毎回貼り付けたくない場合（推奨）】
//   1. ブラウザに Tampermonkey 拡張を入れる（https://www.tampermonkey.net/）
//   2. Tampermonkey →「新規スクリプトを作成」→ このファイルの中身を全部貼り付けて保存
//   → 以後 adk web を開くたびに自動で有効化されます（コンソール操作は不要）。
//
// ※ このファイルはコンソールに貼り付けても動きます（その場合は再読み込みごとに貼り付けが必要）。
// ※ adk web を 8000 以外のポートで起動している場合は、上の @match のポート番号を合わせてください。

(() => {
  'use strict';

  // 二重登録を避けつつ、再実行で最新に差し替える。
  if (window.__adkPasteHandler) {
    document.removeEventListener('paste', window.__adkPasteHandler, true);
  }

  // チャット用のファイル入力を探す（セッションインポート用 accept=json は除外）。
  function findChatFileInput() {
    const inputs = Array.from(document.querySelectorAll('input[type=file]'));
    return (
      inputs.find((i) => !(i.getAttribute('accept') || '').includes('json')) || inputs[0] || null
    );
  }
  // デバッグ用: 見つかった file input の一覧を返す。
  window.adkListInputs = () => Array.from(document.querySelectorAll('input[type=file]'));

  function inject(file) {
    const input = findChatFileInput();
    if (!input) {
      console.warn('[adk-paste] チャットのファイル入力が見つかりません');
      return;
    }
    const named = new File([file], file.name || `pasted-${Date.now()}.png`, {
      type: file.type || 'image/png',
    });
    // adk web 自身の (change) ハンドラ（onFileSelect → selectedFiles）へ流し込む。
    const dt = new DataTransfer();
    dt.items.add(named);
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    console.log('[adk-paste] 添付しました:', named.name);
  }

  const handler = (e) => {
    const items = (e.clipboardData && e.clipboardData.items) || [];
    // 1) paste イベントの items から画像ファイルを取得（同期）。
    for (const it of items) {
      if (it.kind === 'file' && it.type.startsWith('image/')) {
        e.preventDefault();
        inject(it.getAsFile());
        return;
      }
    }
    // 2) items に無ければ、非同期 Clipboard API で読む（コピー方法によってはこちら）。
    if (navigator.clipboard && navigator.clipboard.read) {
      navigator.clipboard
        .read()
        .then(async (data) => {
          for (const item of data) {
            const t = item.types.find((x) => x.startsWith('image/'));
            if (t) {
              inject(
                new File([await item.getType(t)], `pasted-${Date.now()}.png`, {
                  type: t,
                }),
              );
              return;
            }
          }
        })
        .catch(() => {});
    }
  };

  window.__adkPasteHandler = handler;
  document.addEventListener('paste', handler, true);
  console.log('[adk-paste] 有効化しました（画像をコピーしてチャット欄で Cmd+V）');
})();
