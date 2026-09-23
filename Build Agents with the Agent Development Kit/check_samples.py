# =====================================================================
# サンプルコードの読み込みチェック（モデルは呼びません。API キー不要）
# ---------------------------------------------------------------------
#   uv run python check_samples.py
#
# 確認すること
#   1. agents/m01〜m13 を adk web と同じ仕組み（AgentLoader）で読み込み、
#      root_agent（または app）が作れるか
#   2. 各フォルダの補助モジュール（examples.py など）が import できるか
#   3. シェルスクリプトに構文エラーが無いか（bash -n）
# =====================================================================

import importlib
import pathlib
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore")  # 非推奨テンプレート（M7）の DeprecationWarning 等を隠す

ROOT = pathlib.Path(__file__).parent
AGENTS_DIR = ROOT / "agents"
sys.path.insert(0, str(AGENTS_DIR))

from google.adk.cli.utils.agent_loader import AgentLoader  # noqa: E402

failures = 0
loader = AgentLoader(str(AGENTS_DIR))

print("== 1. agent の読み込み ==")
for folder in sorted(p for p in AGENTS_DIR.iterdir() if p.is_dir() and p.name.startswith("m")):
    try:
        loaded = loader.load_agent(folder.name)
        root = getattr(loaded, "root_agent", loaded)
        print(f"  OK  {folder.name:28s} {type(loaded).__name__:10s} name={root.name}")
    except Exception as exc:  # チェック用スクリプトなので広く捕まえて一覧表示する
        failures += 1
        print(f"  NG  {folder.name:28s} {exc!r}")

print("== 2. 補助モジュールの import ==")
for py in sorted(AGENTS_DIR.glob("m*/*.py")):
    if py.name in ("__init__.py", "agent.py"):
        continue
    module = f"{py.parent.name}.{py.stem}"
    try:
        importlib.import_module(module)
        print(f"  OK  {module}")
    except Exception as exc:
        failures += 1
        print(f"  NG  {module} {exc!r}")

print("== 3. シェルスクリプトの構文 ==")
for sh in sorted(AGENTS_DIR.glob("m*/*.sh")):
    result = subprocess.run(["bash", "-n", str(sh)], capture_output=True, text=True)
    ok = result.returncode == 0
    failures += 0 if ok else 1
    print(f"  {'OK' if ok else 'NG'}  {sh.relative_to(AGENTS_DIR)} {result.stderr.strip()}")

print("\n結果:", "すべて OK" if failures == 0 else f"{failures} 件の NG")
sys.exit(1 if failures else 0)
