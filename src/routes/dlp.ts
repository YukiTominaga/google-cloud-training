import { Hono } from 'hono';
import { DlpService, MIN_LIKELIHOOD_DESCRIPTIONS } from '../services/dlp.service.js';
import { LoggingService } from '../services/logging.service.js';
import type {
  DlpMaskImageRequest,
  DlpMaskImageResponse,
  DlpLikelihood,
} from '../types/dlp.js';

const dlp = new Hono();
const dlpService = new DlpService();
const loggingService = new LoggingService();

/** 有効なmin_likelihoodの値 */
const VALID_LIKELIHOODS: DlpLikelihood[] = [
  'LIKELIHOOD_UNSPECIFIED',
  'VERY_UNLIKELY',
  'UNLIKELY',
  'POSSIBLE',
  'LIKELY',
  'VERY_LIKELY',
];

/**
 * POST /dlp - GCSに保存された画像の個人情報をマスキング
 *
 * リクエストボディ:
 * - gcs_path: GCSオブジェクトのパス（必須）例: gs://bucket-name/path/to/image.png
 * - min_likelihood: 検出の最小確度（任意）デフォルト: POSSIBLE
 *
 * min_likelihoodを変更することで誤検知を防げます:
 * - 低い値（VERY_UNLIKELY, UNLIKELY）: 多くの検出、誤検知も多い
 * - 高い値（LIKELY, VERY_LIKELY）: 検出件数減、誤検知が減り精度向上
 *
 * curl -X POST http://localhost:3000/dlp -H "Content-Type: application/json" \
 *   -d '{"gcs_path": "gs://my-bucket/images/sample.png", "min_likelihood": "LIKELY"}'
 */
dlp.post('/', async (c) => {
  try {
    const body = (await c.req.json()) as Partial<DlpMaskImageRequest>;

    // バリデーション
    if (!body.gcs_path || typeof body.gcs_path !== 'string') {
      return c.json(
        {
          success: false,
          message: 'gcs_path is required',
          hint: 'Example: {"gcs_path": "gs://bucket-name/path/to/image.png", "min_likelihood": "LIKELY", "email_only": false}',
        } satisfies DlpMaskImageResponse,
        400,
      );
    }

    const minLikelihood: DlpLikelihood =
      body.min_likelihood && VALID_LIKELIHOODS.includes(body.min_likelihood)
        ? body.min_likelihood
        : 'POSSIBLE';

    const emailOnly = body.email_only === true;
    const hotword = typeof body.hotword === 'string' ? body.hotword : undefined;

    const result = await dlpService.maskImageInGcs(
      body.gcs_path,
      minLikelihood,
      emailOnly,
      hotword,
    );

    const response: DlpMaskImageResponse = {
      success: true,
      output_gcs_path: result.outputGcsPath,
      findings_count: result.findingsCount,
      message: 'Image redacted successfully',
      inspect_config_used: result.inspectConfigUsed,
    };

    return c.json(response);
  } catch (error) {
    loggingService.logErrorWithContext(c, 'Error masking image with DLP', error);

    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    const isClientError =
      errorMessage.includes('Invalid GCS path') ||
      errorMessage.includes('Unsupported image format');

    return c.json(
      {
        success: false,
        message: 'Failed to mask image',
        error: errorMessage,
      } satisfies DlpMaskImageResponse,
      isClientError ? 400 : 500,
    );
  }
});

/**
 * GET /dlp - min_likelihoodの説明とエンドポイントの使い方
 *
 * 検知レベル（min_likelihood）を変更することで誤検知を防げることを説明
 */
dlp.get('/', (c) => {
  return c.json({
    endpoint: 'POST /dlp',
    description: 'GCSに保存された画像の個人情報をマスキングします',
    request_body: {
      gcs_path: {
        type: 'string',
        required: true,
        description: 'GCSオブジェクトのパス（例: gs://bucket-name/path/to/image.png）',
      },
      min_likelihood: {
        type: 'string',
        required: false,
        default: 'POSSIBLE',
        description: '検出の最小確度。高いほど誤検知が減ります',
        values: VALID_LIKELIHOODS,
      },
      email_only: {
        type: 'boolean',
        required: false,
        default: false,
        description:
          'trueの場合、メールアドレスのみ検出・マスキング。ファイル名は a.emailonly.png の形式',
      },
      hotword: {
        type: 'string',
        required: false,
        description:
          '指定すると、その文字列の近く（前後50文字）にある個人情報のみマスキング。ファイル名は a.hotword.png',
      },
    },
    min_likelihood_explanations: {
      description:
        'min_likelihoodを高く設定すると、検出の確度が高いもののみがマスキング対象になり、誤検知を防げます',
      levels: Object.entries(MIN_LIKELIHOOD_DESCRIPTIONS).map(([key, desc]) => ({
        value: key,
        description: desc,
      })),
      recommendation:
        '誤検知が多い場合は LIKELY または VERY_LIKELY に上げてください。検出漏れが多い場合は POSSIBLE や UNLIKELY に下げてください。',
    },
    supported_formats: ['.png', '.jpg', '.jpeg', '.bmp'],
    output_location:
      'マスキング済み画像は redacted/ に保存。通常: a.possible.png、email_only: a.emailonly.png、hotword: a.hotword.png',
    example: {
      curl: `curl -X POST ${c.req.url} -H "Content-Type: application/json" -d '{"gcs_path": "gs://your-bucket/images/sample.png", "min_likelihood": "LIKELY"}'`,
    },
  });
});

export default dlp;
