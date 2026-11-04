import subprocess
from typing import Any

from gcp_assistant.tools import get_current_gcp_project
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/get_current_gcp_project.feature")


@given("gcloud CLI is installed")
def gcloud_installed() -> None:
    """Marker step that gcloud CLI is installed."""


@given(parsers.parse('gcloud config has active project "{project_id}"'))
def mock_gcloud_success(monkeypatch: Any, project_id: str) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args[0] if args else kwargs.get("args"),
            returncode=0,
            stdout=f"{project_id}\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)


@given(parsers.parse('gcloud command fails with error "{error_message}"'))
def mock_gcloud_failure(monkeypatch: Any, error_message: str) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args[0] if args else kwargs.get("args"),
            returncode=1,
            stdout="",
            stderr=error_message,
        )

    monkeypatch.setattr(subprocess, "run", fake_run)


@given(parsers.parse('gcloud command succeeds with output "{output}"'))
def mock_gcloud_output(monkeypatch: Any, output: str) -> None:
    """終了コード 0 で任意の標準出力を返す gcloud を模擬する。"""

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args[0] if args else kwargs.get("args"),
            returncode=0,
            stdout=f"{output}\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)


@given(
    parsers.parse('gcloud config has active project "{project_id}" and calls are recorded'),
    target_fixture="recorded_calls",
)
def mock_gcloud_recorded(monkeypatch: Any, project_id: str) -> list[dict[str, Any]]:
    """subprocess.run の呼び出し引数を記録しつつ成功を返す gcloud を模擬する。"""
    calls: list[dict[str, Any]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"args": args, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            args=args[0] if args else kwargs.get("args"),
            returncode=0,
            stdout=f"{project_id}\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


@given("gcloud CLI is not installed")
def mock_gcloud_not_installed(monkeypatch: Any) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("[Errno 2] No such file or directory: 'gcloud'")

    monkeypatch.setattr(subprocess, "run", fake_run)


@given("gcloud command times out")
def mock_gcloud_timeout(monkeypatch: Any) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            cmd=["gcloud", "config", "get-value", "project"],
            timeout=5,
        )

    monkeypatch.setattr(subprocess, "run", fake_run)


@when("get_current_gcp_project is called")
def call_get_current_gcp_project(bdd_context: dict[str, Any]) -> None:
    bdd_context["result"] = get_current_gcp_project()


@then(parsers.parse('the result status should be "{expected_status}"'))
def verify_status(bdd_context: dict[str, Any], expected_status: str) -> None:
    assert bdd_context["result"]["status"] == expected_status


@then(parsers.parse('the result project should be "{expected_project}"'))
def verify_project(bdd_context: dict[str, Any], expected_project: str) -> None:
    assert bdd_context["result"].get("project") == expected_project


@then(parsers.parse('the result error message should contain "{expected_error}"'))
def verify_error_contains(bdd_context: dict[str, Any], expected_error: str) -> None:
    error_message = bdd_context["result"].get("error", "")
    assert expected_error in error_message


@then("gcloud should have been invoked without a shell")
def verify_no_shell(recorded_calls: list[dict[str, Any]]) -> None:
    """shell=True が使われておらず、引数がリスト形式であることを検証する。"""
    assert recorded_calls
    for call in recorded_calls:
        assert not call["kwargs"].get("shell", False)
        command = call["args"][0] if call["args"] else call["kwargs"].get("args")
        assert isinstance(command, list)


@then("gcloud should have been invoked with a finite timeout")
def verify_timeout(recorded_calls: list[dict[str, Any]]) -> None:
    """有限のタイムアウトが指定されていることを検証する。"""
    assert recorded_calls
    for call in recorded_calls:
        timeout = call["kwargs"].get("timeout")
        assert isinstance(timeout, (int, float)) and timeout > 0
