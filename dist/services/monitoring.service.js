import { MetricServiceClient } from '@google-cloud/monitoring';
import { config, validateConfig } from '../config/config.js';
export class MonitoringService {
  client;
  projectId;
  isConfigValid;
  constructor() {
    const configValidation = validateConfig();
    this.isConfigValid = configValidation.isValid;
    if (!this.isConfigValid && !config.enableLocalTesting) {
      console.warn('Google Cloud Monitoring configuration errors:', configValidation.errors);
    }
    // Application Default Credentials を使用
    // gcloud auth application-default login を実行するか、
    // GCE/GKE環境でサービスアカウントが自動設定される
    this.client = new MetricServiceClient();
    this.projectId = config.projectId;
  }
  /**
   * 設定が有効かどうかをチェック
   */
  checkConfig() {
    if (!this.isConfigValid && !config.enableLocalTesting) {
      throw new Error(
        'Google Cloud Monitoring is not properly configured. Check GOOGLE_CLOUD_PROJECT environment variable and ensure ADC is set up.',
      );
    }
  }
  /**
   * カスタム指標の定義を作成
   */
  async createMetricDescriptor(descriptor) {
    this.checkConfig();
    if (config.enableLocalTesting) {
      console.log(`[LOCAL TEST] Would create metric descriptor: ${descriptor.type}`);
      return;
    }
    const projectName = this.client.projectPath(this.projectId);
    const request = {
      name: projectName,
      metricDescriptor: {
        type: `custom.googleapis.com/${descriptor.type}`,
        metricKind: descriptor.metricKind,
        valueType: descriptor.valueType,
        description: descriptor.description,
        displayName: descriptor.displayName,
        labels: descriptor.labels || [],
      },
    };
    try {
      const [result] = await this.client.createMetricDescriptor(request);
      console.log(`Created metric descriptor: ${result.name}`);
    } catch (error) {
      // 既に存在する場合はエラーをログに出力するが処理は継続
      if (error instanceof Error && error.message.includes('already exists')) {
        console.log(`Metric descriptor already exists: ${descriptor.type}`);
      } else {
        throw error;
      }
    }
  }
  /**
   * カスタム指標を送信
   */
  async sendCustomMetric(metric) {
    this.checkConfig();
    if (config.enableLocalTesting) {
      console.log(`[LOCAL TEST] Would send metric:`, {
        type: metric.metricType,
        value: metric.value,
        labels: metric.labels,
        timestamp: new Date().toISOString(),
      });
      return;
    }
    const projectName = this.client.projectPath(this.projectId);
    // タイムスタンプを作成
    const now = new Date();
    const seconds = Math.floor(now.getTime() / 1000);
    const nanos = (now.getTime() % 1000) * 1000000;
    const timeInterval = {
      endTime: {
        seconds: seconds,
        nanos: nanos,
      },
    };
    const request = {
      name: projectName,
      timeSeries: [
        {
          metric: {
            type: `custom.googleapis.com/${metric.metricType}`,
            labels: metric.labels || {},
          },
          resource: {
            type: 'global',
            labels: {
              project_id: this.projectId,
            },
          },
          points: [
            {
              interval: timeInterval,
              value: {
                doubleValue: metric.value,
              },
            },
          ],
        },
      ],
    };
    await this.client.createTimeSeries(request);
  }
  /**
   * サンプル指標を送信するヘルパーメソッド
   */
  async sendSampleMetrics() {
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
    // 指標定義を作成（初回のみ）
    for (const metric of sampleMetrics) {
      await this.createMetricDescriptor({
        type: metric.metricType,
        metricKind: 'GAUGE',
        valueType: 'DOUBLE',
        description: metric.description,
        displayName: metric.metricType.replace('application/', '').replace('_', ' '),
      });
    }
    // 指標を送信
    const results = [];
    for (const metric of sampleMetrics) {
      await this.sendCustomMetric({
        metricType: metric.metricType,
        value: metric.value,
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
   * 設定状態を取得
   */
  getConfigStatus() {
    const validation = validateConfig();
    return {
      isValid: this.isConfigValid,
      projectId: this.projectId,
      enableLocalTesting: config.enableLocalTesting,
      authMethod: 'Application Default Credentials (ADC)',
      errors: validation.errors,
    };
  }
}
