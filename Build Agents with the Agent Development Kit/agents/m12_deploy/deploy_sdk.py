# =====================================================================
# M12 Code 5. 経路 C ― SDK を直接使う
# ---------------------------------------------------------------------
# CLI を使わず、Python から Agent Runtime にデプロイする。
# CI/CD パイプラインに組み込むときや、インスタンス数・リソース・
# identity などを細かく指定したいときに使う。
#
# 実行方法（agents/ フォルダで。Cloud の認証が必要）:
#   export PROJECT_ID=my-project LOCATION=us-central1 STAGING_BUCKET=gs://my-staging-bucket
#   python -m m12_deploy.deploy_sdk
# =====================================================================

import os

import vertexai
from vertexai import agent_engines, types

from .agent import root_agent


def build_config() -> dict:
    """デプロイ設定。キーは SDK の AgentEngineConfig に対応する。"""
    return {
        # Agent Runtime 側でインストールする依存
        "requirements": ["google-cloud-aiplatform[agent_engines,adk]", "google-adk==2.9.2"],
        # ソースを一時的に置く GCS バケット。
        # ※ CLI の --staging_bucket は非推奨だが、SDK の config キーとしては現役
        "staging_bucket": os.environ.get("STAGING_BUCKET", "gs://my-staging-bucket"),
        "display_name": "Order Support Agent",
        # agent 専用の ID（Agent Identity）で動かす。
        # サービスアカウントを共有せず、agent ごとに権限を絞れる
        "identity_type": types.IdentityType.AGENT_IDENTITY,
        # スケーリング：常時 1 インスタンス待機（コールドスタート回避）〜最大 10
        "min_instances": 1,
        "max_instances": 10,
        # 1 インスタンスあたりのリソース
        "resource_limits": {"cpu": "4", "memory": "8Gi"},
    }


def main() -> None:
    client = vertexai.Client(
        project=os.environ.get("PROJECT_ID", "PROJECT_ID"),
        location=os.environ.get("LOCATION", "us-central1"),
    )

    # ADK の agent を Agent Runtime で動かすためのラッパー
    app = agent_engines.AdkApp(agent=root_agent)

    # ⚠️ SDK のメソッド名は移行中：
    #   Agent Runtime のクイックスタートは client.agent_engines.create()、
    #   デプロイのリファレンスは client.runtimes.create()。
    #   google-cloud-aiplatform 1.165.1 には agent_engines しか無いことを確認済み。
    #   片方でエラーが出たらもう一方を試す。
    remote_agent = client.agent_engines.create(agent=app, config=build_config())

    # 完全なリソース名。末尾の数値が RESOURCE_ID
    print(remote_agent.api_resource.name)
    # projects/PROJECT_NUMBER/locations/LOCATION/reasoningEngines/RESOURCE_ID


if __name__ == "__main__":
    main()
