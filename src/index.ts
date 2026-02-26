// OpenTelemetryの初期化を最初に実行
import { startTracing } from './config/tracing.js';
await startTracing();

import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { httpInstrumentationMiddleware } from '@hono/otel';
import { config, validateConfig } from './config/config.js';
import logging from './routes/logging.js';
import monitoring from './routes/monitoring.js';
import trace from './routes/trace.js';
import telemetry from './routes/telemetry.js';

// アプリケーション設定の検証
const configValidation = validateConfig();
if (!configValidation.isValid) {
  console.error('Application configuration errors:');
  configValidation.errors.forEach((error: string) => console.error(`- ${error}`));
  process.exit(1);
}

console.log(`Application configuration:`);
console.log(`- Project ID: ${config.projectId}`);
console.log(`- Environment: ${config.nodeEnv}`);
console.log(`- Port: ${config.port}`);

const app = new Hono();

// otelミドルウェアをアプリケーション全体に適用（HonoのルーティングをSpan名に反映）
// ヘルスチェックエンドポイントはトレースから除外
const otelMiddleware = httpInstrumentationMiddleware();
app.use('*', (c, next) => {
  if (c.req.path === '/health') return next();
  return otelMiddleware(c, next);
});

// 基本ルート
app.get('/', (c) => {
  return c.text('Hello Hono!');
});

// トップレベルのヘルスチェックエンドポイント
// GCLB/GKE から渡されるトレース関連ヘッダーをログ出力する
app.get('/health', (c) => {
  const traceparent = c.req.header('traceparent') || null;
  const xCloudTraceContext = c.req.header('x-cloud-trace-context') || null;

  return c.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    headers: {
      traceparent,
      'x-cloud-trace-context': xCloudTraceContext,
    },
  });
});

// monitoringルートを統合
app.route('/monitoring', monitoring);

// loggingルートを統合
app.route('/logging', logging);

// traceルートを統合
app.route('/trace', trace);

// telemetryルートを統合（Telemetry API OTLP直接送信デモ）
app.route('/telemetry', telemetry);

serve(
  {
    fetch: app.fetch,
    port: config.port,
  },
  (info) => {
    console.log(`Server is running on http://localhost:${info.port}`);
    console.log(`Health check available at: http://localhost:${info.port}/health`);
  },
);
