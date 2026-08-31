import type { Server as HttpServer } from "http";
import { Server as SocketIOServer, type Socket } from "socket.io";
import type { Role } from "@prisma/client";
import { AUTH_COOKIE, verifyToken } from "./auth";
import { resolveCorsOrigins } from "./cors";

const EVENT_ROOM_MAP: Record<string, string> = {
  "csr:changed": "accounts",
  "monitoringRecord:changed": "monitoring",
  "dispatch:changed": "dispatches",
  "customer:changed": "customers",
  "technician:changed": "technicians",
  "team:changed": "teams",
  "configOption:changed": "config-options",
  "monthlyTarget:changed": "dashboard",
};

interface SocketUser {
  id: number;
  role: Role;
}

let io: SocketIOServer | null = null;

function parseCookies(cookieHeader: string): Record<string, string> {
  const cookies: Record<string, string> = {};
  if (!cookieHeader) return cookies;

  for (const part of cookieHeader.split(";")) {
    const [rawKey, ...rawValue] = part.trim().split("=");
    if (!rawKey) continue;
    const key = decodeURIComponent(rawKey);
    const value = decodeURIComponent(rawValue.join("=") || "");
    cookies[key] = value;
  }

  return cookies;
}

function getSocketToken(socket: Socket): string | null {
  const cookies = parseCookies(socket.handshake.headers.cookie ?? "");
  const token = cookies[AUTH_COOKIE] ?? (socket.handshake.auth?.token as string | undefined);
  return typeof token === "string" && token ? token : null;
}

export function initializeSocketServer(httpServer: HttpServer) {
  if (io) return io;

  io = new SocketIOServer(httpServer, {
    cors: {
      origin: resolveCorsOrigins(),
      credentials: true,
      methods: ["GET", "POST"],
    },
  });

  io.use((socket, next) => {
    const token = getSocketToken(socket);
    if (!token) {
      return next(new Error("Unauthorized"));
    }

    try {
      const payload = verifyToken(token);
      socket.data.user = {
        id: payload.sub,
        role: payload.role,
      } as SocketUser;
      next();
    } catch {
      next(new Error("Unauthorized"));
    }
  });

  io.on("connection", (socket) => {
    socket.on("subscribe", (room: unknown) => {
      if (typeof room === "string" && room.trim()) {
        void socket.join(room.trim());
      }
    });

    socket.on("unsubscribe", (room: unknown) => {
      if (typeof room === "string" && room.trim()) {
        void socket.leave(room.trim());
      }
    });
  });

  return io;
}

export function emitAuditChanged() {
  io?.to("audit").emit("audit:new");
}

export function emitEntityChanged(event: string, id?: number) {
  const room = EVENT_ROOM_MAP[event];
  const payload = id === undefined ? undefined : { id };

  if (room) {
    if (payload === undefined) {
      io?.to(room).emit(event);
    } else {
      io?.to(room).emit(event, payload);
    }
    return;
  }

  if (payload === undefined) {
    io?.emit(event);
    return;
  }

  io?.emit(event, payload);
}

export function emitEntityChangedToRoom(event: string, room: string, id?: number) {
  if (id === undefined) {
    io?.to(room).emit(event);
    return;
  }

  io?.to(room).emit(event, { id });
}

export function getSocketServer() {
  return io;
}
