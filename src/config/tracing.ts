import { HttpInstrumentation } from '@opentelemetry/instrumentation-http';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { NodeSDK } from '@opentelemetry/sdk-node';
import { CompositePropagator, ExportResultCode, W3CTraceContextPropagator } from '@opentelemetry/core';
import { CloudPropagator } from '@google-cloud/opentelemetry-cloud-trace-propagator';
import { GoogleAuth } from 'google-auth-library';
import type { AuthClient } from 'google-auth-library';
import type { ExportResult } from '@opentelemetry/core';
import type { ReadableSpan, SpanExporter } from '@opentelemetry/sdk-trace-base';

/**
 * OpenTelemetryの初期化
 * Google Cloud Telemetry API (OTLP) へ直接トレースデータを送信するための設定
 * 参考: https://cloud.google.com/stackdriver/docs/reference/telemetry/overview
 */

const TELEMETRY_ENDPOINT = 'https://telemetry.googleapis.com/v1/traces';

/**
 * トークン自動更新機能付き OTLP トレースエクスポーター
 *
 * OTLPTraceExporter は初期化時に Authorization ヘッダーを固定するため、
 * アクセストークン（有効期間 ~1 時間）の期限切れ後に 401 エラーが発生する。
 * このクラスは export() の都度 google-auth-library で最新トークンを取得し、
 * トークンが変わった場合にのみ内部エクスポーターを再生成することで自動更新を実現する。
 */
class GoogleAuthOTLPExporter implements SpanExporter {
  private readonly authClient: AuthClient;
  private innerExporter: OTLPTraceExporter | null = null;
  private cachedToken: string | null = null;

  constructor(authClient: AuthClient) {
    this.authClient = authClient;
  }

  private async resolveExporter(): Promise<OTLPTraceExporter> {
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

      this.innerExporter = new OTLPTraceExporter({
        url: TELEMETRY_ENDPOINT,
        headers,
      });

      console.log(
        `[OTel:token] ${isRefresh ? 'refreshed' : 'initialized'}` +
          ` token=${token.slice(0, 10)}...` +
          ` quota-project=${quotaProject || '(none)'}` +
          ` auth-type=${this.authClient.constructor.name}`,
      );
    }

    return this.innerExporter;
  }

  export(spans: ReadableSpan[], resultCallback: (result: ExportResult) => void): void {
    console.log(`[OTel:export] exporting ${spans.length} span(s)`);

    this.resolveExporter()
      .then((exporter) =>
        exporter.export(spans, (result) => {
          if (result.error) {
            console.error(
              `[OTel:export] FAILED: ${result.error.message}`,
              result.error.stack ?? '',
            );
          } else {
            console.log(`[OTel:export] OK: ${spans.length} span(s) sent`);
          }
          resultCallback(result);
        }),
      )
      .catch((err: Error) => {
        console.error(`[OTel:export] ERROR (token/auth): ${err.message}`, err.stack ?? '');
        resultCallback({ code: ExportResultCode.FAILED, error: err });
      });
  }

  async shutdown(): Promise<void> {
    await this.innerExporter?.shutdown();
    this.innerExporter = null;
  }
}

let sdk: NodeSDK | null = null;

/**
 * OpenTelemetryを起動
 * アプリケーション起動時に最初に呼び出す必要がある
 * ADC (Application Default Credentials) を使用して認証クライアントを生成し、
 * Google Cloud Telemetry API に直接 OTLP で送信する
 */
export async function startTracing(): Promise<void> {
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
    console.log(`[OTel:init]   endpoint           : ${TELEMETRY_ENDPOINT}`);
    console.log(`[OTel:init]   GOOGLE_CLOUD_PROJECT      : ${process.env.GOOGLE_CLOUD_PROJECT ?? '(not set)'}`);
    console.log(`[OTel:init]   GOOGLE_CLOUD_QUOTA_PROJECT: ${process.env.GOOGLE_CLOUD_QUOTA_PROJECT ?? '(not set)'}`);
    console.log(`[OTel:init]   OTEL_RESOURCE_ATTRIBUTES  : ${process.env.OTEL_RESOURCE_ATTRIBUTES ?? '(not set)'}`);

    // Google Cloud Telemetry API (OTLP) エンドポイントに直接送信するエクスポーター
    // traceparent および X-Cloud-Trace-Context からのトレースコンテキストを解釈できるように、
    // W3C Trace Context と Cloud Trace 用プロパゲータの両方を登録する
    const traceExporter = new GoogleAuthOTLPExporter(authClient);

    sdk = new NodeSDK({
      traceExporter,
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
    console.log('[OTel:init] SDK started');
  } catch (error) {
    console.error('[OTel:init] FAILED to initialize:', error);
    // トレーシング初期化に失敗してもアプリケーションは起動させる
  }
}

/**
 * アプリケーション終了時のクリーンアップ
 */
export async function stopTracing(): Promise<void> {
  if (!sdk) return;
  try {
    await sdk.shutdown();
    console.log('OpenTelemetry tracing shut down successfully');
  } catch (error) {
    console.error('Failed to shut down OpenTelemetry:', error);
  }
}

// プロセス終了時のクリーンアップ
process.on('SIGTERM', async () => {
  await stopTracing();
  process.exit(0);
});

process.on('SIGINT', async () => {
  await stopTracing();
  process.exit(0);
});
