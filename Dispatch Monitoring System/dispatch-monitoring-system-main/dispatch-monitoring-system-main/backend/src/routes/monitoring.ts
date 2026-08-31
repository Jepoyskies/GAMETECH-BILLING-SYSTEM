import { Router } from "express";
import {
  listMonitoring,
  getMonitoringRecord,
  createMonitoringRecord,
  updateMonitoringRecord,
  markMonitoringRecordDone,
  cancelMonitoringRecord,
  deleteMonitoringRecord,
} from "../controllers/monitoring.controller";
import { validateBody } from "../middleware/validate";
import { requireSuperAdmin } from "../middleware/auth";
import {
  CreateMonitoringSchema,
  UpdateMonitoringSchema,
  MarkDoneMonitoringSchema,
  CancelMonitoringSchema,
  DeleteMonitoringSchema,
} from "../lib/validators";

const router = Router();

router.get("/", listMonitoring);
router.get("/:id", getMonitoringRecord);
router.post("/", validateBody(CreateMonitoringSchema), createMonitoringRecord);
router.put("/:id", validateBody(UpdateMonitoringSchema), updateMonitoringRecord);
router.post("/:id/done", validateBody(MarkDoneMonitoringSchema), markMonitoringRecordDone);
router.post("/:id/cancel", validateBody(CancelMonitoringSchema), cancelMonitoringRecord);
router.delete("/:id", requireSuperAdmin, validateBody(DeleteMonitoringSchema), deleteMonitoringRecord);

export default router;