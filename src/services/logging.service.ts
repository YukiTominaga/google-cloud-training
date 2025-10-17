import { randomUUID } from 'crypto';
import { config } from '../config/config.js';
import type { LogEntry, LogStructureRequest } from '../types/logging.js';

export class LoggingService {
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
   * 構造化ログとして出力（trace情報付き）
   */
  logStructuredData(data: LogStructureRequest, traceparent?: string): string {
    const logId = randomUUID();
    const traceId = this.extractTraceId(traceparent);

    const structuredLog: any = {
      message: 'Request body logged',
      severity: 'INFO',
      ...data,
    };

    // Google Cloud Loggingのtrace形式でtraceIdを追加
    if (traceId) {
      structuredLog['logging.googleapis.com/trace'] =
        `projects/${config.projectId}/traces/${traceId}`;
    }

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
    const traceId = this.extractTraceId(traceparent);

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

    // traceIdがある場合は追加
    if (traceId) {
      errorLog['logging.googleapis.com/trace'] = `projects/${config.projectId}/traces/${traceId}`;
    }

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

    const logEntry: LogEntry = {
      logId,
      timestamp,
      level,
      message,
      data: data || null,
    };

    // jsonPayloadとして認識されるように1行で出力
    console.log(JSON.stringify(logEntry));
    return logId;
  }
}
