import { Router } from "express";
import {
  listTechnicians,
  createTechnician,
  updateTechnician,
  deleteTechnician,
} from "../controllers/technician.controller";
import { validateBody } from "../middleware/validate";
import { requireAuth } from "../middleware/auth";
import { CreateTechnicianSchema, UpdateTechnicianSchema, DeleteTechnicianSchema } from "../lib/validators";

const router = Router();

router.get("/", listTechnicians);
router.post("/", requireAuth, validateBody(CreateTechnicianSchema), createTechnician);
router.put("/:id", requireAuth, validateBody(UpdateTechnicianSchema), updateTechnician);
router.delete("/:id", requireAuth, validateBody(DeleteTechnicianSchema), deleteTechnician);

export default router;