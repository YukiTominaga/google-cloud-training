# ==============================================================================
# Build Stage
# ==============================================================================
FROM node:22-alpine AS builder

# セキュリティの向上のため非rootユーザーを作成
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 hono

# 作業ディレクトリの設定
WORKDIR /app

# パッケージファイルをコピー（キャッシュ効率化のため最初にコピー）
COPY package.json package-lock.json ./

# 依存関係のインストール（本番 + 開発依存関係）
RUN npm ci

# アプリケーションのソースコードをコピー
COPY . .

# TypeScriptビルドの実行
RUN npm run build

# ==============================================================================
# Production Stage
# ==============================================================================
FROM node:22-alpine AS production

# セキュリティパッケージのインストール
RUN apk add --no-cache dumb-init

# 非rootユーザーを作成
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 hono

# 作業ディレクトリの設定
WORKDIR /app

# 所有者を適切に設定
RUN chown hono:nodejs /app

# パッケージファイルをコピー
COPY package.json package-lock.json ./

# 本番用依存関係のみインストール
RUN npm ci --production && npm cache clean --force

# ビルド成果物をコピー
COPY --from=builder --chown=hono:nodejs /app/dist ./dist

# 非rootユーザーに切り替え
USER hono

# ポートの公開（デフォルト3000、環境変数で変更可能）
EXPOSE 3000

# アプリケーションの起動
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "dist/index.js"]
