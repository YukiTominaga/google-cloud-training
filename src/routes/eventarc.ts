import { Hono } from 'hono';
import { LoggingService } from '../services/logging.service.js';
import { decodeDocumentEvent } from '../services/firestore-event.service.js';

const eventarc = new Hono();

const loggingService = new LoggingService();

// POST /eventarc/firestore/users
// Eventarc トリガー（Firestore database "utaha" の users/* の written イベント）の送信先。
// イベントは CloudEvents バイナリモードで届く: メタデータは ce-* ヘッダー、本文は protobuf の DocumentEventData。
// 設定手順は deploy/README.md の「Firestore（utaha/users）変更ログの Eventarc トリガー」を参照。
eventarc.post('/firestore/users', async (c) => {
  const ce = {
    id: c.req.header('ce-id') ?? null,
    type: c.req.header('ce-type') ?? null,
    source: c.req.header('ce-source') ?? null,
    subject: c.req.header('ce-subject') ?? null,
    time: c.req.header('ce-time') ?? null,
    database: c.req.header('ce-database') ?? null,
    document: c.req.header('ce-document') ?? null,
  };

  try {
    const body = new Uint8Array(await c.req.arrayBuffer());
    const { before, after, updatedFields } = decodeDocumentEvent(body);

    loggingService.logInfo('Firestore users document changed', {
      cloudEvent: ce,
      before,
      after,
      updatedFields,
    });

    return c.body(null, 204);
  } catch (error) {
    // デコードできないイベントは再送しても成功しないため、ERROR ログに残したうえで 2xx を返して再送を止める
    loggingService.logError(`Failed to decode Firestore event (ce-id=${ce.id})`, error);
    return c.body(null, 204);
  }
});

export default eventarc;
