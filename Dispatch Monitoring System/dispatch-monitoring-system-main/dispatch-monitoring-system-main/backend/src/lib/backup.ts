import { execFile } from "child_process";
import { promisify } from "util";
import path from "path";
import fs from "fs/promises";
import fsSync from "fs";
import os from "os";
import crypto from "crypto";
import { Prisma } from "@prisma/client";
import prisma from "./prisma";
import logger from "./logger";

const execFileAsync = promisify(execFile);

const HOURLY_KEEP = 24;
const DAILY_KEEP = 7;
const PRESAFETY_KEEP = 3;

const BACKUP_TABLE = "BackupHistory";
const BACKUP_SEQUENCE = "BackupHistory_id_seq";
const CONFIG_TABLE = "AppConfig";
const CONFIG_SEQUENCE = "AppConfig_id_seq";
const PG_DUMP = process.env.PG_DUMP_PATH || "pg_dump";
const PG_RESTORE = process.env.PG_RESTORE_PATH || "pg_restore";
const PSQL = process.env.PSQL_PATH || "psql";

interface DbConnection {
  host: string;
  port: number;
  database: string;
  user: string;
  password: string;
}

function parseDbUrl(url: string): DbConnection {
  const u = new URL(url);
  return {
    host: u.hostname,
    port: Number(u.port) || 5432,
    database: u.pathname.replace(/^\//, ""),
    user: decodeURIComponent(u.username),
    password: decodeURIComponent(u.password),
  };
}

function pgDumpArgs(conn: DbConnection, excludeTables: string[], excludeSeqs: string[], filePath: string): string[] {
  const args = [
    "-h", conn.host,
    "-p", String(conn.port),
    "-U", conn.user,
    "-d", conn.database,
    "-Fc",
  ];
  for (const t of excludeTables) args.push("--exclude-table", t);
  for (const s of excludeSeqs) args.push("--exclude-table", s);
  args.push("-f", filePath);
  return args;
}

function pgRestoreArgs(conn: DbConnection, filePath: string): string[] {
  return [
    "-h", conn.host,
    "-p", String(conn.port),
    "-U", conn.user,
    "-d", conn.database,
    "--clean",
    "--if-exists",
    "--no-owner",
    "--no-privileges",
    filePath,
  ];
}

/**
 * Rotates the JWT_SECRET in the backend .env file and restarts PM2.
 * This force-logs-out all users by invalidating existing tokens.
 */
async function rotateJwtSecretAndRestart(): Promise<void> {
  const envPath = path.resolve(__dirname, "../../.env");
  const newSecret = crypto.randomBytes(64).toString("hex");

  try {
    let envContent = await fs.readFile(envPath, "utf-8");

    if (envContent.includes("JWT_SECRET=")) {
      envContent = envContent.replace(
        /JWT_SECRET=.*/,
        `JWT_SECRET="${newSecret}"`
      );
    } else {
      envContent += `\nJWT_SECRET="${newSecret}"\n`;
    }

    await fs.writeFile(envPath, envContent, "utf-8");
    process.env.JWT_SECRET = newSecret;
    logger.info("JWT_SECRET rotated after database restore");

    try {
      await execFileAsync("pm2", ["restart", "dispatch-backend"]);
      logger.info("PM2 process restarted after JWT rotation");
    } catch (pm2Err) {
      logger.warn({ err: pm2Err }, "PM2 restart failed — users must restart server manually");
    }
  } catch (err) {
    logger.error({ err }, "Failed to rotate JWT_SECRET — sessions may still be valid");
  }
}

function connection(): DbConnection {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL is not set");
  return parseDbUrl(url);
}

async function getBackupDir(override?: string): Promise<string> {
  if (override && override.trim()) return override.trim();
  const persisted = await getPersistedBackupDir();
  if (persisted) return persisted;
  return process.env.BACKUP_DIR || path.join(process.cwd(), "backups");
}

async function getPersistedBackupDir(): Promise<string | null> {
  try {
    const row = await prisma.appConfig.findUnique({ where: { key: "backup_directory" } });
    return row?.value?.trim() || null;
  } catch {
    return null;
  }
}

function fileName(type: "full" | "hourly", prefixOverride?: string): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const date = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  const time = `${pad(now.getHours())}-${pad(now.getMinutes())}-${pad(now.getSeconds())}`;
  const prefix = prefixOverride ?? (type === "full" ? "full" : "hourly");
  return `${prefix}_${date}_${time}.dump`;
}

function qualifiedTableName(table: string): string {
  return `"${table}"`;
}

type BackupTypeEnum = "FULL" | "HOURLY" | "PRESAFETY" | "RESTORE";
type BackupTriggerEnum = "SCHEDULED" | "MANUAL" | "PRESAFETY" | "RESTORE";

export async function createBackup(
  backupType: BackupTypeEnum,
  trigger: BackupTriggerEnum,
  directoryOverride?: string,
  filenamePrefix?: string,
): Promise<{ success: true; historyId: number; filename: string; fileSize: number } | { success: false; error: string }> {
  const conn = connection();
  const dir = await getBackupDir(directoryOverride);
  const typeKey = backupType === "FULL" ? "full" : backupType === "HOURLY" ? "hourly" : "full";
  const filename = fileName(typeKey, filenamePrefix);
  const filePath = path.join(dir, filename);

  try {
    await fs.mkdir(dir, { recursive: true });
  } catch (err) {
    return { success: false, error: `Failed to create backup directory: ${err}` };
  }

  try {
    const args = pgDumpArgs(
      conn,
      [qualifiedTableName(BACKUP_TABLE), qualifiedTableName(CONFIG_TABLE)],
      [qualifiedTableName(BACKUP_SEQUENCE), qualifiedTableName(CONFIG_SEQUENCE)],
      filePath,
    );
    const env = { ...process.env, PGPASSWORD: conn.password };
    await execFileAsync(PG_DUMP, args, { env, timeout: 300_000 });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    try { await fs.unlink(filePath); } catch { /* ignore */ }
    await logHistory(backupType, trigger, "FAILED", filename, dir, msg);
    return { success: false, error: msg };
  }

  let fileSize = 0;
  try {
    const stat = await fs.stat(filePath);
    fileSize = stat.size;
    if (fileSize === 0) throw new Error("Backup file is empty (0 bytes)");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    try { await fs.unlink(filePath); } catch { /* ignore */ }
    await logHistory(backupType, trigger, "FAILED", filename, dir, msg);
    return { success: false, error: msg };
  }

  const history = await logHistory(backupType, trigger, "SUCCESS", filename, dir, undefined, fileSize);

  if (backupType === "FULL" || backupType === "HOURLY" || backupType === "PRESAFETY") {
    try {
      await rotateBackups(backupType, dir);
    } catch (err) {
      logger.error({ err, backupType }, `Rotation failed for ${backupType} backups`);
    }
  }

  return { success: true, historyId: history.id, filename, fileSize: Number(fileSize) };
}

export async function restoreBackup(
  historyId: number,
  adminId: number,
): Promise<{ success: true } | { success: false; error: string }> {
  await syncBackupHistorySequence();

  const history = await prisma.backupHistory.findUnique({ where: { id: historyId } });
  if (!history) {
    return { success: false, error: "Backup history entry not found" };
  }

  const filePath = path.join(history.directory, history.filename);

  try {
    await fs.access(filePath);
  } catch {
    return { success: false, error: `Backup file not found at ${filePath}` };
  }

  let savedRows: Array<Record<string, unknown>> = [];
  try {
    savedRows = (await prisma.backupHistory.findMany({
      orderBy: { id: "asc" },
    })) as unknown as Array<Record<string, unknown>>;

    await prisma.$executeRawUnsafe(`DROP TABLE IF EXISTS "${BACKUP_TABLE}" CASCADE`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return { success: false, error: `Failed to save/drop BackupHistory: ${msg}` };
  }

  const conn = connection();

  try {
    const args = pgRestoreArgs(conn, filePath);
    const env = { ...process.env, PGPASSWORD: conn.password };
    await execFileAsync(PG_RESTORE, args, { env, timeout: 600_000 });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    try {
      await recreateBackupHistoryTable();
      for (const row of savedRows) {
        await prisma.backupHistory.create({ data: row as never });
      }
      await syncBackupHistorySequence();
      await prisma.backupHistory.create({
        data: {
          backup_type: "RESTORE",
          trigger_source: "RESTORE",
          status: "FAILED",
          filename: `RESTORE_${history.filename}`,
          directory: history.directory,
          error_message: `Restore of ${history.filename} failed: ${msg}`,
          restored_from_id: historyId,
          restored_by_id: adminId,
        },
      });
    } catch { /* best-effort */ }
    return { success: false, error: msg };
  }

  try {
    await recreateBackupHistoryTable();
    for (const row of savedRows) {
      await prisma.backupHistory.create({ data: row as never });
    }
    await syncBackupHistorySequence();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return { success: false, error: `Restore succeeded but failed to re-create BackupHistory: ${msg}` };
  }

  try {
    await resetAllSequences(conn);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.error({ err: msg }, "Sequence reset failed after restore");
  }

  await prisma.backupHistory.create({
    data: {
      backup_type: "RESTORE",
      trigger_source: "RESTORE",
      status: "SUCCESS",
      filename: `RESTORED_${history.filename}`,
      directory: history.directory,
      restored_from_id: historyId,
      restored_by_id: adminId,
    },
  });

  await rotateJwtSecretAndRestart();

  return { success: true };
}

export async function validateImportFile(
  filePath: string,
): Promise<{ success: true; tempId: string } | { success: false; error: string }> {
  try {
    const stat = await fs.stat(filePath);
    if (stat.size === 0) {
      return { success: false, error: "The selected file is empty (0 bytes)." };
    }

    if (stat.size > 500 * 1024 * 1024) {
      return { success: false, error: "File exceeds the 500 MB size limit." };
    }

    const ext = path.extname(filePath).toLowerCase();
    if (ext !== ".dump") {
      return {
        success: false,
        error: `Unsupported file extension "${ext}". Only PostgreSQL custom-format dump files (.dump) produced by pg_dump -Fc are accepted.`,
      };
    }

    const fd = await fs.open(filePath, "r");
    const buf = Buffer.alloc(5);
    await fd.read(buf, 0, 5, 0);
    await fd.close();

    const magic = buf.toString("utf8");
    if (magic !== "PGDMP") {
      return {
        success: false,
        error: "The file is not a valid PostgreSQL custom-format dump (expected magic bytes 'PGDMP'). Only .dump files produced by pg_dump -Fc are supported.",
      };
    }

    let dumpTables: string[];
    try {
      dumpTables = await listDumpTables(filePath);
    } catch (err) {
      return {
        success: false,
        error: `Cannot read the dump file — it may be corrupted: ${err instanceof Error ? err.message : String(err)}`,
      };
    }

    if (dumpTables.length === 0) {
      return { success: false, error: "The dump file contains no tables." };
    }

    let dbTables: string[];
    try {
      const rows: Array<{ tablename: string }> = await prisma.$queryRawUnsafe(
        `SELECT tablename FROM pg_tables
         WHERE schemaname = 'public'
           AND tablename != '_prisma_migrations'
           AND tablename != 'BackupHistory'
           AND tablename != 'AppConfig'
         ORDER BY tablename`,
      );
      dbTables = rows.map((r) => r.tablename);
    } catch {
      return { success: false, error: "Could not query current database schema for compatibility check." };
    }

    if (dbTables.length === 0) {
      return { success: false, error: "The current database has no user tables — cannot validate compatibility." };
    }

    const missingTables = dbTables.filter((t) => {
      const lower = t.toLowerCase();
      return !dumpTables.some((dt) => dt.toLowerCase() === lower);
    });

    if (missingTables.length > 0) {
      return {
        success: false,
        error: `The dump file is incompatible with the current database — it is missing tables that exist in the current schema: ${missingTables.join(", ")}. This dump may be from an older schema version or a different database.`,
      };
    }

    const extraTables = dumpTables.filter((dt) => {
      const lower = dt.toLowerCase();
      return !dbTables.some((t) => t.toLowerCase() === lower);
    });

    if (extraTables.length > 0) {
      return {
        success: false,
        error: `The dump file is incompatible with the current database — it contains tables that do not exist in the current schema: ${extraTables.join(", ")}. This dump may be from a newer schema version or a different database.`,
      };
    }

    return { success: true, tempId: "" };
  } catch (err) {
    return { success: false, error: `Failed to read file: ${err instanceof Error ? err.message : String(err)}` };
  }
}

async function listDumpTables(dumpPath: string): Promise<string[]> {
  const { stdout } = await execFileAsync(
    process.env.PG_RESTORE_PATH || "pg_restore",
    ["--list", dumpPath],
    { timeout: 30_000 },
  );

  const tables: string[] = [];
  const unq = (s: string) => s.replace(/^"(.*)"$/, "$1");

  for (const line of stdout.split("\n")) {
    const trimmed = line.trim();
    if (trimmed.startsWith(";") || trimmed === "") continue;

    const ti = trimmed.search(/\sTABLE\s/);
    if (ti === -1) continue;

    let rest = trimmed.slice(ti + 7).trim();
    if (!rest) continue;

    if (rest.startsWith("DATA ")) {
      rest = rest.slice(5).trimStart();
    } else if (rest === "DATA") {
      continue;
    }

    const tokens = rest.split(/\s+/);
    if (tokens.length === 0) continue;

    const first = tokens[0];
    const knownSchemas = new Set(["public", "-", "pg_catalog", "information_schema", "pg_toast"]);
    const name = knownSchemas.has(first) ? tokens[1] : first;

    if (!name) continue;
    const clean = unq(name);
    if (clean && !clean.startsWith("_prisma") && clean !== "BackupHistory" && clean !== "AppConfig") {
      tables.push(clean);
    }
  }
  return tables;
}

export async function restoreFromFile(
  filePath: string,
  filename: string,
  backupType: "FULL" | "HOURLY",
  adminId: number,
): Promise<{ success: true } | { success: false; error: string }> {
  await syncBackupHistorySequence();

  const existingPath = filePath;
  try {
    await fs.access(existingPath);
  } catch {
    return { success: false, error: `Backup file not found at ${existingPath}` };
  }

  let savedRows: Array<Record<string, unknown>> = [];
  try {
    savedRows = (await prisma.backupHistory.findMany({
      orderBy: { id: "asc" },
    })) as unknown as Array<Record<string, unknown>>;

    await prisma.$executeRawUnsafe(`DROP TABLE IF EXISTS "${BACKUP_TABLE}" CASCADE`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return { success: false, error: `Failed to save/drop BackupHistory: ${msg}` };
  }

  const conn = connection();

  try {
    const args = pgRestoreArgs(conn, existingPath);
    const env = { ...process.env, PGPASSWORD: conn.password };
    await execFileAsync(PG_RESTORE, args, { env, timeout: 600_000 });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    try {
      await recreateBackupHistoryTable();
      for (const row of savedRows) {
        await prisma.backupHistory.create({ data: row as never });
      }
      await syncBackupHistorySequence();
      await prisma.backupHistory.create({
        data: {
          backup_type: "RESTORE",
          trigger_source: "RESTORE",
          status: "FAILED",
          filename: `RESTORE_${filename}`,
          directory: path.dirname(filePath),
          error_message: `Restore of imported file ${filename} failed: ${msg}`,
          restored_by_id: adminId,
        },
      });
    } catch { /* best-effort */ }
    return { success: false, error: msg };
  }

  try {
    await recreateBackupHistoryTable();
    for (const row of savedRows) {
      await prisma.backupHistory.create({ data: row as never });
    }
    await syncBackupHistorySequence();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return { success: false, error: `Restore succeeded but failed to re-create BackupHistory: ${msg}` };
  }

  try {
    await resetAllSequences(conn);
  } catch (err) {
    logger.error({ err }, "Sequence reset failed after import restore");
  }

  await prisma.backupHistory.create({
    data: {
      backup_type: "RESTORE",
      trigger_source: "RESTORE",
      status: "SUCCESS",
      filename: `RESTORED_${filename}`,
      directory: path.dirname(filePath),
      restored_by_id: adminId,
    },
  });

  await rotateJwtSecretAndRestart();

  return { success: true };
}

export function getTempDir(): string {
  const dir = path.join(os.tmpdir(), "dispatch-backup-imports");
  fsSync.mkdirSync(dir, { recursive: true });
  return dir;
}

export async function listRestorableBackups(
  limit = 200,
  offset = 0,
): Promise<{ data: Array<Record<string, unknown>>; total: number }> {
  try {
    const allData = await prisma.backupHistory.findMany({
      where: { status: "SUCCESS" },
      orderBy: { created_at: "desc" },
      take: limit,
      skip: offset,
    });

    const restorable = [];
    for (const row of allData) {
      if (row.backup_type === "PRESAFETY" || row.backup_type === "RESTORE") continue;
      const filePath = path.join(row.directory, row.filename);
      try {
        await fs.access(filePath);
        restorable.push(row);
      } catch {
        // File doesn't exist on disk, skip
      }
    }

    return { data: restorable as unknown as Array<Record<string, unknown>>, total: restorable.length };
  } catch (err) {
    if (
      err instanceof Prisma.PrismaClientKnownRequestError &&
      err.code === "P2021"
    ) {
      await recreateBackupHistoryTable();
      return { data: [], total: 0 };
    }
    throw err;
  }
}

export async function listPresafetyBackups(
  limit = 200,
  offset = 0,
): Promise<{ data: Array<Record<string, unknown>>; total: number }> {
  try {
    const allData = await prisma.backupHistory.findMany({
      where: { backup_type: "PRESAFETY", status: "SUCCESS" },
      orderBy: { created_at: "desc" },
      take: limit,
      skip: offset,
    });

    const existing = [];
    for (const row of allData) {
      const filePath = path.join(row.directory, row.filename);
      try {
        await fs.access(filePath);
        existing.push(row);
      } catch {
        // File doesn't exist on disk, skip
      }
    }

    return { data: existing as unknown as Array<Record<string, unknown>>, total: existing.length };
  } catch (err) {
    if (
      err instanceof Prisma.PrismaClientKnownRequestError &&
      err.code === "P2021"
    ) {
      await recreateBackupHistoryTable();
      return { data: [], total: 0 };
    }
    throw err;
  }
}

export async function listBackupHistory(
  filter: "all" | "full" | "hourly" | "restore" | "presafety" = "all",
  limit = 200,
  offset = 0,
): Promise<{ data: Array<Record<string, unknown>>; total: number }> {
  const where: Prisma.BackupHistoryWhereInput =
    filter === "full" ? { backup_type: "FULL" } :
    filter === "hourly" ? { backup_type: "HOURLY" } :
    filter === "restore" ? { backup_type: "RESTORE" } :
    filter === "presafety" ? { backup_type: "PRESAFETY" } :
    {};

  try {
    const [data, total] = await Promise.all([
      prisma.backupHistory.findMany({ where, orderBy: { created_at: "desc" }, take: limit, skip: offset }),
      prisma.backupHistory.count({ where }),
    ]);
    return { data: data as unknown as Array<Record<string, unknown>>, total };
  } catch (err) {
    // If the table doesn't exist (P2021), recreate it and return empty
    if (
      err instanceof Prisma.PrismaClientKnownRequestError &&
      err.code === "P2021"
    ) {
      await recreateBackupHistoryTable();
      return { data: [], total: 0 };
    }
    throw err;
  }
}

async function rotateBackups(backupType: BackupTypeEnum, _dir: string): Promise<void> {
  const keep =
    backupType === "FULL" ? DAILY_KEEP :
    backupType === "HOURLY" ? HOURLY_KEEP :
    backupType === "PRESAFETY" ? PRESAFETY_KEEP :
    0;
  if (keep === 0) return;

  const rows = await prisma.backupHistory.findMany({
    where: { backup_type: backupType, status: "SUCCESS", restored_from_id: null },
    orderBy: { created_at: "asc" },
    select: { id: true, filename: true, directory: true },
  });

  const toDelete = rows.slice(0, Math.max(0, rows.length - keep));

  for (const row of toDelete) {
    const filePath = path.join(row.directory, row.filename);
    try {
      await fs.unlink(filePath);
    } catch {
      // File might already be gone
    }
    await prisma.backupHistory.delete({ where: { id: row.id } });
  }
}

async function recreateBackupHistoryTable(): Promise<void> {
  await prisma.$executeRawUnsafe(`
    CREATE TABLE IF NOT EXISTS "${BACKUP_TABLE}" (
      "id"              SERIAL NOT NULL,
      "backup_type"     "BackupType" NOT NULL,
      "trigger_source"   "BackupTrigger" NOT NULL,
      "status"          "BackupStatus" NOT NULL,
      "filename"        TEXT NOT NULL,
      "file_size"       BIGINT,
      "directory"       TEXT NOT NULL,
      "error_message"   TEXT,
      "restored_from_id" INTEGER,
      "restored_by_id"  INTEGER,
      "created_at"      TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT "${BACKUP_TABLE}_pkey" PRIMARY KEY ("id")
    )
  `);
  await prisma.$executeRawUnsafe(`
    CREATE INDEX IF NOT EXISTS "${BACKUP_TABLE}_backup_type_created_at_idx"
      ON "${BACKUP_TABLE}"("backup_type", "created_at")
  `);
  await prisma.$executeRawUnsafe(`
    CREATE INDEX IF NOT EXISTS "${BACKUP_TABLE}_created_at_idx"
      ON "${BACKUP_TABLE}"("created_at")
  `);
  await prisma.$executeRawUnsafe(`
    CREATE INDEX IF NOT EXISTS "${BACKUP_TABLE}_status_idx"
      ON "${BACKUP_TABLE}"("status")
  `);
}

async function syncBackupHistorySequence(): Promise<void> {
  await prisma.$executeRawUnsafe(
    `SELECT setval('"${BACKUP_SEQUENCE}"', COALESCE((SELECT MAX(id) FROM "${BACKUP_TABLE}"), 0) + 1, false)`,
  );
}

async function resetAllSequences(conn: DbConnection): Promise<void> {
  const env = { ...process.env, PGPASSWORD: conn.password };
  const { stdout } = await execFileAsync(
    PSQL,
    [
      "-h", conn.host,
      "-p", String(conn.port),
      "-U", conn.user,
      "-d", conn.database,
      "-t",
      "-A",
      "-c",
      `SELECT tablename FROM pg_tables
       WHERE schemaname = 'public'
         AND tablename != '${BACKUP_TABLE}'
         AND tablename != '_prisma_migrations'
       ORDER BY tablename`,
    ],
    { env, timeout: 30_000 },
  );

  const tables = stdout.trim().split("\n").filter(Boolean);

  for (const table of tables) {
    const { stdout: maxId } = await execFileAsync(
      PSQL,
      [
        "-h", conn.host,
        "-p", String(conn.port),
        "-U", conn.user,
        "-d", conn.database,
        "-t",
        "-A",
        "-c",
        `SELECT COALESCE(MAX("id"), 0) FROM "${table}"`,
      ],
      { env, timeout: 15_000 },
    );

    const nextVal = parseInt(maxId.trim(), 10) + 1;

    await execFileAsync(
      PSQL,
      [
        "-h", conn.host,
        "-p", String(conn.port),
        "-U", conn.user,
        "-d", conn.database,
        "-c",
        `ALTER SEQUENCE "${table}_id_seq" RESTART WITH ${nextVal}`,
      ],
      { env, timeout: 15_000 },
    );
  }
}

async function logHistory(
  backupType: BackupTypeEnum,
  trigger: BackupTriggerEnum,
  status: "SUCCESS" | "FAILED",
  filename: string,
  directory: string,
  errorMessage?: string,
  fileSize?: number,
) {
  return prisma.backupHistory.create({
    data: {
      backup_type: backupType,
      trigger_source: trigger,
      status,
      filename,
      directory,
      file_size: fileSize ?? null,
      error_message: errorMessage ?? null,
    },
  });
}
