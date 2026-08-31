import { Router } from "express";
import {
  listTeams,
  createTeam,
  updateTeam,
  deleteTeam,
} from "../controllers/team.controller";
import { validateBody } from "../middleware/validate";
import { requireAuth } from "../middleware/auth";
import { CreateTeamSchema, UpdateTeamSchema } from "../lib/validators";

const router = Router();

router.get("/", listTeams);
router.post("/", requireAuth, validateBody(CreateTeamSchema), createTeam);
router.put("/:id", requireAuth, validateBody(UpdateTeamSchema), updateTeam);
router.delete("/:id", requireAuth, deleteTeam);

export default router;