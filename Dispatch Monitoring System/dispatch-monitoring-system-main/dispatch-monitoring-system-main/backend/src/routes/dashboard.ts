import { Router } from "express";
import {
  getStats,
  getByStaff,
  getByTeam,
  getByAdmin,
  getMonitoringSummary,
  getTargets,
  upsertTarget,
  deleteTarget,
} from "../controllers/dashboard.controller";
import { exportDashboardExcel } from "../controllers/export/dashboardExport.controller";
import { validateBody } from "../middleware/validate";
import { MonthlyTargetSchema } from "../lib/validators";

const router = Router();

router.get("/stats", getStats);
router.get("/by-staff", getByStaff);
router.get("/by-team", getByTeam);
router.get("/by-admin", getByAdmin);
router.get("/monitoring-summary", getMonitoringSummary);
router.get("/targets", getTargets);
router.post("/targets", validateBody(MonthlyTargetSchema), upsertTarget);
router.delete("/targets/:id", deleteTarget);

router.get("/export/excel", exportDashboardExcel);

export default router;
