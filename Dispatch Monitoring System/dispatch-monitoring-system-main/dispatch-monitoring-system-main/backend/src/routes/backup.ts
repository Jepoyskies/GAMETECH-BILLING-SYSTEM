import os from "os";
import multer from "multer";
import { Router } from "express";
import { requireAuth, requireSuperAdmin } from "../middleware/auth";
import {
  getBackupHistory,
  getRestorableBackups,
  getPresafetyBackups,
  triggerManualBackup,
  triggerRestore,
  validateImport,
  importRestore,
  downloadBackup,
  getDefaultDirectory,
  updateDirectory,
} from "../controllers/backup.controller";

const upload = multer({ dest: os.tmpdir() });

const router = Router();

// All backup routes require SUPERADMIN
router.use(requireAuth);
router.use(requireSuperAdmin);

router.get("/history", getBackupHistory);
router.get("/restorable", getRestorableBackups);
router.get("/presafety", getPresafetyBackups);
router.get("/download/:id", downloadBackup);
router.post("/manual", triggerManualBackup);
router.post("/restore", triggerRestore);
router.post("/validate-import", upload.single("file"), validateImport);
router.post("/import-restore", importRestore);
router.get("/directory", getDefaultDirectory);
router.put("/directory", updateDirectory);

export default router;
