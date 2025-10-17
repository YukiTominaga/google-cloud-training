import { Hono } from 'hono';
import { LoggingService } from '../services/logging.service.js';

const trace = new Hono();
const loggingService = new LoggingService();

/**
 * カスタムspanのデモエンドポイント
 * withSpanメソッドを使用してカスタムspanを作成し、
 * span内でログを出力すると自動的にtrace情報が付与される
 */
trace.get('/demo', async (c) => {
  try {
    // カスタムspanを作成して処理を実行
    const result = await loggingService.withSpan('demo-operation', async (span) => {
      // span内でログを出力（自動的にtrace情報が付与される）
      loggingService.logInfo('Starting demo operation', { step: 1 });

      // 何か処理をシミュレート
      await new Promise((resolve) => setTimeout(resolve, 100));

      // span属性を追加
      span.setAttribute('demo.step', '2');
      loggingService.logInfo('Processing demo operation', { step: 2 });

      await new Promise((resolve) => setTimeout(resolve, 100));

      loggingService.logInfo('Completed demo operation', { step: 3 });

      return { message: 'Demo operation completed', timestamp: new Date().toISOString() };
    });

    return c.json({
      success: true,
      data: result,
      message: 'Check Cloud Trace and Cloud Logging to see the span and associated logs',
    });
  } catch (error) {
    return c.json(
      {
        success: false,
        error: 'Demo operation failed',
      },
      500,
    );
  }
});

/**
 * ネストされたspanのデモ
 */
trace.get('/nested', async (c) => {
  try {
    const result = await loggingService.withSpan('parent-operation', async (parentSpan) => {
      loggingService.logInfo('Parent operation started');
      parentSpan.setAttribute('operation.type', 'parent');

      // 子spanを作成
      const childResult = await loggingService.withSpan('child-operation', async (childSpan) => {
        loggingService.logInfo('Child operation started');
        childSpan.setAttribute('operation.type', 'child');

        await new Promise((resolve) => setTimeout(resolve, 50));

        loggingService.logInfo('Child operation completed');
        return { child: 'completed' };
      });

      loggingService.logInfo('Parent operation completed', childResult);
      return { parent: 'completed', child: childResult };
    });

    return c.json({
      success: true,
      data: result,
      message: 'Check Cloud Trace to see the nested spans',
    });
  } catch (error) {
    return c.json(
      {
        success: false,
        error: 'Nested operation failed',
      },
      500,
    );
  }
});

/**
 * エラーハンドリングのデモ
 * spanでエラーが発生した場合の処理
 */
trace.get('/error', async (c) => {
  try {
    await loggingService.withSpan('error-operation', async (span) => {
      loggingService.logInfo('Operation started');
      span.setAttribute('will.fail', 'true');

      // 意図的にエラーを発生させる
      throw new Error('Simulated error in span');
    });

    return c.json({ success: true });
  } catch (error) {
    // エラーは既にwithSpan内でログ出力されている
    return c.json(
      {
        success: false,
        message: 'Error was logged with trace information',
        error: error instanceof Error ? error.message : 'Unknown error',
      },
      500,
    );
  }
});

/**
 * 長時間処理のデモ（約10秒、4つの子span）
 * 複数の処理ステップを持つ長時間実行される処理のトレース
 */
trace.get('/slow', async (c) => {
  try {
    const result = await loggingService.withSpan('long-process-operation', async (parentSpan) => {
      parentSpan.setAttribute('operation.type', 'long-running');
      parentSpan.setAttribute('operation.steps', 4);
      loggingService.logInfo('Long process started', { totalSteps: 4 });

      const results: any[] = [];

      // Step 1: データ取得（約2秒）
      const step1Result = await loggingService.withSpan('step-1-fetch-data', async (span) => {
        span.setAttribute('step.number', 1);
        span.setAttribute('step.name', 'fetch-data');
        loggingService.logInfo('Step 1: Fetching data from database', { step: 1 });

        await new Promise((resolve) => setTimeout(resolve, 2000));

        const data = { records: 1000, fetchTime: 2000 };
        span.setAttribute('step.records', data.records);
        loggingService.logInfo('Step 1: Data fetched successfully', data);

        return data;
      });
      results.push(step1Result);

      // Step 2: データ処理（約3秒）
      const step2Result = await loggingService.withSpan('step-2-process-data', async (span) => {
        span.setAttribute('step.number', 2);
        span.setAttribute('step.name', 'process-data');
        loggingService.logInfo('Step 2: Processing data', {
          step: 2,
          inputRecords: step1Result.records,
        });

        await new Promise((resolve) => setTimeout(resolve, 3000));

        const processed = { processedRecords: step1Result.records, processingTime: 3000 };
        span.setAttribute('step.processed_records', processed.processedRecords);
        loggingService.logInfo('Step 2: Data processed successfully', processed);

        return processed;
      });
      results.push(step2Result);

      // Step 3: データ検証（約2.5秒）
      const step3Result = await loggingService.withSpan('step-3-validate-data', async (span) => {
        span.setAttribute('step.number', 3);
        span.setAttribute('step.name', 'validate-data');
        loggingService.logInfo('Step 3: Validating processed data', {
          step: 3,
          recordsToValidate: step2Result.processedRecords,
        });

        await new Promise((resolve) => setTimeout(resolve, 2500));

        const validated = {
          validRecords: step2Result.processedRecords - 10,
          invalidRecords: 10,
          validationTime: 2500,
        };
        span.setAttribute('step.valid_records', validated.validRecords);
        span.setAttribute('step.invalid_records', validated.invalidRecords);
        loggingService.logInfo('Step 3: Validation completed', validated);

        return validated;
      });
      results.push(step3Result);

      // Step 4: データ保存（約2.5秒）
      const step4Result = await loggingService.withSpan('step-4-save-data', async (span) => {
        span.setAttribute('step.number', 4);
        span.setAttribute('step.name', 'save-data');
        loggingService.logInfo('Step 4: Saving validated data', {
          step: 4,
          recordsToSave: step3Result.validRecords,
        });

        await new Promise((resolve) => setTimeout(resolve, 2500));

        const saved = { savedRecords: step3Result.validRecords, saveTime: 2500 };
        span.setAttribute('step.saved_records', saved.savedRecords);
        loggingService.logInfo('Step 4: Data saved successfully', saved);

        return saved;
      });
      results.push(step4Result);

      parentSpan.setAttribute('operation.completed', true);
      loggingService.logInfo('Long process completed successfully', {
        totalTime: '~10s',
        steps: results,
      });

      return {
        message: 'Long process completed successfully',
        totalSteps: 4,
        results: results,
        timestamp: new Date().toISOString(),
      };
    });

    return c.json({
      success: true,
      data: result,
      message: 'Check Cloud Trace to see the 4 child spans under the parent span',
    });
  } catch (error) {
    return c.json(
      {
        success: false,
        error: 'Long process failed',
      },
      500,
    );
  }
});

/**
 * 利用可能なトレースエンドポイントの情報
 */
trace.get('/info', (c) => {
  return c.json({
    description: 'Cloud Trace integration endpoints',
    endpoints: [
      {
        path: 'GET /trace/demo',
        description: 'カスタムspanを作成し、span内でログを出力するデモ',
        features: ['カスタムspan作成', 'span属性の追加', 'ログとトレースの連携'],
      },
      {
        path: 'GET /trace/nested',
        description: 'ネストされたspanのデモ',
        features: ['親子関係のあるspan', 'span間の関連付け'],
      },
      {
        path: 'GET /trace/error',
        description: 'span内でのエラーハンドリングのデモ',
        features: ['エラーの記録', 'エラーログとトレースの連携'],
      },
      {
        path: 'GET /trace/long-process',
        description: '長時間処理のデモ（約10秒、4つの子span）',
        features: [
          '複数ステップの処理',
          '各ステップが独立したspan',
          'Step 1: データ取得 (2s)',
          'Step 2: データ処理 (3s)',
          'Step 3: データ検証 (2.5s)',
          'Step 4: データ保存 (2.5s)',
        ],
        estimatedDuration: '~10 seconds',
      },
    ],
    note: '既存の /logging/* エンドポイントも自動的にトレースされます',
  });
});

export default trace;
