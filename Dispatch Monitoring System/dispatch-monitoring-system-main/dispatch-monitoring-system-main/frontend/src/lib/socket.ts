import { io, Socket } from "socket.io-client";
import { invalidateQuery, listeners } from "./querySync";

let socket: Socket | null = null;
let listenersAttached = false;

const EVENT_NAMES = [
  "csr:changed",
  "monitoringRecord:changed",
  "dispatch:changed",
  "customer:changed",
  "technician:changed",
  "team:changed",
  "configOption:changed",
  "monthlyTarget:changed",
] as const;

const ROOM_QUERY_KEYS: Record<string, string[]> = {
  dispatches: ["dispatches", "/dispatches"],
  monitoring: ["monitoring", "/monitoring"],
  customers: ["customers", "/customers"],
  technicians: ["technicians", "/technicians"],
  teams: ["teams", "/teams"],
  "config-options": ["configOptions", "/config-options"],
  accounts: ["accounts", "/auth/accounts"],
  dashboard: ["monthlyTargets", "/dashboard/targets"],
  audit: ["auditLog", "/audit"],
};

const DASHBOARD_ROOMS = new Set(["monitoring", "dispatches", "dashboard", "technicians", "teams", "accounts", "config-options"]);

function invalidateRoomQueries(room: string) {
  for (const key of ROOM_QUERY_KEYS[room] ?? []) {
    invalidateQuery(key);
  }
  if (DASHBOARD_ROOMS.has(room)) {
    for (const [key, callbacks] of listeners.entries()) {
      if (key.startsWith("/dashboard/")) {
        for (const cb of Array.from(callbacks)) { void cb(); }
      }
    }
  }
}

function attachListeners() {
  if (!socket || listenersAttached) return;

  for (const eventName of EVENT_NAMES) {
    socket.on(eventName, () => {
      const room = roomForEvent(eventName);
      if (room) {
        invalidateRoomQueries(room);
      }
    });
  }

  socket.on("audit:new", () => {
    invalidateRoomQueries("audit");
  });

  listenersAttached = true;
}

function roomForEvent(eventName: string) {
  switch (eventName) {
    case "csr:changed":
      return "accounts";
    case "monitoringRecord:changed":
      return "monitoring";
    case "dispatch:changed":
      return "dispatches";
    case "customer:changed":
      return "customers";
    case "technician:changed":
      return "technicians";
    case "team:changed":
      return "teams";
    case "configOption:changed":
      return "config-options";
    case "monthlyTarget:changed":
      return "dashboard";
    default:
      return null;
  }
}

export function connectSocket() {
  if (socket?.connected) return socket;

  const url = import.meta.env.VITE_WS_URL || window.location.origin;

  socket = io(url, {
    path: "/socket.io",
    withCredentials: true,
    transports: ["websocket", "polling"],
  });

  attachListeners();
  return socket;
}

export function disconnectSocket() {
  if (!socket) return;
  socket.disconnect();
  socket = null;
  listenersAttached = false;
}

export function subscribeToRoom(room: string) {
  if (!socket || !room) return;
  socket.emit("subscribe", room);
}

export function unsubscribeFromRoom(room: string) {
  if (!socket || !room) return;
  socket.emit("unsubscribe", room);
}

export function getSocket() {
  return socket;
}
