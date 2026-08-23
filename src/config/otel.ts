import { HttpInstrumentation } from '@opentelemetry/instrumentation-http';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { OTLPLogExporter } from '@opentelemetry/exporter-logs-otlp-http';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { BatchLogRecordProcessor } from '@opentelemetry/sdk-logs';
import { PeriodicExportingMetricReader, AggregationTemporality } from '@opentelemetry/sdk-metrics';
import { NodeSDK } from '@opentelemetry/sdk-node';
import { CompositePropagator, ExportResultCode, W3CTraceContextPropagator } from '@opentelemetry/core';
import { CloudPropagator } from '@google-cloud/opentelemetry-cloud-trace-propagator';
import { GoogleAuth } from 'google-auth-library';
import type { AuthClient } from 'google-auth-library';
import type { ExportResult } from '@opentelemetry/core';
import type { ReadableSpan, SpanExporter } from '@opentelemetry/sdk-trace-base';
import type { ReadableLogRecord } from '@opentelemetry/sdk-logs';
import type { ResourceMetrics } from '@opentelemetry/sdk-metrics';

/**
 * OpenTelemetryの初期化
 * Google Cloud Telemetry API (OTLP) へ直接トレース・メトリクス・ログを送信するための設定
 * 参考: https://cloud.google.com/stackdriver/docs/reference/telemetry/overview
 */

const TELEMETRY_ENDPOINTS = {
  traces: 'https://telemetry.googleapis.com/v1/traces',
  metrics: 'https://telemetry.googleapis.com/v1/metrics',
  logs: 'https://telemetry.googleapis.com/v1/logs',
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
 * トークン自動更新機能付き OTLP エクスポーター（トレース・メトリクス・ログ共通）
 *
 * OTLP*Exporter は初期化時に Authorization ヘッダーを固定するため、
 * アクセストークン（有効期間 ~1 時間）の期限切れ後に 401 エラーが発生する。
 * このクラスは export() の都度 google-auth-library で最新トークンを取得し、
 * トークンが変わった場合にのみ内部エクスポーターを再生成することで自動更新を実現する。
 *
 * シグナル（trace/metric/log）ごとに内部エクスポーターの型が異なるため、
 * ジェネリック型 T（export() に渡されるデータの型）で抽象化している。
 * export() の引数型がシグナルごとに異なる（ReadableSpan[] / ResourceMetrics / ReadableLogRecord[]）ため、
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
      const isRefresh = this.cachedToken !== null;
      this.cachedToken = token;

      // ユーザー認証情報（authorized_user）の場合、
      // x-goog-user-project ヘッダーでクォータプロジェクトを明示する必要がある
      const quotaProject = process.env.GOOGLE_CLOUD_QUOTA_PROJECT ?? '';
      const headers: Record<string, string> = {
        Authorization: `Bearer ${token}`,
        ...(quotaProject ? { 'x-goog-user-project': quotaProject } : {}),
      };

      this.innerExporter = this.buildExporter(headers);

      console.log(
        `[OTel:token:${this.signal}] ${isRefresh ? 'refreshed' : 'initialized'}` +
          ` token=${token.slice(0, 10)}...` +
          ` quota-project=${quotaProject || '(none)'}` +
          ` auth-type=${this.authClient.constructor.name}`,
      );
    }

    return this.innerExporter;
  }

  export(data: T, resultCallback: (result: ExportResult) => void): void {
    console.log(`[OTel:export:${this.signal}] exporting`);

    this.resolveExporter()
      .then((exporter) =>
        exporter.export(data, (result) => {
          if (result.error) {
            const err = result.error as { code?: number; data?: string; message: string; stack?: string };
            console.error(
              `[OTel:export:${this.signal}] FAILED: ${err.message} code=${err.code ?? '?'} data=${err.data ?? '(none)'}`,
              err.stack ?? '',
            );
          } else {
            console.log(`[OTel:export:${this.signal}] OK`);
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

let sdk: NodeSDK | null = null;

/**
 * OpenTelemetryを起動
 * アプリケーション起動時に最初に呼び出す必要がある
 * ADC (Application Default Credentials) を使用して認証クライアントを生成し、
 * Google Cloud Telemetry API に直接 OTLP でトレース・メトリクス・ログを送信する
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

    console.log('[OTel:init] auth ok');
    console.log(`[OTel:init]   auth-type         : ${authClient.constructor.name}`);
    console.log(`[OTel:init]   endpoint (traces)  : ${TELEMETRY_ENDPOINTS.traces}`);
    console.log(`[OTel:init]   endpoint (metrics) : ${TELEMETRY_ENDPOINTS.metrics}`);
    console.log(`[OTel:init]   endpoint (logs)    : ${TELEMETRY_ENDPOINTS.logs}`);
    console.log(`[OTel:init]   GOOGLE_CLOUD_PROJECT      : ${process.env.GOOGLE_CLOUD_PROJECT ?? '(not set)'}`);
    console.log(`[OTel:init]   GOOGLE_CLOUD_QUOTA_PROJECT: ${process.env.GOOGLE_CLOUD_QUOTA_PROJECT ?? '(not set)'}`);
    console.log(`[OTel:init]   OTEL_RESOURCE_ATTRIBUTES  : ${process.env.OTEL_RESOURCE_ATTRIBUTES ?? '(not set)'}`);

    // Google Cloud Telemetry API (OTLP) エンドポイントに直接送信するエクスポーター
    const traceExporter = new GoogleAuthOTLPExporter<ReadableSpan[]>(
      authClient,
      'traces',
      (headers) => new OTLPTraceExporter({ url: TELEMETRY_ENDPOINTS.traces, headers }),
    );
    const logExporter = new GoogleAuthOTLPExporter<ReadableLogRecord[]>(
      authClient,
      'logs',
      (headers) => new OTLPLogExporter({ url: TELEMETRY_ENDPOINTS.logs, headers }),
    );
    const metricExporter = new GoogleAuthOTLPExporter<ResourceMetrics>(
      authClient,
      'metrics',
      (headers) => new OTLPMetricExporter({ url: TELEMETRY_ENDPOINTS.metrics, headers }),
    );

    sdk = new NodeSDK({
      traceExporter,
      logRecordProcessors: [new BatchLogRecordProcessor(logExporter)],
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
    console.log('[OTel:init] SDK started (traces + metrics + logs)');
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
    console.log('OpenTelemetry shut down successfully');
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
