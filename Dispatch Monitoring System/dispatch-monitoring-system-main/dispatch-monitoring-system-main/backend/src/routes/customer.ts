import { Router } from "express";
import {
  listCustomers,
  searchCustomers,
  checkAccountNumber,
  checkName,
  getCustomer,
  getCustomerStats,
  getCustomerJobs,
  createCustomer,
  updateCustomer,
  deleteCustomer,
} from "../controllers/customer.controller";
import { validateBody } from "../middleware/validate";
import { requireSuperAdmin } from "../middleware/auth";
import {
  CreateCustomerSchema,
  UpdateCustomerSchema,
  DeleteCustomerSchema,
} from "../lib/validators";

const router = Router();

router.get("/", listCustomers);
router.get("/search", searchCustomers);
router.get("/check-account", checkAccountNumber);
router.get("/check-name", checkName);
router.get("/:id", getCustomer);
router.get("/:id/stats", getCustomerStats);
router.get("/:id/jobs", getCustomerJobs);
router.post("/", validateBody(CreateCustomerSchema), createCustomer);
router.put("/:id", validateBody(UpdateCustomerSchema), updateCustomer);
router.delete("/:id", requireSuperAdmin, validateBody(DeleteCustomerSchema), deleteCustomer);

export default router;
