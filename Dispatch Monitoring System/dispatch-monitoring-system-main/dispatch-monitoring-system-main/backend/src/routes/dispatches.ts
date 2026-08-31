import { Router } from "express";
import {
  listDispatches,
  getDispatch,
  updateDispatch,
  deleteDispatch,
} from "../controllers/dispatches.controller";
import {
  listDispatchExportMonths,
  exportDispatches,
  exportDispatchesExcel,
} from "../controllers/export/dispatchExport.controller";
import { validateBody } from "../middleware/validate";
import { requireSuperAdmin } from "../middleware/auth";
import { UpdateDispatchSchema, DeleteDispatchSchema } from "../lib/validators";

const router = Router();

router.get("/", listDispatches);
router.get("/export/months", listDispatchExportMonths);
router.get("/export", exportDispatches);
router.get("/export/excel", exportDispatchesExcel);
router.get("/:id", getDispatch);
router.put("/:id", validateBody(UpdateDispatchSchema), updateDispatch);
router.delete("/:id", requireSuperAdmin, validateBody(DeleteDispatchSchema), deleteDispatch);

export default router;