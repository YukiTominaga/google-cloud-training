import { MetricServiceClient } from '@google-cloud/monitoring';
import { config, validateConfig } from '../config/config.js';
import type {
  CustomMetricRequest,
  MetricDescriptor,
  MonitoredResource,
} from '../types/monitoring.js';

export class MonitoringService {
  private client: MetricServiceClient;
  private projectId: string;
  private isConfigValid: boolean;

  constructor() {
    const configValidation = validateConfig();
    this.isConfigValid = configValidation.isValid;

    if (!this.isConfigValid) {
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
   * モニタリングリソースを取得
   */
  private getMonitoredResource(): MonitoredResource {
    return {
      type: 'generic_task',
      labels: {
        project_id: this.projectId,
        location: 'global',
        namespace: 'hono-app',
        job: 'custom-metrics',
        task_id: process.env.HOSTNAME || 'local-instance',
      },
    };
  }

  /**
   * カスタム指標の定義を作成
   */
  async createMetricDescriptor(descriptor: MetricDescriptor): Promise<void> {
    this.checkConfig();

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

    if (config.enableDebugLogging) {
      console.log('[Monitoring] Creating metric descriptor:', JSON.stringify(request, null, 2));
    }

    try {
      const [result] = await this.client.createMetricDescriptor(request);
      console.log(`✓ Created metric descriptor: ${result.name}`);
    } catch (error) {
      // 既に存在する場合はエラーをログに出力するが処理は継続
      if (error instanceof Error && error.message.includes('already exists')) {
        console.log(`ℹ Metric descriptor already exists: ${descriptor.type}`);
      } else {
        console.error('[Monitoring Error] Failed to create metric descriptor:', {
          metricType: descriptor.type,
          error: error instanceof Error ? error.message : error,
          stack: error instanceof Error ? error.stack : undefined,
        });
        throw error;
      }
    }
  }

  /**
   * カスタム指標を送信
   * @param metric - 送信するメトリックデータ
   * @param autoCreateDescriptor - メトリックディスクリプタが存在しない場合に自動作成するか（デフォルト: false）
   */
  async sendCustomMetric(
    metric: CustomMetricRequest,
    autoCreateDescriptor: boolean = false,
  ): Promise<void> {
    this.checkConfig();
    this.validateMetric(metric);

    // 自動作成が有効な場合、メトリックディスクリプタを作成を試みる
    if (autoCreateDescriptor) {
      try {
        await this.createMetricDescriptor({
          type: metric.metricType,
          metricKind: 'GAUGE',
          valueType: 'DOUBLE',
          description: metric.description || `Custom metric: ${metric.metricType}`,
          displayName: metric.metricType.split('/').pop() || metric.metricType,
          labels: metric.labels
            ? Object.keys(metric.labels).map((key) => ({
                key,
                valueType: 'STRING' as const,
                description: `Label: ${key}`,
              }))
            : [],
        });
      } catch (error) {
        // エラーは無視（既に存在する場合など）
        if (config.enableDebugLogging) {
          console.log('[Monitoring] Metric descriptor creation skipped:', error);
        }
      }
    }

    const projectName = this.client.projectPath(this.projectId);

    // タイムスタンプを作成
    const now = new Date();
    const seconds = Math.floor(now.getTime() / 1000);
    const nanos = (now.getTime() % 1000) * 1000000;

    // GAUGEメトリックの場合はstartTimeとendTimeを同じにする
    const timeInterval = {
      endTime: {
        seconds: seconds,
        nanos: nanos,
      },
      startTime: {
        seconds: seconds,
        nanos: nanos,
      },
    };

    const monitoredResource = this.getMonitoredResource();

    const request = {
      name: projectName,
      timeSeries: [
        {
          metric: {
            type: `custom.googleapis.com/${metric.metricType}`,
            labels: metric.labels || {},
          },
          resource: monitoredResource,
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

    if (config.enableDebugLogging) {
      console.log('[Monitoring] Sending metric:', JSON.stringify(request, null, 2));
    }

    try {
      await this.client.createTimeSeries(request);
      console.log(`✓ Metric sent successfully: ${metric.metricType} = ${metric.value}`);
    } catch (error: any) {
      // より詳細なエラー情報を抽出
      const errorDetails = {
        metricType: metric.metricType,
        value: metric.value,
        labels: metric.labels,
        message: error instanceof Error ? error.message : String(error),
        code: error?.code,
        details: error?.details,
        metadata: error?.metadata,
      };

      console.error('[Monitoring Error] Failed to send metric:', errorDetails);

      // より分かりやすいエラーメッセージを生成
      let userFriendlyMessage = error instanceof Error ? error.message : String(error);

      if (error?.message?.includes('not exist')) {
        userFriendlyMessage = `Metric descriptor for "${metric.metricType}" does not exist. Create it first using createMetricDescriptor().`;
      } else if (error?.message?.includes('TimeSeries could not be written')) {
        userFriendlyMessage = `Failed to write metric "${metric.metricType}". This may be due to: 1) Missing metric descriptor, 2) Invalid labels, 3) Invalid resource type. Original error: ${error.message}`;
      }

      const enhancedError = new Error(userFriendlyMessage);
      (enhancedError as any).originalError = error;
      (enhancedError as any).details = errorDetails;
      throw enhancedError;
    }
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

    // 指標定義を作成（初回のみ）
    // ラベルを定義に含める
    for (const metric of sampleMetrics) {
      await this.createMetricDescriptor({
        type: metric.metricType,
        metricKind: 'GAUGE',
        valueType: 'DOUBLE',
        description: metric.description,
        displayName: metric.metricType.replace('application/', '').replace(/_/g, ' '),
        labels: [
          {
            key: 'environment',
            valueType: 'STRING',
            description: 'Environment name (development, production, etc.)',
          },
          {
            key: 'instance',
            valueType: 'STRING',
            description: 'Instance identifier',
          },
        ],
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
      enableDebugLogging: config.enableDebugLogging,
      authMethod: 'Application Default Credentials (ADC)',
      monitoredResourceType: 'generic_task',
      errors: validation.errors,
    };
  }
}
