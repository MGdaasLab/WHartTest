ARG NODE_BASE_IMAGE=node:22-alpine
FROM ${NODE_BASE_IMAGE}

WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmjs.org

COPY package.json ./
RUN npm config set registry "${NPM_REGISTRY}" && npm install

# 兼容修复：openclaw >= 2026.6 内置的 undici 会拒绝上游插件（2.0.1）显式设置的
# Content-Length 请求头，抛 "InvalidArgumentError: invalid content-length header"，
# 表现为微信 getUpdates 长轮询 TypeError: fetch failed（收不到消息、不回复）。
# 移除该头，交由 fetch 自动计算长度（HTTP 标准做法）；插件后续版本修复后可移除本步。
RUN sed -i '/"Content-Length": String(Buffer.byteLength/d' \
    /app/node_modules/@tencent-weixin/openclaw-weixin/src/api/api.ts

COPY . ./

EXPOSE 3001

CMD ["npm", "run", "start"]
