// ログ関連の型定義

export interface LogStructureRequest {
  [key: string]: any; // 任意のJSONオブジェクト
}

export interface LogStructureResponse {
  success: boolean;
  message: string;
}

export interface LogEntry {
  logId: string;
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG';
  message: string;
  data: any;
}
