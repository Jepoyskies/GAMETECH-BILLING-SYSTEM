import { randomBytes } from "crypto";
import pinoHttp from "pino-http";
import logger from "../lib/logger";

export const requestLogger = pinoHttp({
  logger,
  genReqId: () => randomBytes(6).toString("hex"),
  customLogLevel: (_req, res, err) => {
    if (res.statusCode >= 500 || err) return "error";
    if (res.statusCode >= 400) return "warn";
    return "info";
  },
  customSuccessMessage: (req) => {
    return `${req.method} ${req.url}`;
  },
  customErrorMessage: (_req, res, err) => {
    return `Request error: ${err?.message ?? "unknown error"}`;
  },
  customAttributeKeys: {
    req: "req",
    res: "res",
    err: "err",
    responseTime: "responseTime",
  },
  customProps: (req) => {
    const user = (req as unknown as Record<string, unknown>).user as
      | { id?: number; role?: string; name?: string }
      | undefined;
    if (user?.id) {
      return { user: { id: user.id, role: user.role, name: user.name } };
    }
    return {};
  },
});

export { logger };