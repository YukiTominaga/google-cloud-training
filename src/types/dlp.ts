// Google Cloud DLP API のリクエスト/レスポンス型定義

/**
 * DLP API の Likelihood（検出確度）の値
 * 値が高いほど検出件数は減り、誤検知は減ります
 *
 * @see https://cloud.google.com/sensitive-data-protection/docs/reference/rest/v2/InspectConfig#Likelihood
 */
export type DlpLikelihood =
  | 'LIKELIHOOD_UNSPECIFIED'
  | 'VERY_UNLIKELY'
  | 'UNLIKELY'
  | 'POSSIBLE'
  | 'LIKELY'
  | 'VERY_LIKELY';

/**
 * GCS画像マスキングリクエストのボディ
 */
export interface DlpMaskImageRequest {
  /** GCSオブジェクトのパス（例: gs://bucket-name/path/to/image.png） */
  gcs_path: string;

  /**
   * 検出の最小確度（min_likelihood）
   * この閾値以上の検出結果のみマスキング対象になります
   *
   * - VERY_UNLIKELY: 誤検知の可能性が最も高い
   * - UNLIKELY: 誤検知の可能性が高い
   * - POSSIBLE: デフォルト。いくつかのマッチングシグナルあり
   * - LIKELY: 誤検知の可能性が低い
   * - VERY_LIKELY: 誤検知の可能性が最も低い
   */
  min_likelihood?: DlpLikelihood;

  /**
   * trueの場合、検出するInfoTypeをメールアドレス（EMAIL_ADDRESS）のみに絞る
   * ファイル名には emailonly が付与される（例: a.emailonly.png）
   */
  email_only?: boolean;

  /**
   * Hotword（キーワード）を指定すると、その文字列の近くにある個人情報のみマスキングする
   * 例: "患者" を指定すると「患者」の近くの氏名・連絡先などだけがマスキングされる
   * ファイル名には hotword が付与される（例: a.hotword.png）
   */
  hotword?: string;
}

/**
 * DLPマスキングレスポンス
 */
export interface DlpMaskImageResponse {
  success: boolean;
  /** マスキング済み画像の保存先GCSパス（redacted/元のパス） */
  output_gcs_path?: string;
  /** 検出された個人情報の件数（includeFindings時） */
  findings_count?: number;
  message: string;
  /** 使用した検出設定（説明用） */
  inspect_config_used?: {
    min_likelihood: string;
    description: string;
  };
  /** エラー時の詳細メッセージ */
  error?: string;
  /** バリデーションエラー時のヒント */
  hint?: string;
}
