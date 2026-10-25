# syntax=docker/dockerfile:1

ARG NODE_VERSION=24

# ==============================================================================
# Build Stage
# ==============================================================================
FROM node:${NODE_VERSION}-alpine AS builder

WORKDIR /app

# パッケージファイルを先にコピーし、依存関係のレイヤーキャッシュを効かせる
COPY package.json package-lock.json ./

# 依存関係のインストール（本番 + 開発依存関係）
# npm のキャッシュは BuildKit のキャッシュマウントに置き、イメージには残さない
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

# アプリケーションのソースコードをコピーして TypeScript をビルド
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# 開発依存関係を取り除き、本番用の node_modules だけを残す
RUN npm prune --omit=dev

# ==============================================================================
# Production Stage
# ==============================================================================
FROM node:${NODE_VERSION}-alpine AS production

# PID 1 としてシグナルを正しく転送するための init
RUN apk add --no-cache dumb-init

ENV NODE_ENV=production
WORKDIR /app

# ベースイメージに同梱の非 root ユーザー node（UID 1000）で実行する
COPY --chown=node:node package.json package-lock.json ./
COPY --from=builder --chown=node:node /app/node_modules ./node_modules
COPY --from=builder --chown=node:node /app/dist ./dist

USER node

# ポートの公開（デフォルト3000、環境変数 PORT で変更可能）
EXPOSE 3000

# アプリケーションの起動
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "dist/index.js"]
