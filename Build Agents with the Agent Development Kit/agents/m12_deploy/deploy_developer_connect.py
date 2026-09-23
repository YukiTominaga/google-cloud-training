# =====================================================================
# M12 Code 6. Developer Connect から直接デプロイ
# ---------------------------------------------------------------------
# ローカルのソースをアップロードする代わりに、Developer Connect で
# 連携済みの Git リポジトリの特定リビジョンから直接デプロイする。
#   → 「どのコミットが本番で動いているか」が明確になる（監査しやすい）。
#
# 事前準備：Developer Connect で GitHub 等のリポジトリを接続し、
#           gitRepositoryLinks のリソース名を控えておく。
#
# 実行方法（agents/ フォルダで。Cloud の認証が必要）:
#   export PROJECT_ID=my-project LOCATION=us-central1
#   export GIT_REPOSITORY_LINK=projects/.../connections/.../gitRepositoryLinks/...
#   python -m m12_deploy.deploy_developer_connect
# =====================================================================

import os

import vertexai


def build_config() -> dict:
    return {
        "developer_connect_source": {
            # Developer Connect のリポジトリリンク（リソース名）
            "git_repository_link": os.environ.get(
                "GIT_REPOSITORY_LINK",
                "projects/PROJECT_ID/locations/LOCATION/connections/"
                "CONNECTION_ID/gitRepositoryLinks/REPO_ID",
            ),
            "revision": "main",  # ブランチ・タグ・コミット SHA
            "dir": "agents/m12_deploy",  # リポジトリ内の agent フォルダ
        },
        # dir の中の「どのモジュールの、どの変数」を起動するか
        # → M1 から変わらない約束：agent.py の root_agent
        "entrypoint_module": "agent",
        "entrypoint_object": "root_agent",
        "requirements_file": "requirements.txt",
    }


def main() -> None:
    client = vertexai.Client(
        project=os.environ.get("PROJECT_ID", "PROJECT_ID"),
        location=os.environ.get("LOCATION", "us-central1"),
    )
    # ⚠️ メソッド名は移行中（deploy_sdk.py のコメント参照）。
    #   新しい SDK では client.runtimes.create(...)、
    #   runtimes が無いバージョンの SDK では agent_engines.create(...) を使う。
    runtimes = getattr(client, "runtimes", None) or client.agent_engines
    remote_agent = runtimes.create(config=build_config())
    print(remote_agent.api_resource.name)


if __name__ == "__main__":
    main()
