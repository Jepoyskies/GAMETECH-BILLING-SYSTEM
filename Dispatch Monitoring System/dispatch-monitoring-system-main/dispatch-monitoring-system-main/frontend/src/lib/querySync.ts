import { useEffect } from "react";
import { subscribeToRoom, unsubscribeFromRoom } from "./socket";

export type QueryKey = string | readonly unknown[];

type QueryCallback = () => void | Promise<void>;

export const listeners = new Map<string, Set<QueryCallback>>();

function normalizeKey(key: QueryKey): string {
  if (typeof key === "string") return key;
  return key.map((value) => {
    if (value === null || value === undefined) return "null";
    if (typeof value === "string") return value;
    if (typeof value === "number" || typeof value === "boolean") return String(value);
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }).join("::");
}

export function registerQuery(key: QueryKey, callback: QueryCallback) {
  const entryKey = normalizeKey(key);
  const callbacks = listeners.get(entryKey) ?? new Set<QueryCallback>();
  callbacks.add(callback);
  listeners.set(entryKey, callbacks);

  return () => unregisterQuery(key, callback);
}

export function unregisterQuery(key: QueryKey, callback: QueryCallback) {
  const entryKey = normalizeKey(key);
  const callbacks = listeners.get(entryKey);
  if (!callbacks) return;
  callbacks.delete(callback);
  if (callbacks.size === 0) {
    listeners.delete(entryKey);
  }
}

export function invalidateQuery(key: QueryKey) {
  const entryKey = normalizeKey(key);
  const callbacks = listeners.get(entryKey);
  if (!callbacks) return;

  for (const callback of Array.from(callbacks)) {
    void callback();
  }
}

export function invalidateAllQueries() {
  for (const callbacks of Array.from(listeners.values())) {
    for (const callback of Array.from(callbacks)) {
      void callback();
    }
  }
}

export function useQuerySubscription(key: QueryKey, callback: QueryCallback) {
  const rooms = resolveRoomsForKey(key);

  useEffect(() => {
    const unregister = registerQuery(key, callback);
    for (const room of rooms) {
      subscribeToRoom(room);
    }

    return () => {
      unregister();
      for (const room of rooms) {
        unsubscribeFromRoom(room);
      }
    };
  }, [key, callback, rooms]);
}

function resolveRoomsForKey(key: QueryKey): string[] {
  const normalized = typeof key === "string" ? key : key.join("::");

  if (normalized.startsWith("/dashboard/")) {
    const rooms: string[] = ["monitoring", "dispatches", "technicians", "teams", "accounts", "config-options"];
    if (normalized === "/dashboard/targets" || normalized === "monthlyTargets") {
      rooms.push("dashboard");
    }
    return rooms;
  }

  if (normalized === "dispatches" || normalized === "/dispatches" || normalized.startsWith("/dispatches?")) return ["dispatches"];
  if (normalized === "monitoring" || normalized === "/monitoring" || normalized.startsWith("/monitoring?")) return ["monitoring"];
  if (normalized === "customers" || normalized === "/customers" || normalized.startsWith("/customers?")) return ["customers"];
  if (normalized === "technicians" || normalized === "/technicians") return ["technicians"];
  if (normalized === "teams" || normalized === "/teams") return ["teams"];
  if (normalized === "configOptions" || normalized === "/config-options" || normalized.startsWith("/config-options?")) return ["config-options"];
  if (normalized === "accounts" || normalized === "/auth/accounts") return ["accounts"];
  if (normalized === "auditLog" || normalized === "/audit" || normalized.startsWith("/audit?")) return ["audit"];
  if (normalized === "monthlyTargets" || normalized === "/dashboard/targets") return ["dashboard"];
  return [];
}
