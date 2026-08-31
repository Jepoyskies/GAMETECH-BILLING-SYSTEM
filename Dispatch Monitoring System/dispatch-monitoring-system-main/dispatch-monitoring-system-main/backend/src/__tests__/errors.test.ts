import { describe, it, expect } from "vitest";
import {
  AppError,
  NotFoundError,
  ValidationError,
  ConflictError,
  ForbiddenError,
  BadRequestError,
} from "../lib/errors";

describe("AppError", () => {
  it("creates an error with message and status code", () => {
    const err = new AppError("Something went wrong", 500);
    expect(err).toBeInstanceOf(Error);
    expect(err.message).toBe("Something went wrong");
    expect(err.statusCode).toBe(500);
    expect(err.isOperational).toBe(true);
  });

  it("sets isOperational to false when specified", () => {
    const err = new AppError("Internal", 500, false);
    expect(err.isOperational).toBe(false);
  });
});

describe("NotFoundError", () => {
  it("creates a 404 error with resource name", () => {
    const err = new NotFoundError("Dispatch");
    expect(err).toBeInstanceOf(AppError);
    expect(err.statusCode).toBe(404);
    expect(err.message).toBe("Dispatch not found");
  });
});

describe("ValidationError", () => {
  it("creates a 400 error with custom message", () => {
    const err = new ValidationError("Invalid ID");
    expect(err).toBeInstanceOf(AppError);
    expect(err.statusCode).toBe(400);
    expect(err.message).toBe("Invalid ID");
  });
});

describe("ConflictError", () => {
  it("creates a 409 error with message", () => {
    const err = new ConflictError("Duplicate entry");
    expect(err).toBeInstanceOf(AppError);
    expect(err.statusCode).toBe(409);
    expect(err.message).toBe("Duplicate entry");
  });
});

describe("ForbiddenError", () => {
  it("creates a 403 error with message", () => {
    const err = new ForbiddenError("Access denied");
    expect(err).toBeInstanceOf(AppError);
    expect(err.statusCode).toBe(403);
    expect(err.message).toBe("Access denied");
  });
});

describe("BadRequestError", () => {
  it("creates a 400 error with message", () => {
    const err = new BadRequestError("Invalid request body");
    expect(err).toBeInstanceOf(AppError);
    expect(err.statusCode).toBe(400);
    expect(err.message).toBe("Invalid request body");
  });
});
