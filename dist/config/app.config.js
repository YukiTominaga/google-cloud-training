// グローバルなアプリケーション設定
export const appConfig = {
  // Google Cloud Project ID（必須）
  projectId: process.env.GOOGLE_CLOUD_PROJECT || 'your-project-id',
  // 実行環境
  nodeEnv: process.env.NODE_ENV || 'development',
  // サーバーポート
  port: parseInt(process.env.PORT || '3000', 10),
};
// アプリケーション設定の検証
export function validateAppConfig() {
  const errors = [];
  if (!appConfig.projectId || appConfig.projectId === 'your-project-id') {
    errors.push('GOOGLE_CLOUD_PROJECT environment variable is required');
  }
  if (isNaN(appConfig.port) || appConfig.port <= 0) {
    errors.push('PORT must be a valid positive number');
  }
  return {
    isValid: errors.length === 0,
    errors,
  };
}
