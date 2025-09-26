// 統合されたアプリケーション設定
// 統合設定オブジェクト
export const config = {
  // Google Cloud Project ID（必須）
  projectId: process.env.GOOGLE_CLOUD_PROJECT || 'your-project-id',
  // 実行環境
  nodeEnv: process.env.NODE_ENV || 'development',
  // サーバーポート
  port: parseInt(process.env.PORT || '3000', 10),
  // ローカル開発時のテスト用フラグ
  enableLocalTesting: (process.env.NODE_ENV || 'development') === 'development',
};
// 設定の検証
export function validateConfig() {
  const errors = [];
  if (!config.projectId || config.projectId === 'your-project-id') {
    errors.push('GOOGLE_CLOUD_PROJECT environment variable is required');
  }
  if (isNaN(config.port) || config.port <= 0) {
    errors.push('PORT must be a valid positive number');
  }
  return {
    isValid: errors.length === 0,
    errors,
  };
}
