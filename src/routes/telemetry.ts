/**
 * Telemetry API ルート
 *
 * Google Cloud Telemetry API (OTLP) へ直接トレースを送信するデモエンドポイント群。
 * src/config/tracing.ts で初期化された NodeSDK が
 * https://telemetry.googleapis.com/v1/traces へ OTLP/HTTP でエクスポートする。
 *
 * 参考: https://cloud.google.com/stackdriver/docs/instrumentation/migrate-to-otlp-endpoints
 */
import { Hono } from 'hono';
import { context, SpanKind, SpanStatusCode, trace } from '@opentelemetry/api';
import { config } from '../config/config.js';
import { LoggingService } from '../services/logging.service.js';

const telemetry = new Hono();

const tracer = trace.getTracer('telemetry-route', '1.0.0');
const loggingService = new LoggingService();

/**
 * GET /telemetry/basic
 * 単一の span を作成し Telemetry API へ送信するデモ
 */
telemetry.get('/basic', async (c) => {
  const span = tracer.startSpan('telemetry.basic', {
    kind: SpanKind.SERVER,
    attributes: {
      'telemetry.demo': true,
      'request.method': c.req.method,
      'request.path': c.req.path,
    },
  });

  try {
    return await context.with(trace.setSpan(context.active(), span), async () => {
      // span がアクティブなので logInfoWithContext のログには同じ traceId が付与される
      loggingService.logInfoWithContext(c, 'telemetry.basic: request received');

      await new Promise((resolve) => setTimeout(resolve, 50));

      span.setAttribute('processing.result', 'success');
      span.setStatus({ code: SpanStatusCode.OK });

      loggingService.logInfoWithContext(c, 'telemetry.basic: completed');

      return c.json({
        success: true,
        message: 'Single span created and sent to Google Cloud Telemetry API',
        traceId: span.spanContext().traceId,
        spanId: span.spanContext().spanId,
        exportEndpoint: 'https://telemetry.googleapis.com/v1/traces',
      });
    });
  } catch (error) {
    span.recordException(error as Error);
    span.setStatus({ code: SpanStatusCode.ERROR, message: (error as Error).message });
    return c.json({ success: false, error: (error as Error).message }, 500);
  } finally {
    span.end();
  }
});

/**
 * GET /telemetry/attributes
 * span に様々な属性・イベントを付与するデモ
 * OpenTelemetry の Semantic Conventions に沿った属性名を使用
 */
telemetry.get('/attributes', async (c) => {
  const span = tracer.startSpan('telemetry.attributes', {
    kind: SpanKind.SERVER,
    attributes: {
      // HTTP Semantic Conventions
      'http.method': c.req.method,
      'http.url': c.req.url,
      'http.route': '/telemetry/attributes',
      // Google Cloud project
      'gcp.project_id': config.projectId,
      // カスタム属性
      'demo.type': 'attributes',
    },
  });

  return await context.with(trace.setSpan(context.active(), span), async () => {
    try {
      loggingService.logInfoWithContext(c, 'telemetry.attributes: processing started');

      span.addEvent('processing.started', {
        'event.phase': 'start',
        'event.timestamp': Date.now(),
      });

      await new Promise((resolve) => setTimeout(resolve, 30));

      span.addEvent('processing.checkpoint', {
        'event.phase': 'checkpoint',
        'checkpoint.value': 42,
      });

      await new Promise((resolve) => setTimeout(resolve, 30));

      span.setAttribute('response.status', 200);
      span.setAttribute('response.items', 3);

      span.addEvent('processing.completed', { 'event.phase': 'end' });
      span.setStatus({ code: SpanStatusCode.OK });

      loggingService.logInfoWithContext(c, 'telemetry.attributes: completed', {
        responseItems: 3,
      });

      return c.json({
        success: true,
        message: 'Span with attributes and events sent to Google Cloud Telemetry API',
        traceId: span.spanContext().traceId,
        spanId: span.spanContext().spanId,
        addedAttributes: [
          'http.method',
          'http.url',
          'http.route',
          'gcp.project_id',
          'demo.type',
          'response.status',
          'response.items',
        ],
        addedEvents: ['processing.started', 'processing.checkpoint', 'processing.completed'],
      });
    } catch (error) {
      span.recordException(error as Error);
      span.setStatus({ code: SpanStatusCode.ERROR, message: (error as Error).message });
      return c.json({ success: false, error: (error as Error).message }, 500);
    } finally {
      span.end();
    }
  });
});

/**
 * GET /telemetry/nested
 * 親子 span（ネスト構造）を作成するデモ
 * Cloud Trace 上でウォーターフォール表示される
 */
telemetry.get('/nested', async (c) => {
  const parentSpan = tracer.startSpan('telemetry.nested.parent', {
    kind: SpanKind.SERVER,
    attributes: {
      'operation.name': 'nested-demo',
      'operation.level': 'parent',
    },
  });

  return await context.with(trace.setSpan(context.active(), parentSpan), async () => {
    try {
      loggingService.logInfoWithContext(c, 'telemetry.nested: parent span started');
      parentSpan.addEvent('parent.started');

      // 子 span 1: データ取得
      const child1 = tracer.startSpan('telemetry.nested.fetch', {
        kind: SpanKind.INTERNAL,
        attributes: { 'operation.level': 'child', 'db.operation': 'SELECT' },
      });
      await context.with(trace.setSpan(context.active(), child1), async () => {
        loggingService.logInfoWithContext(c, 'telemetry.nested.fetch: started');
        await new Promise((resolve) => setTimeout(resolve, 40));
        child1.setAttribute('db.rows_returned', 100);
        child1.setStatus({ code: SpanStatusCode.OK });
        loggingService.logInfoWithContext(c, 'telemetry.nested.fetch: completed', {
          rowsReturned: 100,
        });
        child1.end();
      });

      // 子 span 2: データ変換
      const child2 = tracer.startSpan('telemetry.nested.transform', {
        kind: SpanKind.INTERNAL,
        attributes: { 'operation.level': 'child', 'transform.input_rows': 100 },
      });
      await context.with(trace.setSpan(context.active(), child2), async () => {
        loggingService.logInfoWithContext(c, 'telemetry.nested.transform: started');
        await new Promise((resolve) => setTimeout(resolve, 60));
        child2.setAttribute('transform.output_rows', 95);
        child2.setStatus({ code: SpanStatusCode.OK });
        loggingService.logInfoWithContext(c, 'telemetry.nested.transform: completed', {
          outputRows: 95,
        });
        child2.end();
      });

      // 子 span 3: レスポンス構築
      const child3 = tracer.startSpan('telemetry.nested.serialize', {
        kind: SpanKind.INTERNAL,
        attributes: { 'operation.level': 'child', 'serialize.format': 'json' },
      });
      await context.with(trace.setSpan(context.active(), child3), async () => {
        loggingService.logInfoWithContext(c, 'telemetry.nested.serialize: started');
        await new Promise((resolve) => setTimeout(resolve, 20));
        child3.setStatus({ code: SpanStatusCode.OK });
        loggingService.logInfoWithContext(c, 'telemetry.nested.serialize: completed');
        child3.end();
      });

      parentSpan.setAttribute('operation.children', 3);
      parentSpan.addEvent('parent.completed');
      parentSpan.setStatus({ code: SpanStatusCode.OK });
      loggingService.logInfoWithContext(c, 'telemetry.nested: all child spans completed');

      return c.json({
        success: true,
        message: 'Nested spans (1 parent + 3 children) sent to Google Cloud Telemetry API',
        traceId: parentSpan.spanContext().traceId,
        parentSpanId: parentSpan.spanContext().spanId,
        spans: [
          { name: 'telemetry.nested.parent', role: 'parent' },
          { name: 'telemetry.nested.fetch', role: 'child-1' },
          { name: 'telemetry.nested.transform', role: 'child-2' },
          { name: 'telemetry.nested.serialize', role: 'child-3' },
        ],
        note: 'Check Cloud Trace to see the waterfall view of nested spans',
      });
    } catch (error) {
      parentSpan.recordException(error as Error);
      parentSpan.setStatus({ code: SpanStatusCode.ERROR, message: (error as Error).message });
      return c.json({ success: false, error: (error as Error).message }, 500);
    } finally {
      parentSpan.end();
    }
  });
});


/**
 * GET /telemetry/error
 * エラー情報を span に記録するデモ
 * Cloud Trace 上でエラースパンとして表示される
 */
telemetry.get('/error', async (c) => {
  const span = tracer.startSpan('telemetry.error.demo', {
    kind: SpanKind.SERVER,
    attributes: { 'demo.type': 'error-recording' },
  });

  return await context.with(trace.setSpan(context.active(), span), async () => {
    try {
      loggingService.logInfoWithContext(c, 'telemetry.error: operation started');
      span.addEvent('operation.started');
      await new Promise((resolve) => setTimeout(resolve, 30));

      throw new Error('Simulated error for Telemetry API demo');
    } catch (error) {
      span.recordException(error as Error);
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: (error as Error).message,
      });

      // エラーログも同じ traceId で Cloud Logging に出力される
      loggingService.logErrorWithContext(c, 'telemetry.error: operation failed', error);

      return c.json(
        {
          success: false,
          message: 'Error was recorded in the span and sent to Google Cloud Telemetry API',
          traceId: span.spanContext().traceId,
          spanId: span.spanContext().spanId,
          error: (error as Error).message,
          note: 'Check Cloud Trace to see the error span with exception details',
        },
        500,
      );
    } finally {
      span.end();
    }
  });
});

/**
 * GET /telemetry/info
 * 利用可能なエンドポイント一覧
 */
telemetry.get('/info', (c) => {
  return c.json({
    description: 'Google Cloud Telemetry API (OTLP) demo endpoints',
    exportConfig: {
      endpoint: 'https://telemetry.googleapis.com/v1/traces',
      protocol: 'OTLP/HTTP (protobuf)',
      authentication: 'Application Default Credentials (ADC)',
      propagators: ['W3C TraceContext (traceparent)', 'Google Cloud Trace (X-Cloud-Trace-Context)'],
    },
    endpoints: [
      {
        path: 'GET /telemetry/basic',
        description: '単一 span を作成し Telemetry API へ送信する基本デモ',
      },
      {
        path: 'GET /telemetry/attributes',
        description: 'span に属性・イベントを付与するデモ',
        features: ['Semantic Conventions 属性', 'span.addEvent()', 'span.setAttribute()'],
      },
      {
        path: 'GET /telemetry/nested',
        description: '親子構造のネスト span デモ（Cloud Trace でウォーターフォール表示）',
        features: ['1 parent + 3 children', 'context.with() によるコンテキスト伝播'],
      },
      {
        path: 'GET /telemetry/error',
        description: 'エラーを span に記録するデモ（span.recordException）',
      },
    ],
  });
});

export default telemetry;
