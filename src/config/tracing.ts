import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { NodeSDK } from '@opentelemetry/sdk-node';

/**
 * OpenTelemetryの初期化
 * Cloud Traceへトレースデータを送信するための設定
 * 参考: https://cloud.google.com/trace/docs/setup/nodejs-ot#config-otel
 */

// NodeSDKの設定と初期化
const sdk = new NodeSDK({
  traceExporter: new OTLPTraceExporter(),
  instrumentations: [getNodeAutoInstrumentations()],
});

/**
 * OpenTelemetryを起動
 * アプリケーション起動時に最初に呼び出す必要がある
 */
export function startTracing(): void {
  try {
    sdk.start();
    console.log('OpenTelemetry tracing initialized successfully');
  } catch (error) {
    console.error('Failed to initialize OpenTelemetry:', error);
    // トレーシング初期化に失敗してもアプリケーションは起動させる
  }
}

/**
 * アプリケーション終了時のクリーンアップ
 */
export async function stopTracing(): Promise<void> {
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
