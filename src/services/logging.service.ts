import { type Span, SpanStatusCode, trace } from '@opentelemetry/api';
import { randomUUID } from 'crypto';
import { config } from '../config/config.js';
import type { LogEntry, LogStructureRequest } from '../types/logging.js';

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
  private addTraceContext(logEntry: any, traceparent?: string): void {
    // まずOpenTelemetryのアクティブなspanから取得を試みる
    const { traceId, spanId } = this.getCurrentTraceInfo();

    if (traceId) {
      // Google Cloud Logging形式でtraceIdを追加
      logEntry['logging.googleapis.com/trace'] = `projects/${config.projectId}/traces/${traceId}`;

      if (spanId) {
        // spanIdも追加（Cloud LoggingとCloud Traceの連携に使用）
        logEntry['logging.googleapis.com/spanId'] = spanId;
      }
    } else if (traceparent) {
      // フォールバック: traceparentヘッダーから抽出
      const extractedTraceId = this.extractTraceId(traceparent);
      if (extractedTraceId) {
        logEntry['logging.googleapis.com/trace'] =
          `projects/${config.projectId}/traces/${extractedTraceId}`;
      }
    }
  }

  /**
   * 構造化ログとして出力（trace情報付き）
   */
  logStructuredData(data: LogStructureRequest, traceparent?: string): string {
    const logId = randomUUID();

    const structuredLog: any = {
      message: 'Request body logged',
      severity: 'INFO',
      ...data,
    };

    // OpenTelemetry spanからtrace情報を追加
    this.addTraceContext(structuredLog, traceparent);

    // 構造化ログを出力（jsonPayloadとして認識されるように1行で出力）
    console.log(JSON.stringify(structuredLog));

    return logId;
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
   */
  logInfo(message: string, data?: any): string {
    return this.createLogEntry('INFO', message, data);
  }

  logWarn(message: string, data?: any): string {
    return this.createLogEntry('WARN', message, data);
  }

  logError(message: string, error?: Error | any, traceparent?: string): string {
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

    // OpenTelemetry spanからtrace情報を追加
    this.addTraceContext(errorLog, traceparent);

    // jsonPayloadとして認識されるように1行で出力
    console.log(JSON.stringify(errorLog));
    return logId;
  }

  logDebug(message: string, data?: any): string {
    return this.createLogEntry('DEBUG', message, data);
  }

  /**
   * ログエントリを作成
   */
  private createLogEntry(level: LogEntry['level'], message: string, data?: any): string {
    const logId = randomUUID();
    const timestamp = new Date().toISOString();

    const logEntry: any = {
      logId,
      timestamp,
      level,
      message,
      data: data || null,
    };

    // OpenTelemetry spanからtrace情報を追加
    this.addTraceContext(logEntry);

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
