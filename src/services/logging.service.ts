import { type Span, SpanStatusCode, trace } from '@opentelemetry/api';
import { logs, SeverityNumber } from '@opentelemetry/api-logs';
import { randomUUID } from 'crypto';
import type { LogStructureRequest } from '../types/logging.js';

type Severity = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';

const SEVERITY_NUMBER_MAP: Record<Severity, SeverityNumber> = {
  DEBUG: SeverityNumber.DEBUG,
  INFO: SeverityNumber.INFO,
  WARNING: SeverityNumber.WARN,
  ERROR: SeverityNumber.ERROR,
};

export class LoggingService {
  private tracer = trace.getTracer('logging-service');
  private logger = logs.getLogger('logging-service');

  constructor() {}

  /**
   * OpenTelemetry LogRecordとして出力する共通ヘルパー
   * trace_id/span_id/severityはアクティブなspanのコンテキストから自動的に付与される
   */
  private emit(severity: Severity, payload: Record<string, unknown>): string {
    const logId = randomUUID();

    this.logger.emit({
      severityNumber: SEVERITY_NUMBER_MAP[severity],
      severityText: severity,
      body: {
        logId,
        ...payload,
      },
    });

    return logId;
  }

  /**
   * 構造化ログとして出力
   */
  logStructuredData(data: LogStructureRequest): string {
    return this.emit('INFO', { message: 'Request body logged', ...data });
  }

  logInfo(message: string, data?: Record<string, unknown>): string {
    return this.emit('INFO', { message, ...(data !== undefined ? { data } : {}) });
  }

  logWarn(message: string, data?: Record<string, unknown>): string {
    return this.emit('WARNING', { message, ...(data !== undefined ? { data } : {}) });
  }

  logDebug(message: string, data?: Record<string, unknown>): string {
    return this.emit('DEBUG', { message, ...(data !== undefined ? { data } : {}) });
  }

  logError(message: string, error?: unknown): string {
    // Google Cloud Error Reporting自動検出用のjsonPayload
    const payload: Record<string, unknown> = {
      '@type': 'type.googleapis.com/google.devtools.clouderrorreporting.v1beta1.ReportedErrorEvent',
      message,
    };

    // エラーオブジェクトがある場合はスタックトレースを追加
    if (error instanceof Error && error.stack) {
      payload.message = `${message}: ${error.message}`;
      payload.stack_trace = error.stack;
    }

    return this.emit('ERROR', payload);
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
