import { HttpInstrumentation } from '@opentelemetry/instrumentation-http';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { SimpleLogRecordProcessor } from '@opentelemetry/sdk-logs';
import { PeriodicExportingMetricReader, AggregationTemporality } from '@opentelemetry/sdk-metrics';
import { NodeSDK } from '@opentelemetry/sdk-node';
import { CompositePropagator, ExportResultCode, hrTimeToTimeStamp, W3CTraceContextPropagator } from '@opentelemetry/core';
import { CloudPropagator } from '@google-cloud/opentelemetry-cloud-trace-propagator';
import { GoogleAuth } from 'google-auth-library';
import type { AuthClient } from 'google-auth-library';
import type { ExportResult } from '@opentelemetry/core';
import type { ReadableSpan, SpanExporter } from '@opentelemetry/sdk-trace';
import type { LogRecordExporter, ReadableLogRecord } from '@opentelemetry/sdk-logs';
import type { ResourceMetrics } from '@opentelemetry/sdk-metrics';
import { config } from './config.js';

/**
 * OpenTelemetryの初期化
 * トレース・メトリクスは Google Cloud Telemetry API (OTLP) へ直接送信する。
 * ログは OTel Logs SDK で生成し、標準出力へ Cloud Logging 形式の JSON として書き出す
 * （Cloud Run が cloud_run_revision のログとして取り込み、リクエストログと trace で紐づく）。
 * 参考: https://cloud.google.com/stackdriver/docs/reference/telemetry/overview
 */

const TELEMETRY_ENDPOINTS = {
  traces: 'https://telemetry.googleapis.com/v1/traces',
  metrics: 'https://telemetry.googleapis.com/v1/metrics',
} as const;

type Signal = keyof typeof TELEMETRY_ENDPOINTS;

/**
 * GoogleAuthOTLPExporter が包む「内部エクスポーター」に要求する最小限の形。
 * OTLPTraceExporter / OTLPLogExporter / OTLPMetricExporter はいずれもこの形を満たす。
 */
interface InnerExporter<T> {
  export(data: T, resultCallback: (result: ExportResult) => void): void;
  shutdown(): Promise<void>;
  forceFlush?(): Promise<void>;
}

/**
 * トークン自動更新機能付き OTLP エクスポーター（トレース・メトリクス共通）
 *
 * OTLP*Exporter は初期化時に Authorization ヘッダーを固定するため、
 * アクセストークン（有効期間 ~1 時間）の期限切れ後に 401 エラーが発生する。
 * このクラスは export() の都度 google-auth-library で最新トークンを取得し、
 * トークンが変わった場合にのみ内部エクスポーターを再生成することで自動更新を実現する。
 *
 * シグナル（trace/metric）ごとに内部エクスポーターの型が異なるため、
 * ジェネリック型 T（export() に渡されるデータの型）で抽象化している。
 * export() の引数型がシグナルごとに異なる（ReadableSpan[] / ResourceMetrics）ため、
 * 単一の implements 節では全シグナルを両立できない。よって明示的な implements は付けず、
 * TypeScript の構造的部分型に委ねる。
 */
class GoogleAuthOTLPExporter<T> {
  private readonly authClient: AuthClient;
  private readonly signal: Signal;
  private readonly buildExporter: (headers: Record<string, string>) => InnerExporter<T>;
  private innerExporter: InnerExporter<T> | null = null;
  private cachedToken: string | null = null;

  constructor(
    authClient: AuthClient,
    signal: Signal,
    buildExporter: (headers: Record<string, string>) => InnerExporter<T>,
  ) {
    this.authClient = authClient;
    this.signal = signal;
    this.buildExporter = buildExporter;
  }

  private async resolveExporter(): Promise<InnerExporter<T>> {
    const { token } = await this.authClient.getAccessToken();
    if (!token) {
      throw new Error('Failed to obtain access token from Application Default Credentials');
    }

    // トークンが変わった場合のみ内部エクスポーターを再生成
    if (token !== this.cachedToken || this.innerExporter === null) {
      void this.innerExporter?.shutdown();
      this.cachedToken = token;

      // ユーザー認証情報（authorized_user）の場合、
      // x-goog-user-project ヘッダーでクォータプロジェクトを明示する必要がある
      const quotaProject = process.env.GOOGLE_CLOUD_QUOTA_PROJECT ?? '';
      const headers: Record<string, string> = {
        Authorization: `Bearer ${token}`,
        ...(quotaProject ? { 'x-goog-user-project': quotaProject } : {}),
      };

      this.innerExporter = this.buildExporter(headers);
    }

    return this.innerExporter;
  }

  // 成功時はログを出さず、失敗時のみ console.error で記録する
  export(data: T, resultCallback: (result: ExportResult) => void): void {
    this.resolveExporter()
      .then((exporter) =>
        exporter.export(data, (result) => {
          if (result.error) {
            const err = result.error as { code?: number; data?: string; message: string; stack?: string };
            console.error(
              `[OTel:export:${this.signal}] FAILED: ${err.message} code=${err.code ?? '?'} data=${err.data ?? '(none)'}`,
              err.stack ?? '',
            );
          }
          resultCallback(result);
        }),
      )
      .catch((err: Error) => {
        console.error(`[OTel:export:${this.signal}] ERROR (token/auth): ${err.message}`, err.stack ?? '');
        resultCallback({ code: ExportResultCode.FAILED, error: err });
      });
  }

  async shutdown(): Promise<void> {
    await this.innerExporter?.shutdown();
    this.innerExporter = null;
  }

  async forceFlush(): Promise<void> {
    await this.innerExporter?.forceFlush?.();
  }

  selectAggregationTemporality(): AggregationTemporality {
    // Cloud Monitoring は Delta temporality の UpDownCounter に非対応なため、常に Cumulative を使う
    return AggregationTemporality.CUMULATIVE;
  }
}

/**
 * 標準出力の構造化ログで Cloud Logging が LogEntry のフィールドとして解釈するキー
 * 参考: https://cloud.google.com/logging/docs/structured-logging#special-payload-fields
 */
const RESERVED_LOG_ENTRY_KEYS = new Set(['severity', 'httpRequest', 'time', 'timestamp', 'timestampSeconds', 'timestampNanos']);

function isReservedLogEntryKey(key: string): boolean {
  return RESERVED_LOG_ENTRY_KEYS.has(key) || key.startsWith('logging.googleapis.com/');
}

/**
 * OTel の LogRecord を Cloud Logging の構造化 JSON として標準出力へ書き出すエクスポーター
 *
 * Telemetry API (OTLP) で送ったログは resource.type が generic_task になり、
 * trace も「trace_id のみ」で保存されるため、Cloud Run のリクエストログ
 * （trace = projects/PROJECT_ID/traces/TRACE_ID）と入れ子表示にならない。
 * 標準出力の JSON 行は Cloud Run が cloud_run_revision のログとして取り込み、
 * logging.googleapis.com/* の特殊フィールドで trace/spanId を指定できるため、リクエストログと紐づく。
 * 参考: https://cloud.google.com/logging/docs/structured-logging
 */
class CloudLoggingStdoutLogExporter implements LogRecordExporter {
  export(logs: ReadableLogRecord[], resultCallback: (result: ExportResult) => void): void {
    for (const record of logs) {
      process.stdout.write(`${JSON.stringify(this.toLogEntry(record))}\n`);
    }
    resultCallback({ code: ExportResultCode.SUCCESS });
  }

  private toLogEntry(record: ReadableLogRecord): Record<string, unknown> {
    const { body, spanContext } = record;
    const payload = body !== null && typeof body === 'object' && !Array.isArray(body) ? body : { message: body };
    return {
      // body にはリクエスト由来の値が入りうるため、Cloud Logging が特別扱いするキーを除外したうえで先に展開し、
      // 後続のサーバー側で決める値（severity / timestamp / trace 等）で上書きされないようにする
      ...Object.fromEntries(Object.entries(payload).filter(([key]) => !isReservedLogEntryKey(key))),
      severity: record.severityText ?? 'DEFAULT',
      // 書き出し時刻ではなく LogRecord の発生時刻を使う
      // RFC 3339 文字列で指定できる特殊フィールドは `time`（`timestamp` は {seconds, nanos} のオブジェクト形式のみ）
      time: hrTimeToTimeStamp(record.hrTime),
      ...(spanContext
        ? {
            'logging.googleapis.com/trace': `projects/${config.projectId}/traces/${spanContext.traceId}`,
            'logging.googleapis.com/spanId': spanContext.spanId,
            'logging.googleapis.com/trace_sampled': (spanContext.traceFlags & 1) === 1,
          }
        : {}),
    };
  }

  async shutdown(): Promise<void> {}

  async forceFlush(): Promise<void> {}
}

let sdk: NodeSDK | null = null;

/**
 * OpenTelemetryを起動
 * アプリケーション起動時に最初に呼び出す必要がある
 * ADC (Application Default Credentials) を使用して認証クライアントを生成し、
 * Google Cloud Telemetry API に直接 OTLP でトレース・メトリクスを送信する（ログは標準出力）
 */
export async function startOpenTelemetry(): Promise<void> {
  try {
    // ADC クライアントを生成（トークン取得はエクスポート時に動的に行う）
    // Telemetry API (OTLP) には cloud-platform スコープが必要
    // ※ trace.append は Cloud Trace 旧 API 用であり Telemetry API には使えない
    const auth = new GoogleAuth({
      scopes: ['https://www.googleapis.com/auth/cloud-platform'],
    });
    const authClient = await auth.getClient();

    // 起動時に一度トークン取得を試みて認証が機能しているか確認
    const { token: initToken } = await authClient.getAccessToken();
    if (!initToken) {
      throw new Error('Failed to obtain access token from Application Default Credentials');
    }

    // Google Cloud Telemetry API (OTLP) エンドポイントに直接送信するエクスポーター
    const traceExporter = new GoogleAuthOTLPExporter<ReadableSpan[]>(
      authClient,
      'traces',
      (headers) => new OTLPTraceExporter({ url: TELEMETRY_ENDPOINTS.traces, headers }),
    );
    const metricExporter = new GoogleAuthOTLPExporter<ResourceMetrics>(
      authClient,
      'metrics',
      (headers) => new OTLPMetricExporter({ url: TELEMETRY_ENDPOINTS.metrics, headers }),
    );

    sdk = new NodeSDK({
      traceExporter,
      // 即時に書き出し、ログの出力順・時刻をリクエスト処理と揃える
      logRecordProcessors: [new SimpleLogRecordProcessor({ exporter: new CloudLoggingStdoutLogExporter() })],
      metricReaders: [
        new PeriodicExportingMetricReader({
          exporter: metricExporter,
          // 同期Gaugeは直近にrecordされた値のみエクスポートされるため、
          // /monitoring/custom-metrics/continuous デモ（デフォルト10秒間隔で書き込む）の
          // 書き込み間隔とメトリクスリーダーの収集間隔を合わせないと、
          // 収集タイミングの間に上書きされた値が失われ、大半の書き込みが欠落して見える
          exportIntervalMillis: 10_000,
        }),
      ],
      // traceparent および X-Cloud-Trace-Context からのトレースコンテキストを解釈できるように、
      // W3C Trace Context と Cloud Trace 用プロパゲータの両方を登録する
      instrumentations: [
        new HttpInstrumentation({
          ignoreIncomingRequestHook: (req) => {
            // GKEのヘルスチェックエンドポイントはトレースから除外
            return req.url === '/health';
          },
        }),
      ],
      textMapPropagator: new CompositePropagator({
        propagators: [new W3CTraceContextPropagator(), new CloudPropagator()],
      }),
    });

    sdk.start();
  } catch (error) {
    console.error('[OTel:init] FAILED to initialize:', error);
    // OpenTelemetry初期化に失敗してもアプリケーションは起動させる
  }
}

/**
 * アプリケーション終了時のクリーンアップ
 */
export async function stopOpenTelemetry(): Promise<void> {
  if (!sdk) return;
  try {
    await sdk.shutdown();
  } catch (error) {
    console.error('Failed to shut down OpenTelemetry:', error);
  }
}

// プロセス終了時のクリーンアップ
process.on('SIGTERM', async () => {
  await stopOpenTelemetry();
  process.exit(0);
});

process.on('SIGINT', async () => {
  await stopOpenTelemetry();
  process.exit(0);
});
