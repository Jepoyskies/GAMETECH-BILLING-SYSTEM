import { Router } from "express";
import {
  listCSR,
  createCSR,
  updateCSR,
  deleteCSR,
} from "../controllers/csr.controller";
import { validateBody } from "../middleware/validate";
import { requireAuth, requireSuperAdmin } from "../middleware/auth";
import { CreateCSRSchema, UpdateCSRSchema, DeleteCSRSchema } from "../lib/validators";

const router = Router();

router.get("/", requireAuth, listCSR);

router.post("/", requireSuperAdmin, validateBody(CreateCSRSchema), createCSR);
router.put("/:id", requireSuperAdmin, validateBody(UpdateCSRSchema), updateCSR);
router.delete("/:id", requireSuperAdmin, validateBody(DeleteCSRSchema), deleteCSR);

export default router;