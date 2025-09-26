import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { config, validateConfig } from './config/config.js';
import logging from './routes/logging.js';
import monitoring from './routes/monitoring.js';
// アプリケーション設定の検証
const configValidation = validateConfig();
if (!configValidation.isValid) {
  console.error('Application configuration errors:');
  configValidation.errors.forEach((error) => console.error(`- ${error}`));
  process.exit(1);
}
console.log(`Application configuration:`);
console.log(`- Project ID: ${config.projectId}`);
console.log(`- Environment: ${config.nodeEnv}`);
console.log(`- Port: ${config.port}`);
const app = new Hono();
// 基本ルート
app.get('/', (c) => {
  return c.text('Hello Hono!');
});
// monitoringルートを統合
app.route('/monitoring', monitoring);
// loggingルートを統合
app.route('/logging', logging);
serve(
  {
    fetch: app.fetch,
    port: config.port,
  },
  (info) => {
    console.log(`Server is running on http://localhost:${info.port}`);
    console.log(`Health check available at: http://localhost:${info.port}/monitoring/health`);
  },
);
