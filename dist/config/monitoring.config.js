// Google Cloud Monitoring設定
import { appConfig } from './app.config.js';
export const monitoringConfig = {
  // グローバルconfigからプロジェクトIDを取得
  projectId: appConfig.projectId,
  // ローカル開発時のテスト用フラグ
  enableLocalTesting: appConfig.nodeEnv === 'development',
};
// Google Cloud Monitoring用の設定チェック
export function validateMonitoringConfig() {
  const errors = [];
  if (!monitoringConfig.projectId || monitoringConfig.projectId === 'your-project-id') {
    errors.push('GOOGLE_CLOUD_PROJECT environment variable is required');
  }
  return {
    isValid: errors.length === 0,
    errors,
  };
}
