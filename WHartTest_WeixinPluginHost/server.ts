import { randomUUID } from "node:crypto";
import { createServer } from "node:http";
import { existsSync } from "node:fs";
import { appendFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { config as loadDotenv } from "dotenv";
import weixinPluginEntry from "@tencent-weixin/openclaw-weixin/index.ts";
import {
  clearStaleAccountsForUserId,
  DEFAULT_BASE_URL,
  listWeixinAccountIds,
  registerWeixinAccountId,
  resolveWeixinAccount,
  saveWeixinAccount,
  triggerWeixinChannelReload,
} from "@tencent-weixin/openclaw-weixin/src/auth/accounts.ts";
import {
  DEFAULT_ILINK_BOT_TYPE,
  startWeixinLoginWithQr,
  waitForWeixinLogin,
} from "@tencent-weixin/openclaw-weixin/src/auth/login-qr.ts";
import { clearContextTokensForAccount } from "@tencent-weixin/openclaw-weixin/src/messaging/inbound.ts";
import { normalizeAccountId } from "openclaw/plugin-sdk/account-id";
import {
  resolveCommandAuthorizedFromAuthorizers,
  shouldComputeCommandAuthorized,
} from "openclaw/plugin-sdk/command-auth";
import {
  createReplyDispatcherWithTyping,
  finalizeInboundContext,
} from "openclaw/plugin-sdk/reply-runtime";

type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

type JsonObject = { [key: string]: JsonValue };

type AccountStatusSnapshot = {
  accountId: string;
  configured: boolean;
  running: boolean;
  lastError: string | null;
  lastStartAt: number | null;
  lastStopAt: number | null;
  lastEventAt: number | null;
  lastInboundAt: number | null;
  lastOutboundAt: number | null;
};

type AccountRuntimeEntry = {
  accountId: string;
  controller: AbortController;
  promise: Promise<void>;
  snapshot: AccountStatusSnapshot;
};

const currentFilePath = fileURLToPath(import.meta.url);
const currentDir = path.dirname(currentFilePath);

function loadEnvFile(filename: string, override = false) {
  const envPath = path.join(currentDir, filename);
  if (!existsSync(envPath)) {
    return;
  }

  const result = loadDotenv({ path: envPath, override, quiet: true });
  if (result.error) {
    throw result.error;
  }
}

loadEnvFile(".env");
loadEnvFile(".env.local", true);

const port = Number.parseInt(process.env.PORT || "3001", 10);
const host = process.env.HOST || "0.0.0.0";
const backendBaseUrl = (
  process.env.WHARTTEST_BACKEND_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");
const backendApiKey = (process.env.WHARTTEST_API_KEY || "").trim();
const sharedDataDir = path.resolve(
  process.env.WHARTTEST_SHARED_DATA_DIR || path.join(currentDir, "..", "data"),
);
const openClawStateDir = path.resolve(
  process.env.OPENCLAW_STATE_DIR || path.join(sharedDataDir, "openclaw-state"),
);
const sessionStoreDir = path.join(openClawStateDir, "sessions");
const mediaStoreDir = path.join(sharedDataDir, "weixin-plugin-media");

process.env.OPENCLAW_STATE_DIR = openClawStateDir;
process.env.OPENCLAW_CONFIG =
  process.env.OPENCLAW_CONFIG || path.join(openClawStateDir, "openclaw.json");

const hostConfig: Record<string, unknown> = {
  channels: {
    "openclaw-weixin": {
      accounts: {},
    },
  },
  session: {
    store: sessionStoreDir,
  },
};

const accountRuntimes = new Map<string, AccountRuntimeEntry>();

function createLogger(prefix: string) {
  return {
    debug: (message: string, ...args: unknown[]) =>
      console.debug(prefix, message, ...args),
    info: (message: string, ...args: unknown[]) =>
      console.info(prefix, message, ...args),
    warn: (message: string, ...args: unknown[]) =>
      console.warn(prefix, message, ...args),
    error: (message: string, ...args: unknown[]) =>
      console.error(prefix, message, ...args),
  };
}

const logger = createLogger("[WHartTest-WeixinHost]");

let registeredChannel: Record<string, any> | null = null;

function noop(): void {}

function buildReplyDispatchResult(finalCount: number) {
  return {
    queuedFinal: finalCount > 0,
    counts: {
      tool: 0,
      block: 0,
      final: finalCount,
    },
  };
}

function sanitizeSessionKey(sessionKey: string): string {
  return (sessionKey || "unknown").replace(/[^0-9A-Za-z_.-]+/g, "_");
}

async function saveSharedMediaBuffer(
  buffer: Buffer,
  contentType?: string,
  subdir = "inbound",
  maxBytes = 20 * 1024 * 1024,
  originalFilename?: string,
) {
  if (buffer.length > maxBytes) {
    throw new Error(
      `media too large: ${buffer.length} bytes exceeds limit ${maxBytes}`,
    );
  }

  const ext =
    path.extname(originalFilename || "") ||
    (contentType?.includes("png")
      ? ".png"
      : contentType?.includes("gif")
        ? ".gif"
        : contentType?.includes("webp")
          ? ".webp"
          : contentType?.includes("jpeg") || contentType?.includes("jpg")
            ? ".jpg"
            : contentType?.includes("mp4")
              ? ".mp4"
              : ".bin");

  const targetDir = path.join(mediaStoreDir, subdir);
  await mkdir(targetDir, { recursive: true });
  const filename = `${Date.now()}-${randomUUID()}${ext}`;
  const filePath = path.join(targetDir, filename);
  await writeFile(filePath, buffer);

  return {
    id: filename,
    path: filePath,
    size: buffer.length,
    contentType,
  };
}

async function recordInboundSession(params: {
  storePath: string;
  sessionKey: string;
  ctx: Record<string, unknown>;
  onRecordError?: (err: unknown) => void;
}) {
  try {
    await mkdir(params.storePath, { recursive: true });
    const transcriptPath = path.join(
      params.storePath,
      `${sanitizeSessionKey(params.sessionKey)}.jsonl`,
    );
    await appendFile(
      transcriptPath,
      `${JSON.stringify({ ts: Date.now(), ctx: params.ctx })}\n`,
      "utf-8",
    );
  } catch (error) {
    params.onRecordError?.(error);
  }
}

async function withReplyDispatcher<T>(params: {
  dispatcher: {
    markComplete: () => void;
    waitForIdle: () => Promise<void>;
  };
  run: () => Promise<T>;
}): Promise<T> {
  try {
    const result = await params.run();
    params.dispatcher.markComplete();
    await params.dispatcher.waitForIdle();
    return result;
  } catch (error) {
    params.dispatcher.markComplete();
    try {
      await params.dispatcher.waitForIdle();
    } catch {
      noop();
    }
    throw error;
  }
}

function resolveStorePath(
  storePath?: string | null,
  opts?: { agentId?: string | null },
): string {
  if (storePath) {
    return storePath;
  }
  if (opts?.agentId) {
    return path.join(sessionStoreDir, sanitizeSessionKey(opts.agentId));
  }
  return sessionStoreDir;
}

function resolveAgentRoute(params: {
  accountId?: string | null;
  peer?: { id: string };
}) {
  const accountId = normalizeAccountId(params.accountId || "default");
  const peerId = normalizeAccountId(params.peer?.id || "direct");
  const sessionKey = `wharttest-weixin:${accountId}:${peerId}`;
  return {
    agentId: "wharttest",
    channel: "openclaw-weixin",
    accountId,
    sessionKey,
    mainSessionKey: sessionKey,
    lastRoutePolicy: "session",
    matchedBy: "binding.channel",
  };
}

async function callWhartTestInbound(ctx: Record<string, unknown>) {
  if (!backendApiKey) {
    throw new Error("WHARTTEST_API_KEY is not configured");
  }

  const response = await fetch(`${backendBaseUrl}/api/weixin/plugin/inbound/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": backendApiKey,
    },
    body: JSON.stringify({
      account_id: ctx.AccountId,
      peer_user_id: ctx.From || ctx.To,
      text: ctx.Body || "",
      context_token: ctx.context_token || "",
      media_path: ctx.MediaPath || "",
      media_type: ctx.MediaType || "",
      external_message_id: ctx.MessageSid || "",
      session_key: ctx.SessionKey || "",
    }),
  });

  const payload = (await response.json().catch(() => ({}))) as Record<string, any>;
  if (!response.ok) {
    const errorMessage =
      payload?.message ||
      payload?.errors?.detail?.[0] ||
      `WHartTest inbound dispatch failed: HTTP ${response.status}`;
    throw new Error(String(errorMessage));
  }

  const reply = String(payload?.data?.reply || "").trim();
  return reply;
}

async function dispatchReplyFromWhartTest(params: {
  ctx: Record<string, unknown>;
  dispatcher: {
    sendFinalReply: (payload: { text: string }) => boolean;
  };
}) {
  const reply = await callWhartTestInbound(params.ctx);
  if (!reply) {
    return buildReplyDispatchResult(0);
  }
  params.dispatcher.sendFinalReply({ text: reply });
  return buildReplyDispatchResult(1);
}

const runtime = {
  version: "2026.3.23",
  channel: {
    commands: {
      shouldComputeCommandAuthorized,
      resolveCommandAuthorizedFromAuthorizers,
    },
    media: {
      saveMediaBuffer: saveSharedMediaBuffer,
    },
    routing: {
      resolveAgentRoute,
    },
    session: {
      resolveStorePath,
      recordInboundSession,
    },
    reply: {
      finalizeInboundContext,
      resolveHumanDelayConfig: () => undefined,
      createReplyDispatcherWithTyping,
      withReplyDispatcher,
      dispatchReplyFromConfig: dispatchReplyFromWhartTest,
    },
  },
};

const pluginApi = {
  id: "wharttest-weixin-host",
  name: "WHartTest Weixin Plugin Host",
  version: "0.1.0",
  description: "WHartTest host adapter for the official Weixin plugin",
  source: "wharttest",
  registrationMode: "full",
  config: hostConfig,
  pluginConfig: {},
  runtime,
  logger,
  registerTool: noop,
  registerHook: noop,
  registerHttpRoute: noop,
  registerChannel: (registration: Record<string, any>) => {
    registeredChannel = registration.plugin || registration;
  },
  registerGatewayMethod: noop,
  registerCli: noop,
  registerService: noop,
  registerProvider: noop,
  registerSpeechProvider: noop,
  registerMediaUnderstandingProvider: noop,
  registerImageGenerationProvider: noop,
  registerWebSearchProvider: noop,
  registerInteractiveHandler: noop,
  onConversationBindingResolved: noop,
  registerCommand: noop,
  registerContextEngine: noop,
  registerMemoryPromptSection: noop,
  resolvePath: (input: string) => path.resolve(input),
  on: noop,
};

await mkdir(sharedDataDir, { recursive: true });
await mkdir(openClawStateDir, { recursive: true });
await mkdir(sessionStoreDir, { recursive: true });
await mkdir(mediaStoreDir, { recursive: true });

await Promise.resolve(weixinPluginEntry.register(pluginApi as never));

if (!registeredChannel) {
  throw new Error("Failed to register official Weixin plugin");
}

function normalizeStatus(
  accountId: string,
  configured: boolean,
  snapshot?: Partial<AccountStatusSnapshot>,
): AccountStatusSnapshot {
  return {
    accountId,
    configured,
    running: Boolean(snapshot?.running),
    lastError: snapshot?.lastError || null,
    lastStartAt: snapshot?.lastStartAt || null,
    lastStopAt: snapshot?.lastStopAt || null,
    lastEventAt: snapshot?.lastEventAt || null,
    lastInboundAt: snapshot?.lastInboundAt || null,
    lastOutboundAt: snapshot?.lastOutboundAt || null,
  };
}

function serializeAccountStatus(accountId: string): AccountStatusSnapshot {
  const normalizedId = normalizeAccountId(accountId);
  const resolved = registeredChannel?.config?.resolveAccount?.(
    hostConfig,
    normalizedId,
  );
  const entry = accountRuntimes.get(normalizedId);
  return normalizeStatus(normalizedId, Boolean(resolved?.configured), entry?.snapshot);
}

async function startAccountMonitor(accountIdInput: string) {
  const accountId = normalizeAccountId(accountIdInput);
  const existing = accountRuntimes.get(accountId);
  if (existing?.snapshot.running) {
    return serializeAccountStatus(accountId);
  }

  const resolvedAccount = registeredChannel?.config?.resolveAccount?.(
    hostConfig,
    accountId,
  );
  if (!resolvedAccount?.configured) {
    throw new Error(
      `Weixin account ${accountId} is not configured. Complete QR login first.`,
    );
  }

  const controller = new AbortController();
  const snapshot = normalizeStatus(accountId, true, {
    running: true,
    lastStartAt: Date.now(),
    lastError: null,
  });

  const entry: AccountRuntimeEntry = {
    accountId,
    controller,
    snapshot,
    promise: Promise.resolve(),
  };
  accountRuntimes.set(accountId, entry);

  entry.promise = Promise.resolve(
    registeredChannel?.gateway?.startAccount?.({
      account: resolvedAccount,
      cfg: hostConfig,
      runtime: {
        log: (message: string) =>
          logger.info(`[${accountId}] ${message}`),
        error: (message: string) =>
          logger.error(`[${accountId}] ${message}`),
      },
      abortSignal: controller.signal,
      setStatus: (next: Partial<AccountStatusSnapshot>) => {
        entry.snapshot = normalizeStatus(accountId, true, {
          ...entry.snapshot,
          ...next,
          running: next.running ?? entry.snapshot.running,
        });
      },
    }),
  )
    .catch((error) => {
      entry.snapshot = normalizeStatus(accountId, true, {
        ...entry.snapshot,
        running: false,
        lastError: String(error),
        lastStopAt: Date.now(),
      });
      logger.error(`monitor failed for ${accountId}:`, error);
    })
    .finally(() => {
      entry.snapshot = normalizeStatus(accountId, true, {
        ...entry.snapshot,
        running: false,
        lastStopAt: entry.snapshot.lastStopAt || Date.now(),
      });
    });

  return serializeAccountStatus(accountId);
}

async function bootstrapAccountIfNeeded(params: {
  accountId: string;
  token?: string;
  baseUrl?: string;
  userId?: string;
}) {
  if (!params.token?.trim()) {
    return;
  }

  saveWeixinAccount(params.accountId, {
    token: params.token.trim(),
    baseUrl: (params.baseUrl || DEFAULT_BASE_URL).trim(),
    userId: params.userId?.trim() || undefined,
  });
  registerWeixinAccountId(params.accountId);
  if (params.userId?.trim()) {
    clearStaleAccountsForUserId(
      params.accountId,
      params.userId.trim(),
      clearContextTokensForAccount,
    );
  }
  await triggerWeixinChannelReload();
}

async function stopAccountMonitor(accountIdInput: string) {
  const accountId = normalizeAccountId(accountIdInput);
  const entry = accountRuntimes.get(accountId);
  if (!entry) {
    return serializeAccountStatus(accountId);
  }

  entry.controller.abort();
  try {
    await Promise.race([
      entry.promise,
      new Promise((resolve) => setTimeout(resolve, 2000)),
    ]);
  } catch {
    noop();
  }

  entry.snapshot = normalizeStatus(accountId, true, {
    ...entry.snapshot,
    running: false,
    lastStopAt: Date.now(),
  });
  return serializeAccountStatus(accountId);
}

async function syncLoginSession(body: Record<string, any>) {
  const apiBaseUrl = String(body.baseUrl || DEFAULT_BASE_URL);
  const sessionKey = String(body.sessionKey || "").trim();
  if (!sessionKey) {
    throw new Error("sessionKey is required");
  }

  const result = await waitForWeixinLogin({
    sessionKey,
    apiBaseUrl,
    timeoutMs: Number(body.timeoutMs || 1000),
    verbose: false,
    botType: DEFAULT_ILINK_BOT_TYPE,
  });

  const normalizedAccountId = result.accountId
    ? normalizeAccountId(result.accountId)
    : "";

  if (
    result.connected &&
    result.accountId &&
    result.botToken
  ) {
    saveWeixinAccount(normalizedAccountId, {
      token: result.botToken,
      baseUrl: result.baseUrl,
      userId: result.userId,
    });
    registerWeixinAccountId(normalizedAccountId);
    if (result.userId) {
      clearStaleAccountsForUserId(
        normalizedAccountId,
        result.userId,
        clearContextTokensForAccount,
      );
    }
    await triggerWeixinChannelReload();
  }

  return {
    connected: result.connected,
    message: result.message,
    rawAccountId: result.accountId || "",
    accountId: normalizedAccountId,
    botToken: result.botToken || "",
    baseUrl: result.baseUrl || apiBaseUrl,
    userId: result.userId || "",
  };
}

async function startLogin(body: Record<string, any>) {
  const apiBaseUrl = String(body.baseUrl || DEFAULT_BASE_URL);
  const accountId = body.accountId ? String(body.accountId) : undefined;
  const result = await startWeixinLoginWithQr({
    apiBaseUrl,
    accountId,
    verbose: false,
    force: Boolean(body.force),
    timeoutMs: body.timeoutMs ? Number(body.timeoutMs) : undefined,
    botType: DEFAULT_ILINK_BOT_TYPE,
  });

  return {
    sessionKey: result.sessionKey,
    qrDataUrl: result.qrcodeUrl || "",
    message: result.message,
  };
}

function listAccountStatuses() {
  const ids = new Set<string>([
    ...listWeixinAccountIds(hostConfig as never),
    ...accountRuntimes.keys(),
  ]);
  return Array.from(ids).map((accountId) => serializeAccountStatus(accountId));
}

async function readJsonBody(req: Parameters<typeof createServer>[0]) {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  if (chunks.length === 0) {
    return {};
  }
  const raw = Buffer.concat(chunks).toString("utf-8");
  return (JSON.parse(raw) || {}) as Record<string, any>;
}

function sendJson(
  res: Parameters<Parameters<typeof createServer>[0]>[1],
  statusCode: number,
  payload: JsonObject,
) {
  res.statusCode = statusCode;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify(payload));
}

const server = createServer(async (req, res) => {
  const method = req.method || "GET";
  const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);

  try {
    if (method === "GET" && url.pathname === "/health") {
      sendJson(res, 200, {
        ok: true,
        data: {
          status: "ok",
          backendBaseUrl,
          openClawStateDir,
        },
      });
      return;
    }

    if (method === "POST" && url.pathname === "/api/login/start") {
      const body = await readJsonBody(req);
      sendJson(res, 200, { ok: true, data: await startLogin(body) });
      return;
    }

    if (method === "POST" && url.pathname === "/api/login/status") {
      const body = await readJsonBody(req);
      sendJson(res, 200, { ok: true, data: await syncLoginSession(body) });
      return;
    }

    if (method === "GET" && url.pathname === "/api/accounts/status") {
      sendJson(res, 200, { ok: true, data: listAccountStatuses() });
      return;
    }

    if (method === "POST" && url.pathname === "/api/accounts/start") {
      const body = await readJsonBody(req);
      const normalizedAccountId = normalizeAccountId(String(body.accountId || ""));
      let resolvedAccount = registeredChannel?.config?.resolveAccount?.(
        hostConfig,
        normalizedAccountId,
      );
      if (!resolvedAccount?.configured) {
        await bootstrapAccountIfNeeded({
          accountId: normalizedAccountId,
          token: body.token ? String(body.token) : undefined,
          baseUrl: body.baseUrl ? String(body.baseUrl) : undefined,
          userId: body.userId ? String(body.userId) : undefined,
        });
      }
      sendJson(res, 200, {
        ok: true,
        data: await startAccountMonitor(normalizedAccountId),
      });
      return;
    }

    if (method === "POST" && url.pathname === "/api/accounts/stop") {
      const body = await readJsonBody(req);
      sendJson(res, 200, {
        ok: true,
        data: await stopAccountMonitor(String(body.accountId || "")),
      });
      return;
    }

    sendJson(res, 404, {
      ok: false,
      error: `Route not found: ${method} ${url.pathname}`,
    });
  } catch (error) {
    logger.error(`request failed for ${method} ${url.pathname}:`, error);
    sendJson(res, 500, {
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

server.listen(port, host, () => {
  logger.info(
    `official Weixin plugin host listening on http://${host}:${port}`,
  );
});
