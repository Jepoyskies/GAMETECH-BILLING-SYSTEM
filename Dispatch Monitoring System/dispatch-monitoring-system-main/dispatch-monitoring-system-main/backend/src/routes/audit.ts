import { Router } from "express";
import { listAuditLogs } from "../controllers/audit.controller";
import {
  listAuditExportMonths,
  exportAuditLogs,
  exportAuditLogsExcel,
} from "../controllers/export/auditExport.controller";
import { requireAuth } from "../middleware/auth";

const router = Router();

router.get("/export/months", requireAuth, listAuditExportMonths);
router.get("/export", requireAuth, exportAuditLogs);
router.get("/export/excel", requireAuth, exportAuditLogsExcel);
router.get("/", requireAuth, listAuditLogs);

export default router;
