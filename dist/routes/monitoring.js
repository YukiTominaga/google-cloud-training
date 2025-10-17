import { Hono } from 'hono';
import { MonitoringService } from '../services/monitoring.service.js';
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
// curl -X POST http://localhost:3000/monitoring/custom-metrics -H "Content-Type: application/json" -d '{"metricType": "business/test_metric", "value": 123, "labels": {"environment": "test", "region": "local"}}'
monitoring.post('/custom-metrics', async (c) => {
    try {
        const body = (await c.req.json());
        // バリデーション
        if (!body.metricType || typeof body.value !== 'number') {
            return c.json({
                success: false,
                message: 'metricType and value are required',
            }, 400);
        }
        // カスタム指標を送信
        await monitoringService.sendCustomMetric(body);
        const response = {
            success: true,
            metricType: body.metricType,
            timestamp: new Date().toISOString(),
            message: 'Custom metric sent successfully',
        };
        return c.json(response);
    }
    catch (error) {
        console.error('Error sending custom metric:', error);
        return c.json({
            success: false,
            message: 'Failed to send custom metric',
            error: error instanceof Error ? error.message : 'Unknown error',
        }, 500);
    }
});
// サンプル指標を一括送信するエンドポイント
monitoring.post('/custom-metrics/sample', async (c) => {
    try {
        const results = await monitoringService.sendSampleMetrics();
        return c.json({
            success: true,
            message: 'Sample metrics sent successfully',
            metrics: results,
            timestamp: new Date().toISOString(),
        });
    }
    catch (error) {
        console.error('Error sending sample metrics:', error);
        return c.json({
            success: false,
            message: 'Failed to send sample metrics',
            error: error instanceof Error ? error.message : 'Unknown error',
        }, 500);
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
            endpoint: 'POST /monitoring/custom-metrics',
            sampleEndpoint: 'POST /monitoring/custom-metrics/sample',
            requiredFields: ['metricType', 'value'],
            optionalFields: ['labels', 'description'],
        },
        examples: {
            singleMetric: {
                url: 'POST /monitoring/custom-metrics',
                body: {
                    metricType: 'application/request_count',
                    value: 42,
                    labels: { environment: 'production', region: 'asia-northeast1' },
                },
            },
            sampleMetrics: {
                url: 'POST /monitoring/custom-metrics/sample',
                description: 'Send predefined sample metrics (request_count, response_time, memory_usage)',
            },
        },
    });
});
export default monitoring;
