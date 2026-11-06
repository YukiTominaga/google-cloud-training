"""gcp_assistant のツール関数群。"""

import subprocess

_GCLOUD_COMMAND: list[str] = ["gcloud", "config", "get-value", "project"]
_TIMEOUT_SECONDS: int = 5


def get_current_gcp_project() -> dict[str, str]:
    """ローカルの gcloud 設定から現在のアクティブな GCP プロジェクト ID を取得する。

    Returns:
        成功時は ``{"status": "success", "project": "<PROJECT_ID>"}``、
        失敗時は ``{"status": "error", "error": "<ERROR_MESSAGE>"}``。
    """
    try:
        completed = subprocess.run(
            _GCLOUD_COMMAND,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return {"status": "error", "error": "gcloud CLI is not installed or not found in PATH"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "Command execution timed out"}

    if completed.returncode != 0:
        detail = (completed.stderr or "").strip() or "gcloud command failed"
        return {"status": "error", "error": detail}

    project = (completed.stdout or "").strip()
    if project in ("", "(unset)"):
        return {"status": "error", "error": "GCP project is not set"}
    return {"status": "success", "project": project}
