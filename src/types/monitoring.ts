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

export interface LabelDescriptor {
  key: string;
  valueType: 'STRING' | 'BOOL' | 'INT64';
  description: string;
}

export interface MetricDescriptor {
  type: string;
  metricKind: 'GAUGE' | 'CUMULATIVE' | 'DELTA';
  valueType: 'BOOL' | 'INT64' | 'DOUBLE' | 'STRING' | 'DISTRIBUTION';
  description: string;
  displayName: string;
  labels?: LabelDescriptor[];
}

export interface MonitoredResource {
  type: 'generic_task' | 'generic_node' | 'gce_instance' | 'k8s_pod' | 'global';
  labels: Record<string, string>;
}
