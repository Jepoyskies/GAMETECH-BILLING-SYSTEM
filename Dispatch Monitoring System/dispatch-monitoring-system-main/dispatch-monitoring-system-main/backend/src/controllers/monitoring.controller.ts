import { Request, Response } from "express";
import prisma from "../lib/prisma";
import { NotFoundError, ForbiddenError, BadRequestError, ConflictError } from "../lib/errors";
import { generateTicketNumber, parseIdParam, dedupeTeamIds } from "../lib/utils";
import { autoDispatch } from "../lib/autoDispatch";
import { writeAudit } from "../lib/audit";
import { emitAuditChanged, emitEntityChanged } from "../lib/socket";
import { resolveCustomerLink } from "../lib/customer";
import { csrPublicSelect } from "../lib/select";
import { assertActiveOption, tabTypeToConfigModule, getOptionId } from "../lib/configOptions";
import { SourceTab, ConfigListModule, Prisma } from "@prisma/client";
import {
  CreateMonitoringSchema,
  UpdateMonitoringSchema,
  MonitoringQuerySchema,
  MarkDoneMonitoringSchema,
  CancelMonitoringSchema,
} from "../lib/validators";
import {
  buildDateRangeFilter,
  buildTextContainsFilter,
  buildTicketNumberFilter,
} from "../lib/queryFilters";

const monitoringInclude = {
  statusOption: true,
  typeOption: true,
  chatTypeOption: true,
  teams: { include: { technician: true } },
  csr: { select: csrPublicSelect },
  dispatch: { include: { teams: true } },
  customer: true,
  jobDetail: true,
} as const;

function parseOptionalDatetime(value: string | null | undefined): Date | null {
  if (!value) return null;
  const d = new Date(value);
  return isNaN(d.getTime()) ? null : d;
}

function buildJobDetailData(raw: Record<string, unknown>): Record<string, unknown> {
  const data: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(raw)) {
    if (value === undefined) continue;
    if (key === "schedule_date") {
      data[key] = parseOptionalDatetime(value as string | null | undefined);
    } else {
      data[key] = value;
    }
  }
  return data;
}

async function getModuleDoneStatusId(_module: ConfigListModule): Promise<number> {
  return getOptionId("STATUS", "DISPATCH", "Done");
}

async function getCancelledDispatchStatusId(): Promise<number> {
  return getOptionId("STATUS", "DISPATCH", "Cancelled");
}

export async function listMonitoring(req: Request, res: Response) {
  const query = MonitoringQuerySchema.parse(req.query);
  const {
    tab_type,
    status_id,
    type_id,
    csr,
    client,
    sales_agent,
    ticket_number,
    job_order,
    done,
    ongoing,
    date_from,
    date_to,
    page,
    limit,
  } = query;

  const skip = (page - 1) * limit;

  const where: Record<string, unknown> = {
    deleted_at: null,
    ...(tab_type && { tab_type }),
    ...(done === false && { done_at: null }),
    ...(done === true && { done_at: { not: null } }),
    ...(ongoing === true && { time_start: { not: null } }),
    ...(ongoing === false && { time_start: null }),
    ...(csr && { csr_id: csr }),
    ...(buildTextContainsFilter(client) && { client: buildTextContainsFilter(client) }),
    ...(buildTextContainsFilter(sales_agent) && { sales_agent: buildTextContainsFilter(sales_agent) }),
    ...(buildTicketNumberFilter(ticket_number) && { ticket_number: buildTicketNumberFilter(ticket_number) }),
    ...(buildTextContainsFilter(job_order) && { jobDetail: { job_order: buildTextContainsFilter(job_order) } }),
    ...buildDateRangeFilter(date_from, date_to),
  };

  if (status_id) where.status_id = status_id;
  if (type_id) where.type_id = type_id;

  const [records, total] = await Promise.all([
    prisma.monitoringRecord.findMany({
      where,
      include: monitoringInclude,
      orderBy: [{ date: "desc" }, { created_at: "desc" }],
      skip,
      take: limit,
    }),
    prisma.monitoringRecord.count({ where }),
  ]);

  res.json({
    success: true,
    data: records,
    pagination: {
      total,
      page,
      limit,
      total_pages: Math.ceil(total / limit),
    },
  });
}

export async function getMonitoringRecord(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);

  const record = await prisma.monitoringRecord.findFirst({
    where: { id, deleted_at: null },
    include: monitoringInclude,
  });

  if (!record) throw new NotFoundError("Monitoring record");

  res.json({ success: true, data: record });
}

export async function createMonitoringRecord(req: Request, res: Response) {
  const body = CreateMonitoringSchema.parse(req.body);

  if (body.status_id) await assertActiveOption("STATUS", "MONITORING", body.status_id);
  if (body.type_id) await assertActiveOption("TYPE", "DISPATCH", body.type_id);
  if (body.chat_type_id) await assertActiveOption("CHAT_TYPE", tabTypeToConfigModule(body.tab_type), body.chat_type_id);

  const {
    teams: rawTeams,
    time_start,
    time_accomplish,
    time,
    csr,
    customer_id,
    jobDetail,
    ...rest
  } = body;

  const teams = dedupeTeamIds(rawTeams);

  let ticket_number: string | undefined;

  let dateValue: Date;
  if (time) {
    const [hours, minutes] = time.split(":").map(Number);
    dateValue = new Date(rest.date);
    dateValue.setHours(hours, minutes, 0, 0);
  } else {
    dateValue = new Date(rest.date);
  }

  const record = await prisma.$transaction(async (tx) => {
    if (rest.tab_type === "CLIENT_CONCERNS") {
      ticket_number = await generateTicketNumber(tx);
    }

    const resolvedCustomerId = await resolveCustomerLink(tx, {
      customerId: customer_id,
      updateCustomer: true,
      snapshot: {
        name: rest.client,
        address: rest.address,
        contact_number: rest.contact_number,
        account_number: jobDetail?.account_no ?? undefined,
        email: jobDetail?.email_address ?? undefined,
        barangay_city: jobDetail?.barangay_city ?? undefined,
        latitude: rest.latitude,
        longitude: rest.longitude,
      },
      actorId: req.user!.id,
      allowAutoCreate: true,
    });

    const created = await tx.monitoringRecord.create({
      data: {
        tab_type: rest.tab_type as SourceTab,
        date: dateValue,
        client: rest.client,
        address: rest.address,
        contact_number: rest.contact_number,
        concern: rest.concern ?? "",
        sales_agent: rest.sales_agent ?? null,
        remarks: rest.remarks ?? "",
        actions_taken: rest.actions_taken ?? "",
        latitude: rest.latitude ?? null,
        longitude: rest.longitude ?? null,
        ticket_number,
        time_start: parseOptionalDatetime(time_start),
        time_accomplish: parseOptionalDatetime(time_accomplish),
        statusOption: { connect: { id: rest.status_id } },
        typeOption: rest.type_id ? { connect: { id: rest.type_id } } : undefined,
        chatTypeOption: rest.chat_type_id ? { connect: { id: rest.chat_type_id } } : undefined,
        csr: { connect: { id: csr } },
        ...(resolvedCustomerId
          ? { customer: { connect: { id: resolvedCustomerId } } }
          : {}),
        teams: {
          create: teams.map((tid: number) => ({ technician_id: tid })),
        },
      },
      include: monitoringInclude,
    });

    if (jobDetail && Object.keys(jobDetail).length > 0) {
      const jobDetailData = buildJobDetailData(jobDetail as Record<string, unknown>);
      if (Object.keys(jobDetailData).length > 0) {
        await tx.jobDetail.create({
          data: { record_id: created.id, ...jobDetailData },
        });
      }
    }

    await writeAudit(tx, {
      action: "CREATE",
      entity_type: "MonitoringRecord",
      entity_id: created.id,
      actor_id: req.user!.id,
      summary: `Created ${created.tab_type} record for ${created.client}`,
      after: created,
    });

    emitEntityChanged("monitoringRecord:changed", created.id);
    emitAuditChanged();

    return created;
  });

  res.status(201).json({ success: true, data: record });
}

export async function updateMonitoringRecord(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const body = UpdateMonitoringSchema.parse(req.body);

  const {
    teams: rawTeams,
    time_start,
    time_accomplish,
    time,
    csr,
    customer_id,
    chat_type_id,
    jobDetail,
    ...rest
  } = body;

  const teams = rawTeams !== undefined ? dedupeTeamIds(rawTeams) : undefined;

  let dateValue: Date | undefined;
  if (rest.date !== undefined) {
    if (time) {
      const [hours, minutes] = time.split(":").map(Number);
      dateValue = new Date(rest.date);
      dateValue.setHours(hours, minutes, 0, 0);
    } else {
      dateValue = new Date(rest.date);
    }
  }

  const result = await prisma.$transaction(async (tx) => {
    const existing = await tx.monitoringRecord.findFirst({
      where: { id, deleted_at: null },
      include: monitoringInclude,
    });
    if (!existing) throw new NotFoundError("Monitoring record");

    if (existing.done_at) {
      throw new ForbiddenError(
        "Cannot edit a completed record. It has already been moved to the Dispatch Log."
      );
    }

    if (time_start && existing.time_start) {
      throw new ConflictError(
        "Record is already dispatched. Refresh and try again."
      );
    }

    if (body.status_id !== undefined) await assertActiveOption("STATUS", "MONITORING", body.status_id);
    if (body.type_id !== undefined && body.type_id !== null)
      await assertActiveOption("TYPE", "DISPATCH", body.type_id);
    if (chat_type_id !== undefined && chat_type_id !== null)
      await assertActiveOption("CHAT_TYPE", tabTypeToConfigModule(body.tab_type ?? existing.tab_type), chat_type_id);

    const updateData: Record<string, unknown> = {};

    if (rest.tab_type !== undefined) updateData.tab_type = rest.tab_type as SourceTab;
    if (dateValue !== undefined) updateData.date = dateValue;
    if (rest.client !== undefined) updateData.client = rest.client;
    if (rest.address !== undefined) updateData.address = rest.address;
    if (rest.contact_number !== undefined) updateData.contact_number = rest.contact_number;
    if (rest.concern !== undefined) updateData.concern = rest.concern || "";
    if (rest.sales_agent !== undefined) updateData.sales_agent = rest.sales_agent ?? null;
    if (rest.type_id !== undefined) updateData.typeOption = { connect: { id: rest.type_id } };
    if (chat_type_id !== undefined) updateData.chatTypeOption = { connect: { id: chat_type_id } };
    if (rest.status_id !== undefined) updateData.statusOption = { connect: { id: rest.status_id } };
    if (rest.remarks !== undefined) updateData.remarks = rest.remarks ?? null;
    if (rest.actions_taken !== undefined) updateData.actions_taken = rest.actions_taken ?? null;
    if (rest.latitude !== undefined) updateData.latitude = rest.latitude;
    if (rest.longitude !== undefined) updateData.longitude = rest.longitude;
    if (time_start !== undefined) updateData.time_start = parseOptionalDatetime(time_start);
    if (time_accomplish !== undefined) updateData.time_accomplish = parseOptionalDatetime(time_accomplish);

    if (csr !== undefined) updateData.csr = { connect: { id: csr } };

    if (customer_id === null) {
      updateData.customer = { disconnect: true };
    } else {
      const existingJobDetail = existing.jobDetail;
      const resolvedCustomerId = await resolveCustomerLink(tx, {
        customerId: customer_id ?? existing.customer_id,
        updateCustomer: true,
        snapshot: {
          name: rest.client ?? existing.client,
          address: rest.address ?? existing.address,
          contact_number: rest.contact_number ?? existing.contact_number,
          account_number: jobDetail?.account_no ?? existingJobDetail?.account_no ?? undefined,
          email: jobDetail?.email_address ?? existingJobDetail?.email_address ?? undefined,
          barangay_city: jobDetail?.barangay_city ?? existingJobDetail?.barangay_city ?? undefined,
          latitude: rest.latitude !== undefined ? rest.latitude : existing.latitude,
          longitude: rest.longitude !== undefined ? rest.longitude : existing.longitude,
        },
        actorId: req.user!.id,
        allowAutoCreate: false,
      });
      if (resolvedCustomerId !== undefined) {
        updateData.customer = { connect: { id: resolvedCustomerId } };
      }
    }

    if (teams !== undefined) {
      await tx.monitoringTeam.deleteMany({ where: { record_id: id } });
      if (teams.length > 0) {
        await tx.monitoringTeam.createMany({
          data: teams.map((tid: number) => ({ record_id: id, technician_id: tid })),
        });
      }
    }

    if (jobDetail !== undefined) {
      const jobDetailData = buildJobDetailData(jobDetail as Record<string, unknown>);
      if (Object.keys(jobDetailData).length > 0) {
        const existingDetail = await tx.jobDetail.findUnique({ where: { record_id: id } });
        if (existingDetail) {
          await tx.jobDetail.update({ where: { record_id: id }, data: jobDetailData });
        } else {
          await tx.jobDetail.create({ data: { record_id: id, ...jobDetailData } });
        }
      }
    }

    const updated = await tx.monitoringRecord.update({
      where: { id, deleted_at: null },
      data: updateData,
      include: monitoringInclude,
    });

    let auditSummary = `Updated ${updated.tab_type} record for ${updated.client}`;
    const newTimeStart = updated.time_start ? new Date(updated.time_start) : null;
    const oldTimeStart = existing.time_start ? new Date(existing.time_start) : null;

    if (newTimeStart && !oldTimeStart) {
      auditSummary = `Dispatched ${updated.tab_type} record for ${updated.client}`;
    } else if (!newTimeStart && oldTimeStart) {
      auditSummary = `Undispatched ${updated.tab_type} record for ${updated.client}`;
    }

    await writeAudit(tx, {
      action: "UPDATE",
      entity_type: "MonitoringRecord",
      entity_id: id,
      actor_id: req.user!.id,
      summary: auditSummary,
      before: existing,
      after: updated,
    });

    emitEntityChanged("monitoringRecord:changed", id);
    emitAuditChanged();

    return updated;
  });

  res.json({ success: true, data: result });
}

export async function markMonitoringRecordDone(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const body = MarkDoneMonitoringSchema.parse(req.body);

  const result = await prisma.$transaction(async (tx) => {
    const existing = await tx.monitoringRecord.findFirst({
      where: { id, deleted_at: null },
      include: { csr: { select: csrPublicSelect }, teams: true },
    });
    if (!existing) throw new NotFoundError("Monitoring record");

    const doneAt = new Date();
    const doneDuration = Math.round(
      (doneAt.getTime() - existing.date.getTime()) / (1000 * 60)
    );

    const monitoringDoneStatusId = await getModuleDoneStatusId("MONITORING");

    const updateData: Record<string, unknown> = {
      done_at: doneAt,
      done_duration: doneDuration,
      statusOption: { connect: { id: monitoringDoneStatusId } },
    };
    if (body.time_start !== undefined) updateData.time_start = parseOptionalDatetime(body.time_start);
    if (body.time_accomplish !== undefined) updateData.time_accomplish = parseOptionalDatetime(body.time_accomplish);

    if (body.teams !== undefined) {
      await tx.monitoringTeam.deleteMany({ where: { record_id: id } });
      if (body.teams.length > 0) {
        await tx.monitoringTeam.createMany({
          data: body.teams.map((tid: number) => ({ record_id: id, technician_id: tid })),
        });
      }
    }

    const updated = await tx.monitoringRecord.update({
      where: { id, done_at: null },
      data: updateData,
      include: monitoringInclude,
    }).catch((e) => {
      if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === "P2025") {
        throw new BadRequestError("Record is already marked as Done.");
      }
      throw e;
    });

    if (body.jobDetail && Object.keys(body.jobDetail).length > 0) {
      const completionData = buildJobDetailData(body.jobDetail as Record<string, unknown>);
      if (Object.keys(completionData).length > 0) {
        const existingDetail = await tx.jobDetail.findUnique({ where: { record_id: id } });
        if (existingDetail) {
          await tx.jobDetail.update({ where: { record_id: id }, data: completionData });
        } else {
          await tx.jobDetail.create({ data: { record_id: id, ...completionData } });
        }
      }
    }

    const dispatch = await autoDispatch(
      {
        monitoringRecord: {
          id: existing.id,
          date: existing.date,
          client: existing.client,
          address: existing.address,
          contact_number: existing.contact_number,
          concern: existing.concern || "",
          sales_agent: existing.sales_agent,
          type_id: existing.type_id,
          chat_type_id: existing.chat_type_id,
          source_tab: existing.tab_type,
          latitude: existing.latitude,
          longitude: existing.longitude,
          ticket_number: existing.ticket_number,
          actions_taken: existing.actions_taken,
          remarks: existing.remarks,
          csr_id: existing.csr_id,
          customer_id: existing.customer_id,
          status_id: monitoringDoneStatusId,
          time_start: body.time_start !== undefined ? (body.time_start ? new Date(body.time_start) : null) : existing.time_start,
          time_accomplish: body.time_accomplish !== undefined ? (body.time_accomplish ? new Date(body.time_accomplish) : null) : existing.time_accomplish,
          done_at: doneAt,
          done_duration: doneDuration,
        },
      },
      tx
    );

    await writeAudit(tx, {
      action: "UPDATE",
      entity_type: "MonitoringRecord",
      entity_id: id,
      actor_id: req.user!.id,
      summary: `Marked ${existing.tab_type} record for ${existing.client} as Done`,
      before: existing,
      after: updated,
    });

    emitEntityChanged("monitoringRecord:changed", id);
    emitEntityChanged("dispatch:changed", dispatch.id);
    emitAuditChanged();

    return { record: updated, dispatch };
  });

  res.json({ success: true, data: result });
}

export async function cancelMonitoringRecord(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const body = CancelMonitoringSchema.parse(req.body);

  const result = await prisma.$transaction(async (tx) => {
    const existing = await tx.monitoringRecord.findFirst({
      where: { id, deleted_at: null },
      include: { csr: { select: csrPublicSelect }, teams: true },
    });
    if (!existing) throw new NotFoundError("Monitoring record");

    const doneAt = new Date();
    const doneDuration = Math.round(
      (doneAt.getTime() - existing.date.getTime()) / (1000 * 60)
    );

    const monitoringDoneStatusId = await getModuleDoneStatusId("MONITORING");

    const cancelledStatusId = await getCancelledDispatchStatusId();

    const updated = await tx.monitoringRecord.update({
      where: { id, done_at: null },
      data: {
        done_at: doneAt,
        done_duration: doneDuration,
        statusOption: { connect: { id: monitoringDoneStatusId } },
      },
      include: monitoringInclude,
    }).catch((e) => {
      if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === "P2025") {
        throw new BadRequestError("Record is already completed.");
      }
      throw e;
    });

    const dispatch = await autoDispatch(
      {
        monitoringRecord: {
          id: existing.id,
          date: existing.date,
          client: existing.client,
          address: existing.address,
          contact_number: existing.contact_number,
          concern: existing.concern || "",
          sales_agent: existing.sales_agent,
          type_id: existing.type_id,
          chat_type_id: existing.chat_type_id,
          source_tab: existing.tab_type,
          latitude: existing.latitude,
          longitude: existing.longitude,
          ticket_number: existing.ticket_number,
          actions_taken: existing.actions_taken,
          remarks: existing.remarks,
          csr_id: existing.csr_id,
          customer_id: existing.customer_id,
          status_id: monitoringDoneStatusId,
          time_start: existing.time_start,
          time_accomplish: existing.time_accomplish,
          done_at: doneAt,
          done_duration: doneDuration,
        },
        overrides: {
          status_id: cancelledStatusId,
          remarks: body.reason,
        },
      },
      tx
    );

    await writeAudit(tx, {
      action: "UPDATE",
      entity_type: "MonitoringRecord",
      entity_id: id,
      actor_id: req.user!.id,
      summary: `Cancelled ${existing.tab_type} record for ${existing.client}`,
      before: existing,
      after: updated,
    });

    emitEntityChanged("monitoringRecord:changed", id);
    emitEntityChanged("dispatch:changed", dispatch.id);
    emitAuditChanged();

    return { record: updated, dispatch };
  });

  res.json({ success: true, data: result });
}

export async function deleteMonitoringRecord(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const { confirm_name } = req.body;

  await prisma.$transaction(async (tx) => {
    const existing = await tx.monitoringRecord.findFirst({
      where: { id, deleted_at: null },
      include: { teams: { include: { technician: true } }, csr: { select: csrPublicSelect } },
    });
    if (!existing) throw new NotFoundError("Monitoring record");

    if (confirm_name !== existing.client) {
      throw new BadRequestError("Client name does not match");
    }

    if (existing.done_at) {
      throw new ForbiddenError(
        "Cannot delete a completed record. Delete the linked Dispatch entry first."
      );
    }

    const deleted = await tx.monitoringRecord.update({
      where: { id },
      data: { deleted_at: new Date() },
    });

    await writeAudit(tx, {
      action: "DELETE",
      entity_type: "MonitoringRecord",
      entity_id: id,
      actor_id: req.user!.id,
      summary: `Deleted ${existing.tab_type} record for ${existing.client}`,
      before: existing,
      after: deleted,
    });

    emitEntityChanged("monitoringRecord:changed", id);
    emitAuditChanged();
  });

  res.json({ success: true, message: "Monitoring record deleted" });
}