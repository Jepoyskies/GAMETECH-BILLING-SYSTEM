import { NextFunction, Request, Response } from "express";
import { ZodError } from "zod";
import { AppError } from "../lib/errors";
import { Prisma } from "@prisma/client";
import logger from "../lib/logger";

export function errorHandler(
  err: unknown,
  req: Request,
  res: Response,
  _next: NextFunction
): void {
  // ── Zod validation errors ──────────────────────────────────────────────────
  if (err instanceof ZodError) {
    const messages = err.errors.map((e) => `${e.path.join(".")}: ${e.message}`);
    res.status(400).json({
      success: false,
      error: "Validation failed",
      details: messages,
    });
    return;
  }

  // ── Known operational errors (NotFoundError, ValidationError, etc.) ────────
  if (err instanceof AppError) {
    res.status(err.statusCode).json({
      success: false,
      error: err.message,
    });
    return;
  }

  // ── Prisma known errors ────────────────────────────────────────────────────
  if (err instanceof Prisma.PrismaClientKnownRequestError) {
    if (err.code === "P2002") {
      const target = err.meta?.target as string | undefined;
      const fieldLabel = target?.includes("account_number") ? "Account number" : "A record";
      res.status(409).json({
        success: false,
        error: `${fieldLabel} already exists`,
        field: target,
      });
      return;
    }
    if (err.code === "P2025") {
      res.status(404).json({
        success: false,
        error: "Record not found",
      });
      return;
    }
    if (err.code === "P2003") {
      res.status(400).json({
        success: false,
        error: "Related record not found",
      });
      return;
    }
  }

  if (
    err instanceof Prisma.PrismaClientValidationError ||
    err instanceof Prisma.PrismaClientUnknownRequestError ||
    err instanceof Prisma.PrismaClientRustPanicError
  ) {
    logger.error({ err: err.message }, "Prisma query error");
    res.status(500).json({
      success: false,
      error: "Database query failed. Please try again shortly.",
    });
    return;
  }

  // ── Prisma connection errors ───────────────────────────────────────────────
  if (err instanceof Prisma.PrismaClientInitializationError) {
    logger.error({ err: err.message }, "Database connection failed");
    res.status(503).json({
      success: false,
      error: "Database unavailable. Please try again shortly.",
    });
    return;
  }

  // ── Unknown/unexpected errors ──────────────────────────────────────────────
  logger.error({ err }, "Unhandled error");
  res.status(500).json({
    success: false,
    error: "An unexpected error occurred",
  });
}
