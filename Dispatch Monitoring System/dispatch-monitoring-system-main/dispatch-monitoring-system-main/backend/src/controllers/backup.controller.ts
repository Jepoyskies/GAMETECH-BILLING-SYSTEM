import path from "path";
import fs from "fs";
import crypto from "crypto";
import { Request, Response } from "express";
import prisma from "../lib/prisma";
import { verifyPassword } from "../lib/auth";
import {
  createBackup,
  restoreBackup,
  restoreFromFile,
  validateImportFile,
  getTempDir,
  listBackupHistory,
  listRestorableBackups,
  listPresafetyBackups,
} from "../lib/backup";

export async function getBackupHistory(req: Request, res: Response) {
  const filter = (req.query.filter as string) || "all";
  const limit = Math.min(parseInt(req.query.limit as string) || 200, 500);
  const offset = parseInt(req.query.offset as string) || 0;

  if (!["all", "full", "hourly", "restore", "presafety"].includes(filter)) {
    res.status(400).json({ success: false, error: "Invalid filter. Use 'all', 'full', 'hourly', 'restore', or 'presafety'." });
    return;
  }

  const result = await listBackupHistory(filter as "all" | "full" | "hourly" | "restore" | "presafety", limit, offset);
  res.json({ success: true, data: result.data, total: result.total });
}

export async function getRestorableBackups(_req: Request, res: Response) {
  const limit = Math.min(parseInt(_req.query.limit as string) || 200, 500);
  const offset = parseInt(_req.query.offset as string) || 0;

  const result = await listRestorableBackups(limit, offset);
  res.json({ success: true, data: result.data, total: result.total });
}

export async function getPresafetyBackups(_req: Request, res: Response) {
  const limit = Math.min(parseInt(_req.query.limit as string) || 200, 500);
  const offset = parseInt(_req.query.offset as string) || 0;

  const result = await listPresafetyBackups(limit, offset);
  res.json({ success: true, data: result.data, total: result.total });
}

export async function triggerManualBackup(req: Request, res: Response) {
  const directory = (req.body.directory as string) || "";

  const result = await createBackup("FULL", "MANUAL", directory);
  if (result.success) {
    res.status(201).json({ success: true, data: { id: result.historyId, filename: result.filename, file_size: result.fileSize } });
  } else {
    res.status(500).json({ success: false, error: result.error });
  }
}

export async function triggerRestore(req: Request, res: Response) {
  const historyId = parseInt(req.body.history_id as string, 10);
  if (isNaN(historyId) || historyId <= 0) {
    res.status(400).json({ success: false, error: "Invalid history_id" });
    return;
  }

  const currentPassword = req.body.current_password as string | undefined;
  if (!currentPassword) {
    res.status(400).json({ success: false, error: "Your password is required to confirm this action." });
    return;
  }

  const actor = req.user!;
  const admin = await prisma.cSR.findFirst({
    where: { id: actor.id, deleted_at: null },
  });
  if (!admin?.password_hash) {
    res.status(401).json({ success: false, error: "Your session is no longer valid. Please log in again." });
    return;
  }
  const credentialsOk = await verifyPassword(currentPassword, admin.password_hash);
  if (!credentialsOk) {
    res.status(403).json({ success: false, error: "Your password is incorrect." });
    return;
  }

  const result = await restoreBackup(historyId, req.user!.id);
  if (result.success) {
    res.json({ success: true, data: { message: "Database restored successfully" } });
  } else {
    res.status(500).json({ success: false, error: result.error });
  }
}

export async function validateImport(req: Request, res: Response) {
  const file = req.file;
  if (!file) {
    res.status(400).json({ success: false, error: "No file uploaded." });
    return;
  }

  const tempDir = getTempDir();
  const tempId = crypto.randomUUID();
  const ext = path.extname(file.originalname) || ".dump";
  const destPath = path.join(tempDir, `${tempId}${ext}`);

  try {
    fs.copyFileSync(file.path, destPath);
    fs.unlinkSync(file.path);
  } catch {
    res.status(500).json({ success: false, error: "Failed to save uploaded file." });
    return;
  }

  const validation = await validateImportFile(destPath);
  if (!validation.success) {
    try { fs.unlinkSync(destPath); } catch { /* ignore */ }
    res.status(400).json({ success: false, error: validation.error });
    return;
  }

  res.json({
    success: true,
    data: {
      temp_id: tempId,
      original_filename: file.originalname,
      file_size: file.size,
      dest_path: destPath,
    },
  });
}

export async function importRestore(req: Request, res: Response) {
  const tempId = req.body.temp_id as string | undefined;
  const currentPassword = req.body.current_password as string | undefined;

  if (!tempId) {
    res.status(400).json({ success: false, error: "Missing temp_id." });
    return;
  }

  if (!currentPassword) {
    res.status(400).json({ success: false, error: "Your password is required to confirm this action." });
    return;
  }

  const tempDir = getTempDir();
  const files = fs.readdirSync(tempDir).filter((f) => f.startsWith(tempId));
  if (files.length === 0) {
    res.status(404).json({ success: false, error: "Uploaded file not found. Please re-upload." });
    return;
  }

  const destPath = path.join(tempDir, files[0]);
  const originalFilename = req.body.original_filename || files[0];

  const actor = req.user!;
  const admin = await prisma.cSR.findFirst({
    where: { id: actor.id, deleted_at: null },
  });
  if (!admin?.password_hash) {
    res.status(401).json({ success: false, error: "Your session is no longer valid. Please log in again." });
    return;
  }
  const credentialsOk = await verifyPassword(currentPassword, admin.password_hash);
  if (!credentialsOk) {
    res.status(403).json({ success: false, error: "Your password is incorrect." });
    return;
  }

  const safetyBackup = await createBackup("PRESAFETY", "PRESAFETY", undefined, "presafety");
  if (!safetyBackup.success) {
    res.status(500).json({ success: false, error: `Failed to create safety backup before import: ${safetyBackup.error}` });
    return;
  }

  const result = await restoreFromFile(destPath, originalFilename, "FULL", req.user!.id);

  try { fs.unlinkSync(destPath); } catch { /* ignore */ }

  if (result.success) {
    res.json({
      success: true,
      data: {
        message: `Database restored from imported file successfully. A safety backup was created beforehand: "${safetyBackup.filename}"`,
        safety_backup: { id: safetyBackup.historyId, filename: safetyBackup.filename },
      },
    });
  } else {
    res.status(500).json({ success: false, error: result.error });
  }
}

export async function downloadBackup(req: Request, res: Response) {
  const id = parseInt(req.params.id, 10);
  if (isNaN(id) || id <= 0) {
    res.status(400).json({ success: false, error: "Invalid backup id" });
    return;
  }

  const entry = await prisma.backupHistory.findUnique({ where: { id } });
  if (!entry) {
    res.status(404).json({ success: false, error: "Backup entry not found" });
    return;
  }

  const filePath = path.join(entry.directory, entry.filename);
  if (!fs.existsSync(filePath)) {
    res.status(404).json({ success: false, error: "Backup file not found on disk" });
    return;
  }

  res.download(filePath, entry.filename);
}

export async function getDefaultDirectory(_req: Request, res: Response) {
  const persisted = await prisma.appConfig.findUnique({ where: { key: "backup_directory" } });
  const dir = persisted?.value?.trim() || process.env.BACKUP_DIR || "";
  res.json({ success: true, data: { directory: dir } });
}

export async function updateDirectory(req: Request, res: Response) {
  const { directory } = req.body;
  if (!directory || typeof directory !== "string" || !directory.trim()) {
    res.status(400).json({ success: false, error: "Directory path is required" });
    return;
  }
  await prisma.appConfig.upsert({
    where: { key: "backup_directory" },
    update: { value: directory.trim() },
    create: { key: "backup_directory", value: directory.trim() },
  });
  res.json({ success: true, data: { directory: directory.trim() } });
}
