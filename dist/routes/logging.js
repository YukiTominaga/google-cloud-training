import { Hono } from 'hono';
import { LoggingService } from '../services/logging.service.js';
const logging = new Hono();
// LoggingServiceのインスタンスを作成
const loggingService = new LoggingService();
// POST /logging/structure エンドポイント
// curl -X POST https://google-cloud-training-103175005729.asia-northeast1.run.app/logging/structure -H "Content-Type: application/json" -H "traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01" -d '{"userId": "123", "action": "login"}'
logging.post('/structure', async (c) => {
  try {
    const body = await c.req.json();
    // traceparentヘッダーを取得
    const traceparent = c.req.header('traceparent');
    // 構造化ログとして出力（trace情報付き）
    loggingService.logStructuredData(body, traceparent);
    const response = {
      success: true,
      message: 'Request body logged with trace information',
    };
    return c.json(response);
  } catch (error) {
    console.error('Error processing logging request:', error);
    const errorResponse = {
      success: false,
      message: 'Failed to log request body',
    };
    return c.json(errorResponse, 500);
  }
});
// ログレベル別のテスト用エンドポイント
logging.post('/test/:level', async (c) => {
  try {
    const level = c.req.param('level');
    const body = await c.req.json();
    let logId;
    switch (level) {
      case 'info':
        logId = loggingService.logInfo('Test info log', body);
        break;
      case 'warn':
        logId = loggingService.logWarn('Test warning log', body);
        break;
      case 'error':
        logId = loggingService.logError('Test error log', body);
        break;
      case 'debug':
        logId = loggingService.logDebug('Test debug log', body);
        break;
      default:
        return c.json({ error: 'Invalid log level. Use: info, warn, error, debug' }, 400);
    }
    return c.json({
      success: true,
      message: `${level.toUpperCase()} level log created`,
    });
  } catch (error) {
    console.error('Error in test logging:', error);
    return c.json({ error: 'Failed to create test log' }, 500);
  }
});
// 利用可能なログエンドポイントの情報を取得
logging.get('/info', (c) => {
  return c.json({
    availableEndpoints: [
      {
        endpoint: 'POST /logging/structure',
        description:
          'リクエストボディをJSON形式で出力（traceparentヘッダーがあればtrace情報も含む）',
        example: {
          url: 'POST /logging/structure',
          headers: {
            'Content-Type': 'application/json',
            traceparent: '00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01',
          },
          body: {
            userId: '123',
            action: 'login',
            timestamp: '2024-01-01T00:00:00Z',
          },
        },
      },
      {
        endpoint: 'POST /logging/test/:level',
        description: 'ログレベル別のテスト用エンドポイント',
        levels: ['info', 'warn', 'error', 'debug'],
        example: {
          url: 'POST /logging/test/info',
          body: { message: 'Test data', value: 42 },
        },
      },
    ],
    logFormat: {
      logId: 'string (UUID)',
      timestamp: 'string (ISO 8601)',
      level: 'INFO | WARN | ERROR | DEBUG',
      message: 'string',
      data: 'any (リクエストボディまたは任意のデータ)',
    },
  });
});
export default logging;
