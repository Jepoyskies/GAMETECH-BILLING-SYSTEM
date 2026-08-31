BigInt.prototype.toJSON = function (): number {
  return Number(this);
};

import "express-async-errors";
import express from "express";
import { createServer } from "http";
import path from "path";
import helmet from "helmet";
import cors from "cors";
import compression from "compression";
import { requestLogger } from "./middleware/requestLogger";
import logger from "./lib/logger";
import rateLimit from "express-rate-limit";
import cookieParser from "cookie-parser";

import authRoutes from "./routes/auth";
import auditRoutes from "./routes/audit";
import dashboardRoutes from "./routes/dashboard";
import dispatchRoutes from "./routes/dispatches";
import monitoringRoutes from "./routes/monitoring";
import csrRoutes from "./routes/csr";
import customerRoutes from "./routes/customer";
import technicianRoutes from "./routes/technician";
import teamRoutes from "./routes/team";
import configOptionRoutes from "./routes/configOption";
import backupRoutes from "./routes/backup";
import { ensureAllHardcodedOptions } from "./controllers/configOption.controller";
import { errorHandler } from "./middleware/errorHandler";
import { requireAuth } from "./middleware/auth";
import prisma from "./lib/prisma";
import { initializeSocketServer } from "./lib/socket";
import { resolveCorsOrigins } from "./lib/cors";
import { startScheduler } from "./lib/scheduler";

const app = express();
const PORT = process.env.PORT ?? 5502;

// ── Security headers ──────────────────────────────────────────────────────────
// Security headers — these are relaxed for LAN/mini‑PC deployment.
// If deploying to the public internet, re‑enable the options below
app.use(helmet({
  crossOriginOpenerPolicy: false,
  crossOriginEmbedderPolicy: false,
  contentSecurityPolicy: false,
}));

// ── CORS — configurable via CORS_ORIGINS env (comma-separated) ──────────────
app.use(
  cors({
    origin: resolveCorsOrigins(),
    methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allowedHeaders: ["Content-Type", "Authorization"],
    credentials: true,
  })
);

// ── Compression ───────────────────────────────────────────────────────────────
app.use(compression());

// ── Body parsing ──────────────────────────────────────────────────────────────
app.use(express.json({ limit: "1mb" }));
app.use(express.urlencoded({ extended: true, limit: "1mb" }));

// ── Cookie parsing (session token lives in an httpOnly cookie) ────────────────
app.use(cookieParser());

// ── Request logging ───────────────────────────────────────────────────────────
app.use(requestLogger);

// ── Rate limiting — prevents runaway loops or scripts hammering the API ───────
const limiter = rateLimit({
  windowMs: 1 * 60 * 1000,
  max: 500,
  standardHeaders: true,
  legacyHeaders: false,
  message: { success: false, error: "Too many requests, slow down." },
});
app.use("/api", limiter);

// ── Health check ──────────────────────────────────────────────────────────────
app.get("/health", async (_req, res) => {
  try {
    await prisma.$queryRaw`SELECT 1`;
    res.json({ success: true, status: "ok", db: "connected" });
  } catch {
    res.status(503).json({ success: false, status: "error", db: "disconnected" });
  }
});

// ── Public auth routes (login, setup, logout) ────────────────────────────────
app.use("/api/auth", authRoutes);

// ── Protected routes — every data route requires a valid session ─────────────
app.use("/api/dashboard", requireAuth, dashboardRoutes);
app.use("/api/dispatches", requireAuth, dispatchRoutes);
app.use("/api/monitoring", requireAuth, monitoringRoutes);
app.use("/api/csr", requireAuth, csrRoutes);
app.use("/api/customers", requireAuth, customerRoutes);
app.use("/api/technicians", requireAuth, technicianRoutes);
app.use("/api/teams", requireAuth, teamRoutes);
app.use("/api/config-options", requireAuth, configOptionRoutes);
app.use("/api/audit", auditRoutes);
app.use("/api/backups", backupRoutes);

// ── Serve frontend static files in production ──────────────────────────────
if (process.env.NODE_ENV === "production") {
  const frontendDist = path.join(__dirname, "../../../frontend/dist");
  app.use(express.static(frontendDist));
}

// ── 404 handler (API only) ─────────────────────────────────────────────────────
app.use((_req, res) => {
  if (_req.path.startsWith("/api")) {
    res.status(404).json({ success: false, error: "Route not found" });
  } else if (process.env.NODE_ENV === "production") {
    // SPA fallback — let React Router handle frontend routes
    res.sendFile(path.join(__dirname, "../../../frontend/dist", "index.html"));
  } else {
    res.status(404).json({ success: false, error: "Not found" });
  }
});

// ── Global error handler (must be last) ──────────────────────────────────────
app.use(errorHandler);

// ── Start server ──────────────────────────────────────────────────────────────
const server = createServer(app);
initializeSocketServer(server);

ensureAllHardcodedOptions().catch((err) => {
  logger.error(err, "Failed to ensure hardcoded options");
});

server.listen(PORT, () => {
  logger.info(`Server running on http://localhost:${PORT}`);
  logger.info(`Dashboard: http://localhost:${PORT}/api/dashboard/stats`);
  logger.info(`Health:    http://localhost:${PORT}/health`);

  // Start backup scheduler
  startScheduler();
});

// ── Graceful shutdown ─────────────────────────────────────────────────────────
// Gives in-flight requests time to finish before closing DB connections.
// PM2 sends SIGINT on restart — this prevents data corruption mid-write.
async function shutdown(signal: string) {
  logger.info(`${signal} received. Shutting down gracefully...`);
  server.close(async () => {
    logger.info("HTTP server closed");
    await prisma.$disconnect();
    logger.info("Database disconnected");
    process.exit(0);
  });

  // Force exit after 10 seconds if graceful shutdown hangs
  setTimeout(() => {
    logger.error("Forced shutdown after timeout");
    process.exit(1);
  }, 10_000);
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));

// ── Catch unhandled promise rejections ────────────────────────────────────────
// Prevents the process from crashing on uncaught async errors
process.on("unhandledRejection", (reason) => {
  logger.error({ err: reason }, "Unhandled rejection");
  // Don't exit — log and continue. PM2 will restart if truly broken.
});

process.on("uncaughtException", (err) => {
  logger.error(err, "Uncaught exception");
  // Uncaught exceptions are dangerous — exit and let PM2 restart
  process.exit(1);
});

export default app;
