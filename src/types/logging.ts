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
  severity: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  message: string;
  data: any;
}
