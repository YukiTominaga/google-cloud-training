import { metrics } from '@opentelemetry/api';
import type { Gauge } from '@opentelemetry/api';
import { config, validateConfig } from '../config/config.js';
import type { CustomMetricRequest } from '../types/monitoring.js';

export class MonitoringService {
  private meter = metrics.getMeter('monitoring-service');
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
      gauge = this.meter.createGauge(metricType, {
        description: description || `Custom metric: ${metricType}`,
      });
      this.gauges.set(metricType, gauge);
    }
    return gauge;
  }

  /**
   * カスタム指標を記録
   * gauge.record() は同期・即時実行で、実際のネットワーク送信は
   * NodeSDK 側の PeriodicExportingMetricReader がバックグラウンドで定期的に行う
   * @param metric - 記録するメトリックデータ
   */
  sendCustomMetric(metric: CustomMetricRequest): void {
    this.checkConfig();
    this.validateMetric(metric);

    const gauge = this.getGauge(metric.metricType, metric.description);
    gauge.record(metric.value, metric.labels ?? {});

    if (config.enableDebugLogging) {
      console.log('[Monitoring] Recording metric:', JSON.stringify(metric, null, 2));
    }

    console.log(`✓ Metric recorded: ${metric.metricType} = ${metric.value}`);
  }

  /**
   * サンプル指標を送信するヘルパーメソッド
   */
  sendSampleMetrics(): Array<{ metricType: string; value: number }> {
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
      this.sendCustomMetric({
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

    return results;
  }

  /**
   * ランダム値(1〜100)を一定間隔で指定時間だけ継続的に書き込む
   * デモ用: 1リクエストだけで時系列データを生成できる
   *
   * 即座に初回の書き込みを行い、ジョブ情報を返す（以降は setInterval で継続書き込み）
   *
   * @param options.metricType - メトリックタイプ（デフォルト: application/demo_random）
   * @param options.durationMinutes - 書き込みを継続する時間（分、デフォルト: 5）
   * @param options.intervalSeconds - 書き込み間隔（秒、デフォルト: 10）
   * @param options.labels - メトリックに付与するラベル
   */
  startContinuousRandomMetrics(options: {
    metricType?: string;
    durationMinutes?: number;
    intervalSeconds?: number;
    labels?: Record<string, string>;
  } = {}): {
    metricType: string;
    durationMinutes: number;
    intervalSeconds: number;
    totalWrites: number;
    labels: Record<string, string>;
  } {
    this.checkConfig();

    const metricType = options.metricType || 'application/demo_random';
    const durationMinutes = options.durationMinutes ?? 5;
    const intervalSeconds = options.intervalSeconds ?? 10;
    const labels = options.labels || {
      environment: process.env.NODE_ENV || 'development',
      instance: 'hono-server',
    };

    const intervalMs = intervalSeconds * 1000;
    const durationMs = durationMinutes * 60 * 1000;
    const totalWrites = Math.floor(durationMs / intervalMs);

    // ランダム値(1〜100)を生成して書き込むヘルパー
    const writeOne = () => {
      const value = Math.floor(Math.random() * 100) + 1; // 1〜100
      try {
        this.sendCustomMetric({ metricType, value, labels });
      } catch (error) {
        console.error('[Monitoring] Continuous metric write failed:', {
          metricType,
          value,
          error: error instanceof Error ? error.message : error,
        });
      }
    };

    // 初回の書き込み
    try {
      this.sendCustomMetric({ metricType, value: Math.floor(Math.random() * 100) + 1, labels });
    } catch (error) {
      console.error('[Monitoring] Initial continuous metric write failed:', error);
    }

    // 継続書き込みを開始
    const startedAt = Date.now();
    const timer = setInterval(() => {
      // 経過時間が指定時間を超えたら停止
      if (Date.now() - startedAt >= durationMs) {
        clearInterval(timer);
        console.log(
          `✓ Continuous metric writing finished: ${metricType} (${durationMinutes} min)`,
        );
        return;
      }
      writeOne();
    }, intervalMs);

    console.log(
      `▶ Started continuous metric writing: ${metricType} every ${intervalSeconds}s for ${durationMinutes} min (~${totalWrites + 1} points)`,
    );

    return {
      metricType,
      durationMinutes,
      intervalSeconds,
      totalWrites: totalWrites + 1, // 初回書き込みを含む
      labels,
    };
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
