import { DlpServiceClient, protos } from '@google-cloud/dlp';
import { Storage } from '@google-cloud/storage';
import { config } from '../config/config.js';
import type { DlpLikelihood } from '../types/dlp.js';

/** GCSパス形式: gs://bucket-name/path/to/object */
const GCS_PATH_REGEX = /^gs:\/\/([^/]+)\/(.+)$/;

/** サポートされる画像形式とDLP BytesTypeの対応 */
const IMAGE_TYPE_MAP: Record<string, protos.google.privacy.dlp.v2.ByteContentItem.BytesType> = {
  '.png': protos.google.privacy.dlp.v2.ByteContentItem.BytesType.IMAGE_PNG,
  '.jpg': protos.google.privacy.dlp.v2.ByteContentItem.BytesType.IMAGE_JPEG,
  '.jpeg': protos.google.privacy.dlp.v2.ByteContentItem.BytesType.IMAGE_JPEG,
  '.bmp': protos.google.privacy.dlp.v2.ByteContentItem.BytesType.IMAGE_BMP,
};

/** Likelihoodの文字列からprotosのenumへのマッピング */
const LIKELIHOOD_MAP: Record<string, protos.google.privacy.dlp.v2.Likelihood> = {
  LIKELIHOOD_UNSPECIFIED: protos.google.privacy.dlp.v2.Likelihood.LIKELIHOOD_UNSPECIFIED,
  VERY_UNLIKELY: protos.google.privacy.dlp.v2.Likelihood.VERY_UNLIKELY,
  UNLIKELY: protos.google.privacy.dlp.v2.Likelihood.UNLIKELY,
  POSSIBLE: protos.google.privacy.dlp.v2.Likelihood.POSSIBLE,
  LIKELY: protos.google.privacy.dlp.v2.Likelihood.LIKELY,
  VERY_LIKELY: protos.google.privacy.dlp.v2.Likelihood.VERY_LIKELY,
};

/** Likelihoodをファイル名用の文字列に変換（例: POSSIBLE → possible） */
const LIKELIHOOD_TO_FILENAME: Record<DlpLikelihood, string> = {
  LIKELIHOOD_UNSPECIFIED: 'unspecified',
  VERY_UNLIKELY: 'very_unlikely',
  UNLIKELY: 'unlikely',
  POSSIBLE: 'possible',
  LIKELY: 'likely',
  VERY_LIKELY: 'very_likely',
};

/** min_likelihoodの説明（誤検知防止の説明用） */
export const MIN_LIKELIHOOD_DESCRIPTIONS: Record<string, string> = {
  LIKELIHOOD_UNSPECIFIED: 'デフォルト（POSSIBLEと同等）',
  VERY_UNLIKELY: '誤検知の可能性が最も高い - 多くの検出、誤検知も多い',
  UNLIKELY: '誤検知の可能性が高い',
  POSSIBLE: 'デフォルト。いくつかのマッチングシグナルあり',
  LIKELY: '誤検知の可能性が低い - 検出件数減、精度向上',
  VERY_LIKELY: '誤検知の可能性が最も低い - 最少検出、最高精度',
};

export class DlpService {
  private dlpClient: DlpServiceClient;
  private storage: Storage;
  private projectId: string;

  constructor() {
    this.dlpClient = new DlpServiceClient();
    this.storage = new Storage();
    this.projectId = config.projectId;
  }

  /**
   * GCSパスをパースしてバケット名とオブジェクトパスを取得
   */
  private parseGcsPath(gcsPath: string): { bucket: string; name: string } {
    const match = gcsPath.match(GCS_PATH_REGEX);
    if (!match) {
      throw new Error(
        `Invalid GCS path: ${gcsPath}. Expected format: gs://bucket-name/path/to/object.png`,
      );
    }
    return { bucket: match[1], name: match[2] };
  }

  /**
   * ファイル拡張子からDLPのBytesTypeを取得
   */
  private getImageBytesType(
    filePath: string,
  ): protos.google.privacy.dlp.v2.ByteContentItem.BytesType {
    const ext = filePath.toLowerCase().slice(filePath.lastIndexOf('.'));
    const bytesType = IMAGE_TYPE_MAP[ext];
    if (!bytesType) {
      throw new Error(`Unsupported image format: ${ext}. Supported: .png, .jpg, .jpeg, .bmp`);
    }
    return bytesType;
  }

  /**
   * GCSから画像をダウンロード
   */
  private async downloadImageFromGcs(gcsPath: string): Promise<Buffer> {
    const { bucket, name } = this.parseGcsPath(gcsPath);
    const file = this.storage.bucket(bucket).file(name);
    const [contents] = await file.download();
    return Buffer.from(contents);
  }

  /**
   * マスキング済み画像をGCSに保存
   * 元のパスが a.png で POSSIBLE の場合 → redacted/a.possible.png
   * 元のパスが a.png で email_only の場合 → redacted/a.emailonly.png
   */
  private async saveRedactedImageToGcs(
    gcsPath: string,
    redactedBuffer: Buffer,
    filenameSuffix: string,
  ): Promise<string> {
    const { bucket, name } = this.parseGcsPath(gcsPath);

    // パスをディレクトリとファイル名に分割し、拡張子の直前に .{suffix} を挿入
    const lastSlash = name.lastIndexOf('/');
    const dir = lastSlash >= 0 ? name.slice(0, lastSlash + 1) : '';
    const filename = lastSlash >= 0 ? name.slice(lastSlash + 1) : name;
    const extIndex = filename.lastIndexOf('.');
    const baseName = extIndex >= 0 ? filename.slice(0, extIndex) : filename;
    const ext = extIndex >= 0 ? filename.slice(extIndex) : '';

    const outputFilename = `${baseName}.${filenameSuffix}${ext}`;
    const outputPath = `redacted/${dir}${outputFilename}`;
    const file = this.storage.bucket(bucket).file(outputPath);
    await file.save(redactedBuffer, {
      contentType: this.getContentTypeFromPath(name),
    });
    return `gs://${bucket}/${outputPath}`;
  }

  /**
   * ファイルパスからContent-Typeを取得
   */
  private getContentTypeFromPath(filePath: string): string {
    const ext = filePath.toLowerCase().slice(filePath.lastIndexOf('.'));
    const contentTypeMap: Record<string, string> = {
      '.png': 'image/png',
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.bmp': 'image/bmp',
    };
    return contentTypeMap[ext] ?? 'application/octet-stream';
  }

  /**
   * 正規表現の特殊文字をエスケープ（Hotwordをリテラルマッチさせるため）
   */
  private escapeRegexLiteral(str: string): string {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  /**
   * GCSに保存された画像の個人情報をマスキング
   *
   * @param gcsPath - GCSオブジェクトのパス（gs://bucket/path/to/image.png）
   * @param minLikelihood - 検出の最小確度。高いほど誤検知が減る
   * @param emailOnly - trueの場合、メールアドレスのみ検出・マスキング
   * @param hotword - 指定時、その文字列の近くの個人情報のみマスキング
   */
  async maskImageInGcs(
    gcsPath: string,
    minLikelihood: DlpLikelihood = 'POSSIBLE',
    emailOnly = false,
    hotword?: string,
  ): Promise<{
    redactedImage: Buffer;
    outputGcsPath: string;
    findingsCount: number;
    inspectConfigUsed: { min_likelihood: string; description: string };
  }> {
    // GCSから画像をダウンロード
    const imageBuffer = await this.downloadImageFromGcs(gcsPath);
    const bytesType = this.getImageBytesType(gcsPath);

    // Likelihoodをprotosのenumに変換
    const likelihoodEnum =
      LIKELIHOOD_MAP[minLikelihood] ?? protos.google.privacy.dlp.v2.Likelihood.POSSIBLE;

    const parent = `projects/${this.projectId}/locations/global`;

    const infoTypes = emailOnly
      ? [{ name: 'EMAIL_ADDRESS' }]
      : [
          { name: 'PERSON_NAME' },
          { name: 'EMAIL_ADDRESS' },
          { name: 'PHONE_NUMBER' },
          { name: 'CREDIT_CARD_NUMBER' },
          { name: 'STREET_ADDRESS' },
        ];

    const useHotword = typeof hotword === 'string' && hotword.trim().length > 0;

    const inspectConfig: protos.google.privacy.dlp.v2.IInspectConfig = {
      infoTypes,
      minLikelihood: useHotword
        ? protos.google.privacy.dlp.v2.Likelihood.VERY_LIKELY
        : likelihoodEnum,
    };

    if (useHotword) {
      const hotwordPattern = this.escapeRegexLiteral(hotword!.trim());
      inspectConfig.ruleSet = [
        {
          infoTypes,
          rules: [
            {
              hotwordRule: {
                hotwordRegex: { pattern: hotwordPattern },
                proximity: { windowBefore: 5, windowAfter: 5 },
                likelihoodAdjustment: {
                  fixedLikelihood: protos.google.privacy.dlp.v2.Likelihood.VERY_LIKELY,
                },
              },
            },
          ],
        },
      ];
    }

    const request: protos.google.privacy.dlp.v2.IRedactImageRequest = {
      parent,
      inspectConfig,
      imageRedactionConfigs: infoTypes.map((it) => ({ infoType: it })),
      includeFindings: true,
      byteItem: {
        type: bytesType,
        data: imageBuffer,
      },
    };

    const [response] = await this.dlpClient.redactImage(request);

    if (!response.redactedImage || response.redactedImage.length === 0) {
      throw new Error('DLP API returned empty redacted image');
    }

    const redactedBuffer = Buffer.from(response.redactedImage);
    const findingsCount = response.inspectResult?.findings?.length ?? 0;

    const suffixParts: string[] = [];
    if (emailOnly) suffixParts.push('emailonly');
    if (useHotword) suffixParts.push('hotword');
    if (suffixParts.length === 0) {
      suffixParts.push(LIKELIHOOD_TO_FILENAME[minLikelihood] ?? 'possible');
    }
    const filenameSuffix = suffixParts.join('.');

    const outputGcsPath = await this.saveRedactedImageToGcs(
      gcsPath,
      redactedBuffer,
      filenameSuffix,
    );

    const inspectConfigDescription = emailOnly
      ? 'メールアドレスのみ検出'
      : useHotword
        ? `Hotword付近のみ検出（hotword: "${hotword!.trim()}")`
        : (MIN_LIKELIHOOD_DESCRIPTIONS[minLikelihood] ?? minLikelihood);

    return {
      redactedImage: redactedBuffer,
      outputGcsPath,
      findingsCount,
      inspectConfigUsed: {
        min_likelihood: minLikelihood,
        description: inspectConfigDescription,
      },
    };
  }
}
