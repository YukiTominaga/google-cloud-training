// Google Cloud Monitoringのカスタム指標関連の型定義

export interface CustomMetricRequest {
  metricType: string;
  value: number;
  labels?: Record<string, string>;
  description?: string;
}

export interface CustomMetricResponse {
  success: boolean;
  metricType: string;
  timestamp: string;
  message: string;
}
