import { Router } from "express";
import rateLimit from "express-rate-limit";
import {
  getSetupStatus,
  setup,
  login,
  logout,
  me,
  createAccount,
  listAccounts,
  updateAccount,
  updateAccountPassword,
} from "../controllers/auth.controller";
import { requireAuth, requireSuperAdmin } from "../middleware/auth";
import { validateBody } from "../middleware/validate";
import {
  SetupSchema,
  LoginSchema,
  CreateAccountSchema,
  UpdateAccountSchema,
  UpdatePasswordSchema,
} from "../lib/validators";

const router = Router();

const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 20,
  standardHeaders: true,
  legacyHeaders: false,
  skipSuccessfulRequests: true,
  message: {
    success: false,
    error: "Too many login attempts. Please wait a few minutes and try again.",
  },
});

const passwordLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    success: false,
    error: "Too many password change attempts. Please wait a few minutes and try again.",
  },
});

router.get("/setup", getSetupStatus);
router.post("/setup", authLimiter, validateBody(SetupSchema), setup);
router.post("/login", authLimiter, validateBody(LoginSchema), login);
router.post("/logout", logout);

router.get("/me", requireAuth, me);

router.get("/accounts", requireAuth, listAccounts);
router.post(
  "/accounts",
  requireAuth,
  requireSuperAdmin,
  validateBody(CreateAccountSchema),
  createAccount
);
router.put(
  "/accounts/:id",
  requireAuth,
  validateBody(UpdateAccountSchema),
  updateAccount
);
router.put(
  "/accounts/:id/password",
  requireAuth,
  passwordLimiter,
  validateBody(UpdatePasswordSchema),
  updateAccountPassword
);

export default router;