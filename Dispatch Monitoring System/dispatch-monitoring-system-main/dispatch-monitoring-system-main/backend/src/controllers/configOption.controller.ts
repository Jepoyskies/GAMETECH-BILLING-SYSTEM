import { Request, Response } from "express";
import { z } from "zod";
import prisma from "../lib/prisma";
import { ConflictError, NotFoundError, ValidationError } from "../lib/errors";
import { parseIdParam } from "../lib/utils";
import { writeAudit } from "../lib/audit";
import { emitAuditChanged, emitEntityChanged } from "../lib/socket";
import {
  CreateConfigOptionSchema,
  UpdateConfigOptionSchema,
  ReorderConfigOptionsSchema,
  ConfigOptionQuerySchema,
} from "../lib/validators";
import type { ConfigListType, ConfigListModule } from "@prisma/client";
import { Prisma } from "@prisma/client";
import logger from "../lib/logger";

type ConfigOptionQuery = z.infer<typeof ConfigOptionQuerySchema>;
type CreateConfigOptionBody = z.infer<typeof CreateConfigOptionSchema>;
type UpdateConfigOptionBody = z.infer<typeof UpdateConfigOptionSchema>;
type ReorderConfigOptionsBody = z.infer<typeof ReorderConfigOptionsSchema>;

interface HardcodedOption {
  label: string;
  color: string;
  dispatch_equivalent?: string;
}

type HardcodedOptionsMap = Partial<Record<ConfigListType, Partial<Record<ConfigListModule, HardcodedOption[]>>>>;

const HARDCODED_OPTIONS: HardcodedOptionsMap = {
  STATUS: {
    DISPATCH: [
      { label: "Done", color: "#16a34a" },
      { label: "Cancelled", color: "#ef4444" },
    ],
    MONITORING: [
      { label: "Pending", color: "#f59e0b" },
    ],
  },
  TYPE: {
    DISPATCH: [
      { label: "Repair", color: "#f59e0b" },
      { label: "Installation", color: "#0349cb" },
      // { label: "Configuration", color: "#f59e0b" },
      // { label: "Technical Support", color: "#8b5cf6" },
    ],
  },
  CHAT_TYPE: {
    DISPATCH: [
      { label: "Inquiry", color: "#0349cb" },
      { label: "Concern", color: "#ef4444" },
      { label: "For Installation", color: "#16a34a" },
    ],
  },
};

export async function listConfigOptions(req: Request, res: Response) {
  const { list_type, module, include_inactive } = req.query as unknown as ConfigOptionQuery;

  await ensureHardcodedOptions(list_type, module as ConfigListModule);

  const options = await prisma.configOption.findMany({
    where: { list_type, module, ...(include_inactive ? {} : { active: true }) },
    orderBy: { sort_order: "asc" },
    include: { dispatch_equivalent: { select: { id: true, label: true } } },
  });

  res.json({ success: true, data: options });
}

async function ensureHardcodedOptions(list_type: ConfigListType, module: ConfigListModule) {
  const hardcoded = HARDCODED_OPTIONS[list_type]?.[module];
  if (!hardcoded) return;

  if (module !== "DISPATCH") {
    await ensureHardcodedOptions(list_type, "DISPATCH");
  }

  const BASE_SORT_ORDER = -3;

  for (let i = 0; i < hardcoded.length; i++) {
    const { label, color, dispatch_equivalent } = hardcoded[i];
    const existing = await prisma.configOption.findFirst({
      where: { list_type, module, label: { equals: label, mode: "insensitive" } },
    });

    if (!existing) {
      try {
        const created = await prisma.configOption.create({
          data: {
            list_type,
            module,
            label,
            color,
            sort_order: BASE_SORT_ORDER + i,
            active: true,
            hardcoded: true,
          },
        });

        if (dispatch_equivalent && module !== "DISPATCH") {
          const target = await prisma.configOption.findFirst({
            where: { list_type, module: "DISPATCH", label: { equals: dispatch_equivalent, mode: "insensitive" } },
          });
          if (target) {
            await prisma.configOption.update({
              where: { id: created.id },
              data: { dispatch_equivalent_id: target.id },
            });
          }
        }
      } catch (e) {
        if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === "P2002") {
          // Another concurrent request created this option — skip
        } else {
          throw e;
        }
      }
    } else {
      const updateData: Record<string, unknown> = {};
      if (!existing.hardcoded) updateData.hardcoded = true;
      if (dispatch_equivalent && !existing.dispatch_equivalent_id && module !== "DISPATCH") {
        const target = await prisma.configOption.findFirst({
          where: { list_type, module: "DISPATCH", label: { equals: dispatch_equivalent, mode: "insensitive" } },
        });
        if (target) {
          updateData.dispatch_equivalent_id = target.id;
        }
      }
      if (Object.keys(updateData).length > 0) {
        await prisma.configOption.update({ where: { id: existing.id }, data: updateData });
      }
    }
  }
}

export async function ensureAllHardcodedOptions() {
  for (const [listType, modules] of Object.entries(HARDCODED_OPTIONS)) {
    for (const [module] of Object.entries(modules)) {
      await ensureHardcodedOptions(listType as ConfigListType, module as ConfigListModule);
    }
  }
  logger.info("Hardcoded config options ensured.");
}

export async function createConfigOption(req: Request, res: Response) {
  const body = req.body as CreateConfigOptionBody;

  const existing = await prisma.configOption.findFirst({
    where: {
      list_type: body.list_type,
      module: body.module,
      label: { equals: body.label, mode: "insensitive" },
    },
  });

  if (existing) {
    if (existing.active) {
      throw new ConflictError("An option with this name already exists in this list");
    }
    const max = await prisma.configOption.aggregate({
      where: { list_type: body.list_type, module: body.module, active: true },
      _max: { sort_order: true },
    });
    const reactivated = await prisma.configOption.update({
      where: { id: existing.id },
      data: { active: true, label: body.label, color: body.color, sort_order: (max._max.sort_order ?? 0) + 1 },
    });

    await writeAudit(prisma, {
      action: "CREATE",
      entity_type: "ConfigOption",
      entity_id: reactivated.id,
      actor_id: req.user!.id,
      summary: `Reactivated ${reactivated.list_type} option "${reactivated.label}" for ${reactivated.module}`,
      after: { label: reactivated.label, list_type: reactivated.list_type, module: reactivated.module },
    });

    emitEntityChanged("configOption:changed", reactivated.id);
    emitAuditChanged();

    res.status(200).json({ success: true, data: reactivated });
    return;
  }

  const max = await prisma.configOption.aggregate({
    where: { list_type: body.list_type, module: body.module },
    _max: { sort_order: true },
  });

  const created = await prisma.configOption.create({
    data: { ...body, sort_order: (max._max.sort_order ?? 0) + 1 },
  }).catch((e) => {
    if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === "P2002") {
      throw new ConflictError("An option with this name already exists in this list");
    }
    throw e;
  });

  await writeAudit(prisma, {
    action: "CREATE",
    entity_type: "ConfigOption",
    entity_id: created.id,
    actor_id: req.user!.id,
    summary: `Created ${created.list_type} option "${created.label}" for ${created.module}`,
    after: { label: created.label, list_type: created.list_type, module: created.module },
  });

  emitEntityChanged("configOption:changed", created.id);
  emitAuditChanged();

  res.status(201).json({ success: true, data: created });
}

export async function updateConfigOption(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const body = req.body as UpdateConfigOptionBody;

  if (Object.keys(body).length === 0) {
    throw new ValidationError("Provide at least one field to update");
  }

  if ("dispatch_equivalent_id" in body) {
    throw new ValidationError(
      "dispatch_equivalent_id cannot be changed through this endpoint"
    );
  }

  const existing = await prisma.configOption.findUnique({ where: { id } });
  if (!existing) throw new NotFoundError("Option");

  if (existing.hardcoded && body.label !== undefined) {
    throw new ValidationError("Cannot rename a hardcoded option");
  }

  if (body.label) {
    const duplicate = await prisma.configOption.findFirst({
      where: {
        list_type: existing.list_type,
        module: existing.module,
        label: { equals: body.label, mode: "insensitive" },
        active: true,
        NOT: { id },
      },
    });
    if (duplicate) {
      throw new ConflictError("An option with this name already exists in this list");
    }
  }

  if (existing.hardcoded && body.label !== undefined) {
    throw new ValidationError("Cannot rename a hardcoded option");
  }

  const updated = await prisma.configOption.update({ where: { id }, data: body });

  await writeAudit(prisma, {
    action: "UPDATE",
    entity_type: "ConfigOption",
    entity_id: id,
    actor_id: req.user!.id,
    summary: `Updated ${existing.list_type} option "${existing.label}"`,
    before: { label: existing.label, color: existing.color, active: existing.active },
    after: { label: updated.label, color: updated.color, active: updated.active },
  });

  emitEntityChanged("configOption:changed", id);
  emitAuditChanged();

  res.json({ success: true, data: updated });
}

export async function deactivateConfigOption(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);

  const existing = await prisma.configOption.findUnique({ where: { id } });
  if (!existing) throw new NotFoundError("Option");

  if (existing.hardcoded) {
    throw new ValidationError("Cannot delete a hardcoded option");
  }

  if (!existing.active) {
    throw new ConflictError("This option is already inactive");
  }

  const deactivated = await prisma.configOption.update({
    where: { id },
    data: { active: false },
  });

  await writeAudit(prisma, {
    action: "DELETE",
    entity_type: "ConfigOption",
    entity_id: id,
    actor_id: req.user!.id,
    summary: `Deactivated ${existing.list_type} option "${existing.label}"`,
    before: { label: existing.label, active: true },
    after: { label: existing.label, active: false },
  });

  emitEntityChanged("configOption:changed", id);
  emitAuditChanged();

  res.json({ success: true, data: deactivated });
}

export async function reorderConfigOptions(req: Request, res: Response) {
  const { list_type, module, ordered_ids } = req.body as ReorderConfigOptionsBody;

  if (new Set(ordered_ids).size !== ordered_ids.length) {
    throw new ValidationError("Duplicate ids in reorder payload");
  }

  const activeOptions = await prisma.configOption.findMany({
    where: { list_type, module, active: true },
    orderBy: { sort_order: "asc" },
  });
  const validIds = new Set(activeOptions.map((o) => o.id));

  for (const id of ordered_ids) {
    if (!validIds.has(id)) {
      throw new ValidationError(`Option ${id} does not belong to this list or is inactive`);
    }
  }
  if (ordered_ids.length !== activeOptions.length) {
    throw new ValidationError("Reorder payload must include every active option in this list");
  }

  await prisma.$transaction(
    async (tx) => {
      for (let i = 0; i < ordered_ids.length; i++) {
        await tx.configOption.update({ where: { id: ordered_ids[i] }, data: { sort_order: i } });
      }
    },
    { isolationLevel: Prisma.TransactionIsolationLevel.Serializable }
  );

  const reordered = await prisma.configOption.findMany({
    where: { list_type, module },
    orderBy: { sort_order: "asc" },
  });

  await writeAudit(prisma, {
    action: "UPDATE",
    entity_type: "ConfigOption",
    entity_id: reordered[0]?.id ?? 0,
    actor_id: req.user!.id,
    summary: `Reordered ${list_type} options for ${module}`,
  });

  emitEntityChanged("configOption:changed");
  emitAuditChanged();

  res.json({ success: true, data: reordered });
}