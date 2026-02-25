import { type Span, SpanStatusCode, trace } from '@opentelemetry/api';
import { randomUUID } from 'crypto';
import { config } from '../config/config.js';
import type { LogEntry, LogStructureRequest } from '../types/logging.js';
import type { Context } from 'hono';

export class LoggingService {
  private tracer = trace.getTracer('logging-service');

  constructor() {
    console.log('LoggingService initialized');
  }

  /**
   * w3c traceparentヘッダーからtraceIdを抽出
   */
  private extractTraceId(traceparent?: string): string | null {
    if (!traceparent) return null;

    // w3c traceparent format: 00-{trace-id}-{parent-id}-{trace-flags}
    const parts = traceparent.split('-');
    if (parts.length === 4 && parts[0] === '00') {
      return parts[1];
    }

    return null;
  }

  /**
   * X-Cloud-Trace-ContextヘッダーからtraceIdを抽出
   * 形式の例: TRACE_ID/SPAN_ID;o=TRACE_TRUE
   */
  private extractTraceIdFromXCloudTraceContext(header?: string): string | null {
    if (!header) return null;

    const [traceAndSpan] = header.split(';', 1);
    if (!traceAndSpan) return null;

    const [traceId] = traceAndSpan.split('/', 1);
    if (!traceId) return null;

    // Cloud TraceのtraceIdは通常32桁の16進数
    if (!/^[0-9a-fA-F]{16,32}$/.test(traceId)) {
      return null;
    }

    return traceId;
  }

  /**
   * 現在のアクティブなspanからtrace情報を取得
   */
  private getCurrentTraceInfo(): { traceId: string | null; spanId: string | null } {
    const activeSpan = trace.getActiveSpan();
    if (!activeSpan) {
      return { traceId: null, spanId: null };
    }

    const spanContext = activeSpan.spanContext();
    return {
      traceId: spanContext.traceId,
      spanId: spanContext.spanId,
    };
  }

  /**
   * Cloud Logging形式のtrace/span情報を追加
   */
  private addTraceContext(
    logEntry: any,
    traceparent?: string,
    xCloudTraceContext?: string,
  ): void {
    // spanId は常に現在のアクティブspanから取得しておく
    const current = this.getCurrentTraceInfo();
    let traceId: string | null = null;
    const spanId: string | null = current.spanId;

    // 1. traceparentヘッダーを最優先で使用
    if (traceparent) {
      traceId = this.extractTraceId(traceparent);
    }

    // 2. traceparentが無い／不正な場合は X-Cloud-Trace-Context を使用
    if (!traceId && xCloudTraceContext) {
      traceId = this.extractTraceIdFromXCloudTraceContext(xCloudTraceContext);
    }

    // 3. どちらのヘッダーも無い場合は現在のアクティブなspanを使用
    if (!traceId) {
      traceId = current.traceId;
    }

    if (traceId) {
      // Google Cloud Logging形式でtraceIdを追加
      logEntry['logging.googleapis.com/trace'] = `projects/${config.projectId}/traces/${traceId}`;

      if (spanId) {
        // spanIdも追加（Cloud LoggingとCloud Traceの連携に使用）
        logEntry['logging.googleapis.com/spanId'] = spanId;
      }
    }
  }

  /**
   * 構造化ログとして出力（trace情報付き）
   */
  logStructuredData(
    data: LogStructureRequest,
    traceparent?: string,
    xCloudTraceContext?: string,
  ): string {
    const logId = randomUUID();

    const structuredLog: any = {
      message: 'Request body logged',
      severity: 'INFO',
      ...data,
    };

    // OpenTelemetry spanからtrace情報を追加
    this.addTraceContext(structuredLog, traceparent, xCloudTraceContext);

    // 構造化ログを出力（jsonPayloadとして認識されるように1行で出力）
    console.log(JSON.stringify(structuredLog));

    return logId;
  }

  /**
   * HonoのContextからヘッダーを解決
   * （将来ミドルウェアで c.set(...) した場合も考慮）
   */
  private resolveTraceHeadersFromContext(
    c: Context,
  ): { traceparent?: string; xCloudTraceContext?: string } {
    const traceparent =
      (c.get?.('traceparent') as string | undefined) ??
      c.req.header('traceparent') ??
      undefined;
    const xCloudTraceContext =
      (c.get?.('xCloudTraceContext') as string | undefined) ??
      c.req.header('x-cloud-trace-context') ??
      undefined;

    return { traceparent, xCloudTraceContext };
  }

  /**
   * Google Cloud Loggingに送信（将来的な拡張用）
   * 現在はコンソール出力のみ
   */
  private sendToCloudLogging(logEntry: LogEntry): void {
    // TODO: Google Cloud Logging Clientを使用した実装
    // 現在は開発用としてコンソール出力のみ
    console.log(`[CLOUD_LOGGING_PLACEHOLDER] Log entry created with ID: ${logEntry.logId}`);
  }

  /**
   * ログレベル別の出力メソッド
   * HTTPコンテキストがある場合はtraceparent/x-cloud-trace-contextを渡すことで、
   * ヘッダーを優先してtraceIdを決定する。
   */
  logInfo(
    message: string,
    data?: any,
    traceparent?: string,
    xCloudTraceContext?: string,
  ): string {
    return this.createLogEntry('INFO', message, data, traceparent, xCloudTraceContext);
  }

  logWarn(
    message: string,
    data?: any,
    traceparent?: string,
    xCloudTraceContext?: string,
  ): string {
    return this.createLogEntry('WARN', message, data, traceparent, xCloudTraceContext);
  }

  logError(
    message: string,
    error?: Error | any,
    traceparent?: string,
    xCloudTraceContext?: string,
  ): string {
    const logId = randomUUID();

    // Google Cloud Error Reporting形式のjsonPayload
    const errorLog: any = {
      '@type': 'type.googleapis.com/google.devtools.clouderrorreporting.v1beta1.ReportedErrorEvent',
      message: message,
      severity: 'ERROR',
    };

    // エラーオブジェクトがある場合はスタックトレースを追加
    if (error && error instanceof Error && error.stack) {
      errorLog.message = `${message}: ${error.message}`;
      errorLog.stack_trace = error.stack;
    }

    // OpenTelemetry spanまたはHTTPヘッダーからtrace情報を追加
    this.addTraceContext(errorLog, traceparent, xCloudTraceContext);

    // jsonPayloadとして認識されるように1行で出力
    console.log(JSON.stringify(errorLog));
    return logId;
  }

  logDebug(
    message: string,
    data?: any,
    traceparent?: string,
    xCloudTraceContext?: string,
  ): string {
    return this.createLogEntry('DEBUG', message, data, traceparent, xCloudTraceContext);
  }

  /**
   * Hono Context 付きのヘルパー
   * すべてのエンドポイントでヘッダー処理を共通化するためのラッパー
   */
  logStructuredDataWithContext(c: Context, data: LogStructureRequest): string {
    const { traceparent, xCloudTraceContext } = this.resolveTraceHeadersFromContext(c);
    return this.logStructuredData(data, traceparent, xCloudTraceContext);
  }

  logInfoWithContext(c: Context, message: string, data?: any): string {
    const { traceparent, xCloudTraceContext } = this.resolveTraceHeadersFromContext(c);
    return this.logInfo(message, data, traceparent, xCloudTraceContext);
  }

  logWarnWithContext(c: Context, message: string, data?: any): string {
    const { traceparent, xCloudTraceContext } = this.resolveTraceHeadersFromContext(c);
    return this.logWarn(message, data, traceparent, xCloudTraceContext);
  }

  logDebugWithContext(c: Context, message: string, data?: any): string {
    const { traceparent, xCloudTraceContext } = this.resolveTraceHeadersFromContext(c);
    return this.logDebug(message, data, traceparent, xCloudTraceContext);
  }

  logErrorWithContext(c: Context, message: string, error?: Error | any): string {
    const { traceparent, xCloudTraceContext } = this.resolveTraceHeadersFromContext(c);
    return this.logError(message, error, traceparent, xCloudTraceContext);
  }

  /**
   * ログエントリを作成
   */
  private createLogEntry(
    level: LogEntry['level'],
    message: string,
    data?: any,
    traceparent?: string,
    xCloudTraceContext?: string,
  ): string {
    const logId = randomUUID();
    const timestamp = new Date().toISOString();

    const logEntry: any = {
      logId,
      timestamp,
      level,
      message,
      data: data || null,
    };

    // OpenTelemetry spanまたはHTTPヘッダーからtrace情報を追加
    this.addTraceContext(logEntry, traceparent, xCloudTraceContext);

    // jsonPayloadとして認識されるように1行で出力
    console.log(JSON.stringify(logEntry));
    return logId;
  }

  /**
   * カスタムspanでラップして処理を実行
   * span内でのログ出力は自動的にtrace情報が付与される
   */
  async withSpan<T>(spanName: string, fn: (span: Span) => Promise<T>): Promise<T> {
    return await this.tracer.startActiveSpan(spanName, async (span) => {
      try {
        const result = await fn(span);
        span.setStatus({ code: SpanStatusCode.OK });
        return result;
      } catch (error) {
        // エラー情報をspanに記録
        span.setStatus({
          code: SpanStatusCode.ERROR,
          message: error instanceof Error ? error.message : 'Unknown error',
        });

        if (error instanceof Error) {
          span.recordException(error);
        }

        // エラーログを出力（自動的にtrace情報が付与される）
        this.logError(`Error in span: ${spanName}`, error);

        throw error;
      } finally {
        span.end();
      }
    });
  }
}
