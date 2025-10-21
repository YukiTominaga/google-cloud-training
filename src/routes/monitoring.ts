import { Hono } from 'hono';
import { MonitoringService } from '../services/monitoring.service.js';
import type { CustomMetricRequest, CustomMetricResponse } from '../types/monitoring.js';

const monitoring = new Hono();

// MonitoringServiceのインスタンスを作成
const monitoringService = new MonitoringService();

// Google Cloud Monitoring設定状態を確認するエンドポイント
monitoring.get('/custom-metrics/config', (c) => {
  const configStatus = monitoringService.getConfigStatus();

  return c.json({
    ...configStatus,
    timestamp: new Date().toISOString(),
    message: configStatus.isValid
      ? 'Google Cloud Monitoring is properly configured'
      : 'Configuration issues detected',
  });
});

// Google Cloud Monitoringにカスタム指標を送信するエンドポイント
// curl -X POST http://localhost:3000/monitoring/custom-metrics -H "Content-Type: application/json" -d '{"metricType": "application/test", "value": 42, "labels": {"environment": "training"}}'
// autoCreateDescriptor=trueを指定すると、メトリックディスクリプタを自動作成します
// curl -X POST 'http://localhost:3000/monitoring/custom-metrics?autoCreate=true' -H "Content-Type: application/json" -d '{"metricType": "application/test", "value": 42, "labels": {"environment": "training"}}'
monitoring.post('/custom-metrics', async (c) => {
  try {
    const body = (await c.req.json()) as any;

    // 基本的なバリデーション
    if (!body.metricType || typeof body.value !== 'number') {
      return c.json(
        {
          success: false,
          message: 'metricType and value are required',
          hint: 'Example: {"metricType": "application/test", "value": 42, "labels": {"environment": "dev"}}',
        },
        400,
      );
    }

    // labelsの検証と修正
    let labels = body.labels;
    if (!labels) {
      // labelsフィールドがない場合、トップレベルのプロパティから推測
      labels = {};
      const knownFields = ['metricType', 'value', 'description'];
      for (const [key, value] of Object.entries(body)) {
        if (!knownFields.includes(key) && typeof value === 'string') {
          labels[key] = value;
        }
      }
    }

    const metricRequest: CustomMetricRequest = {
      metricType: body.metricType,
      value: body.value,
      labels: labels,
      description: body.description,
    };

    // autoCreateパラメータのチェック
    const autoCreate = c.req.query('autoCreate') === 'true';

    // カスタム指標を送信
    await monitoringService.sendCustomMetric(metricRequest, autoCreate);

    const configStatus = monitoringService.getConfigStatus();
    const response: CustomMetricResponse = {
      success: true,
      metricType: metricRequest.metricType,
      timestamp: new Date().toISOString(),
      message: 'Custom metric sent successfully',
    };

    return c.json({
      ...response,
      metricFullPath: `custom.googleapis.com/${metricRequest.metricType}`,
      projectId: configStatus.projectId,
      labels: metricRequest.labels,
      hint: 'Check Cloud Monitoring Console in 2-3 minutes for the metric data',
    });
  } catch (error: any) {
    console.error('Error sending custom metric:', error);
    return c.json(
      {
        success: false,
        message: 'Failed to send custom metric',
        error: error instanceof Error ? error.message : 'Unknown error',
        details: error?.details || (error instanceof Error ? error.stack : undefined),
        hint: 'Try adding ?autoCreate=true to automatically create the metric descriptor',
      },
      500,
    );
  }
});

// サンプル指標を一括送信するエンドポイント
monitoring.post('/custom-metrics/sample', async (c) => {
  try {
    const results = await monitoringService.sendSampleMetrics();
    const configStatus = monitoringService.getConfigStatus();

    return c.json({
      success: true,
      message: 'Sample metrics sent successfully',
      metrics: results,
      projectId: configStatus.projectId,
      timestamp: new Date().toISOString(),
      hint: 'Check Cloud Monitoring Console in 2-3 minutes for the metric data',
    });
  } catch (error) {
    console.error('Error sending sample metrics:', error);
    return c.json(
      {
        success: false,
        message: 'Failed to send sample metrics',
        error: error instanceof Error ? error.message : 'Unknown error',
        details: error instanceof Error ? error.stack : undefined,
      },
      500,
    );
  }
});

// テスト用の単一メトリック送信エンドポイント
// デフォルトでautoCreate=trueで実行
monitoring.post('/custom-metrics/test', async (c) => {
  try {
    const testMetric = {
      metricType: 'application/test_metric',
      value: Math.random() * 100,
      labels: {
        environment: process.env.NODE_ENV || 'development',
        test: 'true',
      },
    };

    // テストエンドポイントではデフォルトで自動作成を有効化
    await monitoringService.sendCustomMetric(testMetric, true);
    const configStatus = monitoringService.getConfigStatus();

    return c.json({
      success: true,
      message: 'Test metric sent successfully',
      metric: testMetric,
      projectId: configStatus.projectId,
      metricFullPath: `custom.googleapis.com/${testMetric.metricType}`,
      timestamp: new Date().toISOString(),
      hint: 'Check Cloud Monitoring Console in 2-3 minutes for the metric data',
      consoleUrl: `https://console.cloud.google.com/monitoring/metrics-explorer?project=${configStatus.projectId}`,
    });
  } catch (error: any) {
    console.error('Error sending test metric:', error);
    return c.json(
      {
        success: false,
        message: 'Failed to send test metric',
        error: error instanceof Error ? error.message : 'Unknown error',
        details: error?.details || (error instanceof Error ? error.stack : undefined),
      },
      500,
    );
  }
});

// 利用可能な指標タイプを取得するエンドポイント
monitoring.get('/custom-metrics/types', (c) => {
  const availableMetrics = [
    {
      type: 'application/request_count',
      description: 'アプリケーションへのリクエスト数',
      valueType: 'DOUBLE',
      example: { metricType: 'application/request_count', value: 42 },
    },
    {
      type: 'application/response_time',
      description: 'アプリケーションのレスポンス時間（ミリ秒）',
      valueType: 'DOUBLE',
      example: { metricType: 'application/response_time', value: 250.5 },
    },
    {
      type: 'application/memory_usage',
      description: 'アプリケーションのメモリ使用量（MB）',
      valueType: 'DOUBLE',
      example: { metricType: 'application/memory_usage', value: 128.7 },
    },
    {
      type: 'business/user_activity',
      description: 'ユーザーアクティビティ数',
      valueType: 'DOUBLE',
      example: {
        metricType: 'business/user_activity',
        value: 15,
        labels: { region: 'asia-northeast1' },
      },
    },
  ];

  return c.json({
    availableMetrics,
    usage: {
      configEndpoint: 'GET /monitoring/custom-metrics/config',
      testEndpoint: 'POST /monitoring/custom-metrics/test',
      endpoint: 'POST /monitoring/custom-metrics',
      sampleEndpoint: 'POST /monitoring/custom-metrics/sample',
      requiredFields: ['metricType', 'value'],
      optionalFields: ['labels', 'description'],
    },
    examples: {
      testMetric: {
        url: 'POST /monitoring/custom-metrics/test',
        description: 'Send a test metric to verify the setup (auto-creates descriptor)',
      },
      singleMetric: {
        url: 'POST /monitoring/custom-metrics',
        body: {
          metricType: 'application/request_count',
          value: 42,
          labels: { environment: 'production', region: 'asia-northeast1' },
        },
      },
      singleMetricAutoCreate: {
        url: 'POST /monitoring/custom-metrics?autoCreate=true',
        description: 'Automatically create metric descriptor if it does not exist',
        body: {
          metricType: 'application/new_metric',
          value: 100,
          labels: { environment: 'development' },
        },
      },
      sampleMetrics: {
        url: 'POST /monitoring/custom-metrics/sample',
        description: 'Send predefined sample metrics (request_count, response_time, memory_usage)',
      },
    },
    notes: {
      labels:
        'Labels must be nested under "labels" field, or will be auto-detected from top-level string fields',
      autoCreate: 'Add ?autoCreate=true query parameter to automatically create metric descriptors',
      errorHandling: 'Detailed error information is returned in the response',
    },
  });
});

export default monitoring;
