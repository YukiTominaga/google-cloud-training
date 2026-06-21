"""全サンプルエージェントが現行 google-adk でロードできるかを検証するスクリプト。

LLM の呼び出しは行わないため、API キーがなくても実行できます。各ディレクトリの
`root_agent` / `app` が現行の ADK で正しく import・構築できることだけを確認します。

    uv run python verify_agents.py

注: このファイルは診断用ハーネスです。下記の広い例外捕捉は「どのサンプルが
なぜ壊れたか」をまとめて表示するための意図的なものです。エージェントやツールの
本体コードでは広い例外捕捉を書かないでください (retry / HITL を壊すため)。
"""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import BaseAgent
from google.adk.apps import App
from google.adk.cli.utils.agent_loader import AgentLoader

# このスクリプトが置かれているディレクトリ (リポジトリ直下) を agents_dir とします。
AGENTS_DIR = Path(__file__).resolve().parent


def _is_agent_dir(path: Path) -> bool:
    """エージェントディレクトリ (agent.py か __init__.py を持つ) かどうかを判定します。"""
    if not path.is_dir() or path.name.startswith(".") or path.name == "__pycache__":
        return False
    return (path / "agent.py").is_file() or (path / "__init__.py").is_file()


def main() -> int:
    loader = AgentLoader(str(AGENTS_DIR))
    agent_dirs = sorted(p.name for p in AGENTS_DIR.iterdir() if _is_agent_dir(p))

    if not agent_dirs:
        print("エージェントディレクトリが見つかりません。")
        return 1

    failures = 0
    for name in agent_dirs:
        try:
            loaded = loader.load_agent(name)
        except Exception as exc:  # noqa: BLE001 — 診断用にすべての失敗を表示する
            print(f"x {name}: ロード失敗 -> {type(exc).__name__}: {exc}")
            failures += 1
            continue

        if isinstance(loaded, App):
            print(f"o {name}: App(root_agent={loaded.root_agent.name!r})")
        elif isinstance(loaded, BaseAgent):
            print(f"o {name}: {type(loaded).__name__}(name={loaded.name!r})")
        else:
            print(f"x {name}: root_agent/app が BaseAgent/App ではありません -> {type(loaded)}")
            failures += 1

    print()
    if failures:
        print(f"{failures} 件のロードに失敗しました。")
        return 1
    print(f"全 {len(agent_dirs)} 件のエージェントがロードできました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
