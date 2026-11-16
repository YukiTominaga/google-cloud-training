import { metrics } from '@opentelemetry/api';
import type { Gauge } from '@opentelemetry/api';
import { config, validateConfig } from '../config/config.js';
import { flushMetrics } from '../config/otel.js';
import type { CustomMetricRequest } from '../types/monitoring.js';
import { LoggingService } from './logging.service.js';

export class MonitoringService {
  private loggingService = new LoggingService();
  private gauges = new Map<string, Gauge>();
  private projectId: string;
  private isConfigValid: boolean;

  constructor() {
    const configValidation = validateConfig();
    this.isConfigValid = configValidation.isValid;

    if (!this.isConfigValid) {
      console.warn('Google Cloud Monitoring configuration errors:', configValidation.errors);
    }

    this.projectId = config.projectId;
  }

  /**
   * 設定が有効かどうかをチェック
   */
  private checkConfig(): void {
    if (!this.isConfigValid) {
      throw new Error(
        'Google Cloud Monitoring is not properly configured. Check GOOGLE_CLOUD_PROJECT environment variable and ensure ADC is set up.',
      );
    }
  }

  /**
   * メトリックのバリデーション
   */
  private validateMetric(metric: CustomMetricRequest): void {
    if (!metric.metricType) {
      throw new Error('metricType is required');
    }
    if (typeof metric.value !== 'number' || isNaN(metric.value)) {
      throw new Error('value must be a valid number');
    }
  }

  /**
   * metricType に対応する Gauge instrument を取得（なければ作成してキャッシュ）
   */
  private getGauge(metricType: string, description?: string): Gauge {
    let gauge = this.gauges.get(metricType);
    if (!gauge) {
      // Meter はここで取得する。ESM の import は index.ts の startOpenTelemetry() より先に評価されるため、
      // コンストラクタ時点で取得すると MeterProvider 未登録の NOOP Meter になり、記録が捨てられる
      // （metrics API には trace API の ProxyTracerProvider に相当する遅延差し替えの仕組みがない）
      gauge = metrics.getMeter('monitoring-service').createGauge(metricType, {
        description: description || `Custom metric: ${metricType}`,
      });
      this.gauges.set(metricType, gauge);
    }
    return gauge;
  }

  /**
   * カスタム指標を Gauge に記録する（送信はしない）
   */
  private recordMetric(metric: CustomMetricRequest): void {
    this.checkConfig();
    this.validateMetric(metric);

    const gauge = this.getGauge(metric.metricType, metric.description);
    gauge.record(metric.value, metric.labels ?? {});

    if (config.enableDebugLogging) {
      this.loggingService.logDebug('[Monitoring] Recording metric', { ...metric });
    }

    console.log(`✓ Metric recorded: ${metric.metricType} = ${metric.value}`);
  }

  /**
   * カスタム指標を記録し、Telemetry API への送信完了まで待つ
   * Cloud Run のリクエストベース課金ではレスポンス後に CPU が絞られるため、
   * 定期送信に任せずレスポンスを返す前に送り切る
   * @param metric - 記録するメトリックデータ
   */
  async sendCustomMetric(metric: CustomMetricRequest): Promise<void> {
    this.recordMetric(metric);
    await flushMetrics();
  }

  /**
   * サンプル指標を送信するヘルパーメソッド
   */
  async sendSampleMetrics(): Promise<Array<{ metricType: string; value: number }>> {
    const sampleMetrics = [
      {
        metricType: 'application/request_count',
        value: Math.floor(Math.random() * 100) + 1,
        description: 'アプリケーションへのリクエスト数',
      },
      {
        metricType: 'application/response_time',
        value: Math.random() * 1000,
        description: 'アプリケーションのレスポンス時間（ミリ秒）',
      },
      {
        metricType: 'application/memory_usage',
        value: process.memoryUsage().heapUsed / 1024 / 1024, // MB
        description: 'アプリケーションのメモリ使用量（MB）',
      },
    ];

    // 指標を記録
    const results = [];
    for (const metric of sampleMetrics) {
      this.recordMetric({
        metricType: metric.metricType,
        value: metric.value,
        description: metric.description,
        labels: {
          environment: process.env.NODE_ENV || 'development',
          instance: 'hono-server',
        },
      });
      results.push({
        metricType: metric.metricType,
        value: metric.value,
      });
    }

    await flushMetrics();

    return results;
  }

  /**
   * 設定状態を取得
   */
  getConfigStatus() {
    const validation = validateConfig();
    return {
      isValid: this.isConfigValid,
      projectId: this.projectId,
      enableDebugLogging: config.enableDebugLogging,
      authMethod: 'Application Default Credentials (ADC) via OpenTelemetry OTLP Exporter',
      exportPath: 'OpenTelemetry Metrics SDK -> Google Cloud Telemetry API (OTLP)',
      errors: validation.errors,
    };
  }
}
