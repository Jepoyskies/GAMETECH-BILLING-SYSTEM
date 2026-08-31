import { Router } from "express";
import {
  listConfigOptions,
  createConfigOption,
  updateConfigOption,
  deactivateConfigOption,
  reorderConfigOptions,
} from "../controllers/configOption.controller";
import { validateBody, validateQuery } from "../middleware/validate";
import { requireAuth } from "../middleware/auth";
import {
  CreateConfigOptionSchema,
  UpdateConfigOptionSchema,
  ReorderConfigOptionsSchema,
  ConfigOptionQuerySchema,
} from "../lib/validators";

const router = Router();

router.get("/", validateQuery(ConfigOptionQuerySchema), listConfigOptions);
router.post("/", requireAuth, validateBody(CreateConfigOptionSchema), createConfigOption);
router.post("/reorder", requireAuth, validateBody(ReorderConfigOptionsSchema), reorderConfigOptions);
router.put("/:id", requireAuth, validateBody(UpdateConfigOptionSchema), updateConfigOption);
router.delete("/:id", requireAuth, deactivateConfigOption);

export default router;