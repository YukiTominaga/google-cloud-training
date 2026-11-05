"""agy の Stop hook から呼び出し、直近 1 ターンの実行を親子関係付きの trace として送信する。

hook は実行ごとに別プロセスのため、transcript.jsonl から階層を再構築する。
  agy.turn (ユーザー入力 → 応答完了)
   └ agy.model_call (モデル呼び出し。トークン数)
      └ agy.tool.<名前> (ツール呼び出し)

trace_id / span_id は会話 ID とステップ番号から決定的に生成する。
認証は ADC(Application Default Credentials)を使用する。
プロジェクト ID は環境変数 GOOGLE_CLOUD_PROJECT(未設定なら ADC のプロジェクト)。
環境変数 AGY_OTEL_DRY_RUN=1 で、送信せず標準出力にスパンを表示する。
使い方: otel_gcp.py <イベント名>   (hook の入力 JSON は標準入力から受け取る)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import IdGenerator, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import Status, StatusCode

ENDPOINT = "https://telemetry.googleapis.com"
MIN_DURATION_NS = 1_000_000  # 秒精度の時刻で長さ 0 になるのを避ける(1ms)


def _hash_int(key: str, nbytes: int) -> int:
    """キー文字列から決定的な整数 ID を作る(0 は無効値のため避ける)。"""
    value = int.from_bytes(hashlib.sha256(key.encode()).digest()[:nbytes], "big")
    return value or 1


class _FixedIdGenerator(IdGenerator):
    """直前に設定した ID を返す ID 生成器。スパン ID を決定的にするために使う。"""

    def __init__(self) -> None:
        self.next_trace_id = 1
        self.next_span_id = 1

    def generate_span_id(self) -> int:
        return self.next_span_id

    def generate_trace_id(self) -> int:
        return self.next_trace_id



# 機密値をマスクするパターン(キー名は残し、値だけ伏せる)
_SECRET_PATTERNS = [
    # --token xxx / --password=xxx / api_key=xxx / secret: xxx など
    (
        re.compile(
            r"(?i)(--?[\w-]*(?:token|password|passwd|secret|api[-_]?key)[\w-]*[=\s:]+)"
            r"(\"[^\"]*\"|'[^']*'|\S+)"
        ),
        r"\1***",
    ),
    # 環境変数形式 FOO_TOKEN=xxx
    (
        re.compile(r"(?i)\b(\w*(?:token|password|passwd|secret|api_?key)\w*=)(\S+)"),
        r"\1***",
    ),
    # Authorization ヘッダー / Bearer トークン
    (re.compile(r"(?i)(bearer\s+)[\w.~+/=-]+"), r"\1***"),
    # Google の OAuth アクセストークン、AWS アクセスキー、GitHub トークン
    (re.compile(r"\bya29\.[\w.-]+"), "***"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "***"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "***"),
]


def _mask(text: str) -> str:
    """機密情報らしき値を伏せ字にする。"""
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def _extract_user_request(content: str) -> str:
    """ユーザー入力から <USER_REQUEST> タグの中身だけを取り出す。タグがなければ全文を返す。"""
    match = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", content, re.DOTALL)
    return match.group(1) if match else content


def _tool_arg_attrs(call: dict[str, Any]) -> dict[str, str]:
    """ツール呼び出しの引数から、スパン属性にする値を取り出す。

    run_command はコマンド、ファイル系ツールはパス、検索系はクエリ、
    サブエージェント呼び出しは種別を対象とする。
    ファイルの内容やプロンプト本文など大きな引数は送らない。
    コマンド・クエリは機密値をマスクしたうえで送る。
    """
    args = call.get("args") or {}
    attrs: dict[str, str] = {}

    def put(key: str, value: Any, mask: bool = False) -> None:
        text = str(value).strip('"')
        attrs[key] = _mask(text) if mask else text

    if args.get("CommandLine"):
        put("agy.tool.command", args["CommandLine"], mask=True)
    # transcript では引用符で囲まれた文字列として記録されることがある
    path = args.get("Path") or args.get("AbsolutePath") or args.get("TargetFile")
    if path:
        put("agy.tool.file_path", path)
    if args.get("query"):
        put("agy.tool.query", args["query"], mask=True)
    if args.get("TypeName"):
        put("agy.tool.subagent_type", args["TypeName"])
    if args.get("Role"):
        put("agy.tool.subagent_role", args["Role"])
    if args.get("Prompt"):
        put("agy.tool.subagent_prompt", args["Prompt"], mask=True)
    return attrs


def _to_ns(timestamp: str) -> int:
    """ISO 8601 (例: 2026-11-05T03:43:16Z) をナノ秒のエポック時刻へ変換する。"""
    return int(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp() * 1e9)


def _read_last_turn(transcript_path: str) -> list[dict[str, Any]]:
    """transcript.jsonl から、直近のユーザー入力以降のステップを返す。"""
    steps = [
        json.loads(line)
        for line in Path(transcript_path).read_text().splitlines()
        if line.strip()
    ]
    last_user = max(
        (i for i, s in enumerate(steps) if s.get("type") == "USER_INPUT"), default=0
    )
    return steps[last_user:]


def _build_spans(
    steps: list[dict[str, Any]],
    conversation_id: str,
    model_name: str,
    tracer: trace.Tracer,
    ids: _FixedIdGenerator,
) -> None:
    """ステップ列から親子関係付きのスパンを生成する。"""
    if not steps:
        return
    first = steps[0]
    turn_key = f"{conversation_id}:{first.get('step_index')}"
    ids.next_trace_id = _hash_int(turn_key, 16)

    # 各ステップの終了時刻 = 次ステップの開始時刻。
    # 最後のステップは、transcript の時刻が秒精度で長さ 0 になりやすいため、
    # hook の実行時刻(ターン終了直後)を終了時刻とする
    starts = [_to_ns(s["created_at"]) for s in steps]
    now_ns = time.time_ns()
    ends = [
        starts[i + 1] if i + 1 < len(steps) else max(now_ns, starts[i] + MIN_DURATION_NS)
        for i in range(len(steps))
    ]

    def make_span(
        name: str, key: str, start: int, end: int, parent: Any | None, attrs: dict
    ) -> trace.Span:
        ids.next_span_id = _hash_int(f"{turn_key}:{key}", 8)
        ctx = trace.set_span_in_context(parent) if parent else None
        span = tracer.start_span(name, context=ctx, start_time=start, attributes=attrs)
        span.end(end_time=max(end, start + MIN_DURATION_NS))
        return span

    # 親スパンは終了時刻が確定してから ID を参照するため、先に開始だけ行う
    ids.next_span_id = _hash_int(f"{turn_key}:turn", 8)
    turn = tracer.start_span(
        "agy.turn",
        start_time=starts[0],
        attributes={
            "agy.conversation_id": conversation_id,
            "agy.model": model_name,
            "agy.user_input": _mask(_extract_user_request(str(first.get("content", "")))),
        },
    )

    total_in = total_out = 0
    i = 1
    while i < len(steps):
        step = steps[i]
        if step.get("type") != "PLANNER_RESPONSE":
            i += 1
            continue
        in_tok = int(step.get("input_tokens", 0))
        out_tok = int(step.get("output_tokens", 0))
        total_in += in_tok
        total_out += out_tok
        tool_calls = step.get("tool_calls") or []

        # このモデル呼び出しに対応するツール結果ステップ(次の応答/入力の手前まで)
        j = i + 1
        while j < len(steps) and steps[j].get("type") not in (
            "PLANNER_RESPONSE",
            "USER_INPUT",
        ):
            j += 1
        result_idx = list(range(i + 1, j))

        model_end = ends[j - 1] if j - 1 > i else ends[i]
        cache_tok = int(step.get("cache_read_tokens", 0))
        total_in_tok = in_tok + cache_tok
        ids.next_span_id = _hash_int(f"{turn_key}:model:{i}", 8)
        model = tracer.start_span(
            "agy.model_call",
            context=trace.set_span_in_context(turn),
            start_time=starts[i],
            attributes={
                "gen_ai.operation.name": "chat",
                "gen_ai.request.model": model_name,
                "gen_ai.usage.input_tokens": in_tok,
                "gen_ai.usage.output_tokens": out_tok,
                "gen_ai.usage.cache_read.input_tokens": cache_tok,
                # キャッシュ分を含む入力トークン合計と、そのうちキャッシュが占める割合
                "agy.total_input_tokens": total_in_tok,
                "agy.cache_hit_ratio": round(cache_tok / total_in_tok, 3)
                if total_in_tok
                else 0.0,
                "agy.step_index": int(step.get("step_index", i)),
                "agy.status": str(step.get("status", "")),
                # ツール呼び出しで終わったか、最終回答で終わったか
                "gen_ai.response.finish_reasons": ["tool_calls" if tool_calls else "stop"],
                "agy.tool_call_count": len(tool_calls),
                "agy.response_chars": len(str(step.get("content", ""))),
                "agy.thinking_chars": len(str(step.get("thinking", ""))),
                # 応答と思考の本文(機密値はマスク済み)
                "agy.response": _mask(str(step.get("content", ""))),
                "agy.thinking": _mask(str(step.get("thinking", ""))),
            },
        )

        for n, call in enumerate(tool_calls):
            if n < len(result_idx):
                r = result_idx[n]
                t_start, t_end = starts[r], ends[r]
                failed = steps[r].get("status") == "ERROR"
            else:
                t_start, t_end, failed = starts[i], ends[i], False
            make_span(
                f"agy.tool.{call.get('name', 'unknown')}",
                f"tool:{i}:{n}",
                t_start,
                t_end,
                model,
                {
                    "agy.tool_name": str(call.get("name", "")),
                    "agy.tool_error": failed,
                    **_tool_arg_attrs(call),
                },
            )
        model.end(end_time=max(model_end, starts[i] + MIN_DURATION_NS))
        i = j

    turn.set_attribute("gen_ai.usage.input_tokens", total_in)
    turn.set_attribute("gen_ai.usage.output_tokens", total_out)
    turn.set_status(Status(StatusCode.OK))
    turn.end(end_time=max(ends[-1], starts[0] + MIN_DURATION_NS))


def _build_provider(ids: _FixedIdGenerator) -> TracerProvider:
    """送信先(Google Cloud / ドライラン)に応じた TracerProvider を作る。"""
    if os.environ.get("AGY_OTEL_DRY_RUN") == "1":
        provider = TracerProvider(
            resource=Resource.create({"service.name": "antigravity-cli"}),
            id_generator=ids,
        )
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        return provider

    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    # ADC から認証情報を取得し、クォータ課金先プロジェクトを指定する
    credentials, adc_project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    # プロジェクト ID は環境変数を優先し、未設定なら ADC のプロジェクトを使う
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or adc_project
    if not project_id:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT が未設定です")
    session = AuthorizedSession(credentials)
    session.headers["x-goog-user-project"] = project_id

    # 400 などの失敗時に原因を追えるよう、エラー応答の本文を stderr に出す
    def _log_error(response, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        if response.status_code >= 400:
            print(f"OTLP エラー {response.status_code}: {response.text}", file=sys.stderr)

    session.hooks["response"].append(_log_error)

    resource = Resource.create(
        {"service.name": "antigravity-cli", "gcp.project_id": project_id}
    )
    provider = TracerProvider(resource=resource, id_generator=ids)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{ENDPOINT}/v1/traces", session=session)
        )
    )
    return provider


def main() -> None:
    payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    transcript_path = payload.get("transcriptPath")
    if not transcript_path:
        raise RuntimeError("入力に transcriptPath がありません")

    ids = _FixedIdGenerator()
    provider = _build_provider(ids)
    tracer = provider.get_tracer("agy.hooks")

    _build_spans(
        _read_last_turn(transcript_path),
        str(payload.get("conversationId", "")),
        str(payload.get("modelName", "")),
        tracer,
        ids,
    )
    # 短命プロセスのため、終了前に送信する
    provider.shutdown()


if __name__ == "__main__":
    try:
        main()
        print(json.dumps({"success": True}))
    except Exception as e:  # telemetry の失敗でエージェントを止めない
        print(json.dumps({"success": True, "message": f"telemetry 送信失敗: {e}"}))
