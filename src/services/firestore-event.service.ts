import protobuf from 'protobufjs';

/**
 * Eventarc の Firestore 直接イベントは application/protobuf 固定で届くため、
 * google.events.cloud.firestore.v1.DocumentEventData をデコードする。
 * 定義は https://github.com/googleapis/google-cloudevents の
 * proto/google/events/cloud/firestore/v1/data.proto（コメント・option を除去）。
 * .proto ファイルにすると dist にコピーされないため、文字列として埋め込む。
 */
const LATLNG_PROTO = `
syntax = "proto3";
package google.type;
message LatLng {
  double latitude = 1;
  double longitude = 2;
}
`;

const FIRESTORE_DATA_PROTO = `
syntax = "proto3";
package google.events.cloud.firestore.v1;

message DocumentEventData {
  Document value = 1;
  Document old_value = 2;
  DocumentMask update_mask = 3;
}

message DocumentMask {
  repeated string field_paths = 1;
}

message Document {
  string name = 1;
  map<string, Value> fields = 2;
  google.protobuf.Timestamp create_time = 3;
  google.protobuf.Timestamp update_time = 4;
}

message Value {
  oneof value_type {
    google.protobuf.NullValue null_value = 11;
    bool boolean_value = 1;
    int64 integer_value = 2;
    double double_value = 3;
    google.protobuf.Timestamp timestamp_value = 10;
    string string_value = 17;
    bytes bytes_value = 18;
    string reference_value = 5;
    google.type.LatLng geo_point_value = 8;
    ArrayValue array_value = 9;
    MapValue map_value = 6;
  }
}

message ArrayValue {
  repeated Value values = 1;
}

message MapValue {
  map<string, Value> fields = 1;
}
`;

const root = new protobuf.Root();
root.addJSON(protobuf.common.get('google/protobuf/timestamp.proto')!.nested!);
root.addJSON(protobuf.common.get('google/protobuf/struct.proto')!.nested!);
protobuf.parse(LATLNG_PROTO, root);
protobuf.parse(FIRESTORE_DATA_PROTO, root);
const DocumentEventData = root.lookupType('google.events.cloud.firestore.v1.DocumentEventData');

// toObject 後の形（parse の既定でフィールド名は camelCase になる）
interface TimestampObject {
  seconds?: string;
  nanos?: number;
}

interface ValueObject {
  valueType?: string;
  booleanValue?: boolean;
  integerValue?: string;
  doubleValue?: number;
  timestampValue?: TimestampObject;
  stringValue?: string;
  bytesValue?: string;
  referenceValue?: string;
  geoPointValue?: { latitude?: number; longitude?: number };
  arrayValue?: { values?: ValueObject[] };
  mapValue?: { fields?: Record<string, ValueObject> };
}

interface DocumentObject {
  name?: string;
  fields?: Record<string, ValueObject>;
  createTime?: TimestampObject;
  updateTime?: TimestampObject;
}

interface DocumentEventDataObject {
  value?: DocumentObject;
  oldValue?: DocumentObject;
  updateMask?: { fieldPaths?: string[] };
}

/** ログに出しやすい形に変換したドキュメント */
export interface PlainDocument {
  name: string;
  createTime: string | null;
  updateTime: string | null;
  fields: Record<string, unknown>;
}

export interface DecodedDocumentEvent {
  /** 変更前のドキュメント（作成イベントでは null） */
  before: PlainDocument | null;
  /** 変更後のドキュメント（削除イベントでは null） */
  after: PlainDocument | null;
  /** 変更されたフィールドパス（更新イベントのみ） */
  updatedFields: string[];
}

function toIsoString(ts: TimestampObject | undefined): string | null {
  if (!ts) return null;
  const millis = Number(ts.seconds ?? 0) * 1000 + Math.floor((ts.nanos ?? 0) / 1e6);
  return new Date(millis).toISOString();
}

/** Firestore の Value（型タグ付き）を素の JSON 値に変換する */
function toPlainValue(value: ValueObject): unknown {
  switch (value.valueType) {
    case 'nullValue':
      return null;
    case 'booleanValue':
      return value.booleanValue;
    case 'integerValue': {
      // int64 は文字列で受け取り、安全に表現できる範囲だけ number にする
      const n = Number(value.integerValue);
      return Number.isSafeInteger(n) ? n : value.integerValue;
    }
    case 'doubleValue':
      return value.doubleValue;
    case 'timestampValue':
      return toIsoString(value.timestampValue);
    case 'stringValue':
      return value.stringValue;
    case 'bytesValue':
      return value.bytesValue; // base64
    case 'referenceValue':
      return value.referenceValue;
    case 'geoPointValue':
      return {
        latitude: value.geoPointValue?.latitude ?? 0,
        longitude: value.geoPointValue?.longitude ?? 0,
      };
    case 'arrayValue':
      return (value.arrayValue?.values ?? []).map(toPlainValue);
    case 'mapValue':
      return toPlainFields(value.mapValue?.fields);
    default:
      return null;
  }
}

function toPlainFields(fields: Record<string, ValueObject> | undefined): Record<string, unknown> {
  return Object.fromEntries(Object.entries(fields ?? {}).map(([key, v]) => [key, toPlainValue(v)]));
}

function toPlainDocument(doc: DocumentObject | undefined): PlainDocument | null {
  if (!doc?.name) return null;
  return {
    name: doc.name,
    createTime: toIsoString(doc.createTime),
    updateTime: toIsoString(doc.updateTime),
    fields: toPlainFields(doc.fields),
  };
}

/** Eventarc から届いた protobuf のバイト列をデコードし、変更前後のドキュメントを返す */
export function decodeDocumentEvent(data: Uint8Array): DecodedDocumentEvent {
  const message = DocumentEventData.decode(data);
  const obj = DocumentEventData.toObject(message, {
    longs: String,
    bytes: String,
    oneofs: true,
  }) as DocumentEventDataObject;

  return {
    before: toPlainDocument(obj.oldValue),
    after: toPlainDocument(obj.value),
    updatedFields: obj.updateMask?.fieldPaths ?? [],
  };
}
