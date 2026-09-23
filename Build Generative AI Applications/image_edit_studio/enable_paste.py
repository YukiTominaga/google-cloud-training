"""adk web の配信 HTML に「クリップボード画像の Cmd+V 貼り付け」を注入する（恒久・拡張機能不要）。

adk web (v2.3.0) のフロントエンドは画像ペーストに非対応です。このスクリプトは、配信元の
`index.html` に小さな `<script>` を 1 回だけ注入し、ページ読み込み時に自動でペースト対応にします。
これで拡張機能もコンソール操作も不要になり、Web 版 Gemini / ChatGPT のように開くだけで Cmd+V できます。

    uv run python image_edit_studio/enable_paste.py            # 有効化（注入）
    uv run python image_edit_studio/enable_paste.py --disable  # 無効化（除去）

注意:
- これはローカルにインストールされた google-adk の配信ファイル（site-packages 内）を書き換えます。
- `uv sync --reinstall` や google-adk のアップグレード後は消えるので、その場合は再度実行してください。
- 冪等です（何度実行しても二重注入されません）。
"""

from __future__ import annotations

import argparse
import pathlib
import re

import google.adk.cli

MARKER_ID = "adk-clip-paste"
INDEX = pathlib.Path(google.adk.cli.__file__).parent / "browser" / "index.html"

# 注入する JavaScript。adk web 自身のファイル入力に貼り付け画像を流し込み、通常の添付として取り込む。
# （`</script>` や生の `<` を含めないこと。インライン script を壊さないため。）
PASTE_JS = """
(function () {
  function findInput() {
    var a = Array.prototype.slice.call(document.querySelectorAll('input[type=file]'));
    for (var i = 0; i < a.length; i++) {
      if ((a[i].getAttribute('accept') || '').indexOf('json') === -1) return a[i];
    }
    return a[0] || null;
  }
  function inject(file) {
    var input = findInput();
    if (!input) { console.warn('[adk-paste] file input not found'); return; }
    var name = file.name || ('pasted-' + Date.now() + '.png');
    var named = new File([file], name, { type: file.type || 'image/png' });
    var dt = new DataTransfer();
    dt.items.add(named);
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    console.log('[adk-paste] attached', name);
  }
  document.addEventListener('paste', function (e) {
    var items = (e.clipboardData && e.clipboardData.items) || [];
    for (var i = 0; i < items.length; i++) {
      if (items[i].kind === 'file' && items[i].type.indexOf('image/') === 0) {
        e.preventDefault();
        inject(items[i].getAsFile());
        return;
      }
    }
    if (navigator.clipboard && navigator.clipboard.read) {
      navigator.clipboard.read().then(function (data) {
        for (var j = 0; j < data.length; j++) {
          var types = data[j].types || [];
          for (var k = 0; k < types.length; k++) {
            if (types[k].indexOf('image/') === 0) {
              (function (item, t) {
                item.getType(t).then(function (blob) {
                  inject(new File([blob], 'pasted-' + Date.now() + '.png', { type: t }));
                });
              })(data[j], types[k]);
              return;
            }
          }
        }
      }).catch(function () {});
    }
  }, true);
  console.log('[adk-paste] enabled (copy an image and Cmd+V in the chat)');
})();
"""

# 既存の注入ブロックを見つける/消すための正規表現。
SCRIPT_RE = re.compile(r'\n?<script id="' + MARKER_ID + r'">.*?</script>', re.DOTALL)


def _read_index() -> str:
    if not INDEX.is_file():
        raise SystemExit(f"index.html が見つかりません: {INDEX}")
    return INDEX.read_text(encoding="utf-8")


def disable() -> None:
    html = _read_index()
    new_html = SCRIPT_RE.sub("", html)
    if new_html == html:
        print("注入されていません（すでに無効です）。")
        return
    INDEX.write_text(new_html, encoding="utf-8")
    print(f"除去しました: {INDEX}")


def enable() -> None:
    html = _read_index()
    html = SCRIPT_RE.sub("", html)  # 既存を消してから入れ直す（更新にも対応）
    if "</body>" not in html:
        raise SystemExit("index.html に </body> が見つかりません。")
    block = f'\n<script id="{MARKER_ID}">{PASTE_JS}</script>'
    html = html.replace("</body>", block + "\n</body>", 1)
    INDEX.write_text(html, encoding="utf-8")
    print(f"注入しました: {INDEX}")
    print("adk web を開き直すと、画像をコピーして Cmd+V で添付できます（拡張機能・コンソール不要）。")


def main() -> int:
    parser = argparse.ArgumentParser(description="adk web に画像ペースト対応を注入する")
    parser.add_argument("--disable", action="store_true", help="注入を除去する")
    args = parser.parse_args()
    disable() if args.disable else enable()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
