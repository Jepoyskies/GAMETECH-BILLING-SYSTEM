import { Request, Response } from "express";
import prisma from "../lib/prisma";
import { NotFoundError, BadRequestError } from "../lib/errors";
import { computeDuration, parseIdParam } from "../lib/utils";
import { writeAudit } from "../lib/audit";
import { resolveCustomerLink } from "../lib/customer";
import { csrPublicSelect } from "../lib/select";
import { assertActiveOption } from "../lib/configOptions";
import {
  UpdateDispatchSchema,
  DispatchQuerySchema,
} from "../lib/validators";
import {
  buildDateRangeFilter,
  buildDoneAtRangeFilter,
  buildTimeStartRangeFilter,
  buildTextContainsFilter,
  buildTicketNumberFilter,
  buildTeamFilter,
} from "../lib/queryFilters";
import { emitAuditChanged, emitEntityChanged } from "../lib/socket";
const toMinute = (v: unknown): number | null => {
  if (v instanceof Date && !isNaN(v.getTime())) {
    return Math.floor(v.getTime() / 60000);
  }
  if (typeof v === "string") {
    const ms = Date.parse(v);
    if (!isNaN(ms)) return Math.floor(ms / 60000);
  }
  return null;
};

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

const hasChanged = (oldVal: unknown, newVal: unknown): boolean => {
  const oldMinute = toMinute(oldVal);
  const newMinute = toMinute(newVal);
  if (oldMinute !== null && newMinute !== null) {
    return oldMinute !== newMinute;
  }
  const normalize = (v: unknown) =>
    v === null || v === undefined || v === "" ? null : v;
  return normalize(oldVal) !== normalize(newVal);
};

export async function listDispatches(req: Request, res: Response) {
  const query = DispatchQuerySchema.parse(req.query);
  const {
    status_id,
    type_id,
    source_tab,
    chat_type_id,
    csr,
    client,
    ticket_number,
    job_details,
    address,
    teams,
    date_from,
    date_to,
    done_from,
    done_to,
    time_start_from,
    time_start_to,
    sort_by,
    cursor,
    limit,
  } = query;

  const clientFilter = buildTextContainsFilter(client);
  const ticketNumberFilter = buildTicketNumberFilter(ticket_number);
  const jobDetailsFilter = buildTextContainsFilter(job_details);
  const addressFilter = buildTextContainsFilter(address);
  const teamFilter = buildTeamFilter(teams);

  const where: Record<string, unknown> = {
    deleted_at: null,
    ...(source_tab && { source_tab }),
    ...(csr && { csr_id: csr }),
    ...(clientFilter && { client: clientFilter }),
    ...(ticketNumberFilter && { ticket_number: ticketNumberFilter }),
    ...(jobDetailsFilter && {
      OR: [
        { monitoring: { jobDetail: { job_order: jobDetailsFilter } } },
        { monitoring: { jobDetail: { account_no: jobDetailsFilter } } },
      ],
    }),
    ...(addressFilter && {
      OR: [
        { address: addressFilter },
        { monitoring: { jobDetail: { barangay_city: addressFilter } } },
      ],
    }),
    ...buildDateRangeFilter(date_from, date_to),
    ...buildDoneAtRangeFilter(done_from, done_to),
    ...buildTimeStartRangeFilter(time_start_from, time_start_to),
    ...(teamFilter ?? {}),
  };

  if (status_id) where.status_id = status_id;
  if (type_id) where.type_id = type_id;
  if (chat_type_id) where.chat_type_id = chat_type_id;

  const orderBy: Record<string, unknown>[] =
    sort_by === "done_at"
      ? [{ done_at: { sort: "desc", nulls: "last" } }, { id: "desc" }]
      : [{ date: "desc" }, { created_at: "desc" }, { id: "desc" }];

  const records = await prisma.dispatch.findMany({
    where,
    include: {
      statusOption: true,
      typeOption: true,
      chatTypeOption: true,
      teams: { include: { technician: true } },
      csr: { select: csrPublicSelect },
      customer: true,
      monitoring: { include: { jobDetail: true } },
    },
    orderBy,
    ...(cursor ? { cursor: { id: cursor }, skip: 1 } : {}),
    take: limit + 1,
  });

  const hasNext = records.length > limit;
  const data = hasNext ? records.slice(0, limit) : records;
  const nextCursor = hasNext ? data[data.length - 1].id : null;

  res.json({
    success: true,
    data,
    pagination: {
      next_cursor: nextCursor,
      has_next: hasNext,
      limit,
    },
  });
}

export async function getDispatch(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);

  const record = await prisma.dispatch.findFirst({
    where: { id, deleted_at: null },
    include: {
      statusOption: true,
      typeOption: true,
      chatTypeOption: true,
      teams: { include: { technician: true } },
      csr: { select: csrPublicSelect },
      customer: true,
      monitoring: { include: { jobDetail: true } },
    },
  });

  if (!record) throw new NotFoundError("Dispatch");

  res.json({ success: true, data: record });
}

export async function updateDispatch(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const body = UpdateDispatchSchema.parse(req.body);

  if (body.status_id !== undefined) await assertActiveOption("STATUS", "DISPATCH", body.status_id);
  if (body.type_id !== undefined) await assertActiveOption("TYPE", "DISPATCH", body.type_id);
  if (body.chat_type_id !== undefined) await assertActiveOption("CHAT_TYPE", "DISPATCH", body.chat_type_id);

  const { teams, time_start, time_accomplish, done_at, time, csr, customer_id, jobDetail, ...rest } = body;

  const tsStart = time_start ? new Date(time_start) : time_start === null ? null : undefined;
  const tsAccomplish = time_accomplish ? new Date(time_accomplish) : time_accomplish === null ? null : undefined;
  const tsDone = done_at ? new Date(done_at) : done_at === null ? null : undefined;
  const duration =
    tsStart !== undefined || tsAccomplish !== undefined
      ? computeDuration(tsStart ?? null, tsAccomplish ?? null)
      : undefined;

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

  const updated = await prisma.$transaction(async (tx) => {
    const existing = await tx.dispatch.findFirst({
      where: { id, deleted_at: null },
      include: {
        statusOption: true,
        typeOption: true,
        chatTypeOption: true,
        teams: { include: { technician: true } },
        csr: { select: csrPublicSelect },
        customer: true,
        monitoring: { include: { jobDetail: true } },
      },
    });
    if (!existing) throw new NotFoundError("Dispatch");

    const doneDuration = tsDone !== undefined
      ? computeDuration(existing.date, tsDone)
      : undefined;

    const data: Record<string, unknown> = {};

    if (dateValue !== undefined && hasChanged(existing.date, dateValue)) data.date = dateValue;
    if (rest.client !== undefined && hasChanged(existing.client, rest.client)) data.client = rest.client;
    if (rest.address !== undefined && hasChanged(existing.address, rest.address)) data.address = rest.address;
    if (rest.contact_number !== undefined && hasChanged(existing.contact_number, rest.contact_number)) data.contact_number = rest.contact_number;
    if (rest.concern !== undefined && hasChanged(existing.concern, rest.concern || "")) data.concern = rest.concern || "";
    if (rest.sales_agent !== undefined && hasChanged(existing.sales_agent, rest.sales_agent || "")) data.sales_agent = rest.sales_agent || "";
    if (rest.chat_type_id !== undefined && hasChanged(existing.chat_type_id, rest.chat_type_id)) data.chat_type_id = rest.chat_type_id;
    if (rest.type_id !== undefined && hasChanged(existing.type_id, rest.type_id)) data.type_id = rest.type_id;
    if (rest.status_id !== undefined && existing.status_id !== rest.status_id) data.status_id = rest.status_id;
    if (rest.remarks !== undefined && hasChanged(existing.remarks, rest.remarks ?? null)) data.remarks = rest.remarks ?? null;
    if (rest.latitude !== undefined && hasChanged(existing.latitude, rest.latitude)) data.latitude = rest.latitude;
    if (rest.longitude !== undefined && hasChanged(existing.longitude, rest.longitude)) data.longitude = rest.longitude;
    if (rest.source_tab !== undefined && hasChanged(existing.source_tab, rest.source_tab)) data.source_tab = rest.source_tab;
    if (rest.ticket_number !== undefined && hasChanged(existing.ticket_number, rest.ticket_number ?? null)) data.ticket_number = rest.ticket_number ?? null;
    if (rest.actions_taken !== undefined && hasChanged(existing.actions_taken, rest.actions_taken ?? null)) data.actions_taken = rest.actions_taken ?? null;
    if (tsStart !== undefined && hasChanged(existing.time_start, tsStart)) data.time_start = tsStart;
    if (tsAccomplish !== undefined && hasChanged(existing.time_accomplish, tsAccomplish)) data.time_accomplish = tsAccomplish;
    if (duration !== undefined && hasChanged(existing.duration, duration)) data.duration = duration;
    if (tsDone !== undefined && hasChanged(existing.done_at, tsDone)) data.done_at = tsDone;
    if (doneDuration !== undefined && hasChanged(existing.done_duration, doneDuration)) data.done_duration = doneDuration;
    if (csr !== undefined && existing.csr_id !== csr) data.csr = { connect: { id: csr } };

    const existingJobDetail = existing.monitoring?.jobDetail;
    const customerIdChanged = customer_id !== undefined && customer_id !== existing.customer_id;
    if (customer_id === null && existing.customer_id !== null) {
      data.customer = { disconnect: true };
    } else if (customerIdChanged) {
      const resolvedCustomerId = await resolveCustomerLink(tx, {
        customerId: customer_id ?? existing.customer_id,
        updateCustomer: true,
        snapshot: {
          name: rest.client ?? existing.client,
          address: rest.address ?? existing.address,
          contact_number: rest.contact_number ?? existing.contact_number,
          email: jobDetail?.email_address ?? existingJobDetail?.email_address ?? undefined,
          barangay_city: jobDetail?.barangay_city ?? existingJobDetail?.barangay_city ?? undefined,
          latitude: rest.latitude !== undefined ? rest.latitude : existing.latitude,
          longitude: rest.longitude !== undefined ? rest.longitude : existing.longitude,
        },
        actorId: req.user!.id,
        allowAutoCreate: false,
      });
      if (resolvedCustomerId !== undefined) {
        data.customer = { connect: { id: resolvedCustomerId } };
      }
    } else if (existing.customer_id) {
      const infoFieldsChanged =
        (rest.client !== undefined && hasChanged(existing.client, rest.client)) ||
        (rest.address !== undefined && hasChanged(existing.address, rest.address)) ||
        (rest.contact_number !== undefined && hasChanged(existing.contact_number, rest.contact_number)) ||
        (rest.latitude !== undefined && hasChanged(existing.latitude, rest.latitude)) ||
        (rest.longitude !== undefined && hasChanged(existing.longitude, rest.longitude)) ||
        (jobDetail?.email_address !== undefined && hasChanged(existingJobDetail?.email_address ?? null, jobDetail.email_address)) ||
        (jobDetail?.barangay_city !== undefined && hasChanged(existingJobDetail?.barangay_city ?? null, jobDetail.barangay_city));

      if (infoFieldsChanged) {
        await resolveCustomerLink(tx, {
          customerId: existing.customer_id,
          updateCustomer: true,
          snapshot: {
            name: rest.client ?? existing.client,
            address: rest.address ?? existing.address,
            contact_number: rest.contact_number ?? existing.contact_number,
            email: jobDetail?.email_address ?? existingJobDetail?.email_address ?? undefined,
            barangay_city: jobDetail?.barangay_city ?? existingJobDetail?.barangay_city ?? undefined,
            latitude: rest.latitude !== undefined ? rest.latitude : existing.latitude,
            longitude: rest.longitude !== undefined ? rest.longitude : existing.longitude,
          },
          actorId: req.user!.id,
          allowAutoCreate: false,
        });
      }
    }

    if (teams !== undefined) {
      const oldTeamIds = existing.teams.map((t) => t.technician_id).sort();
      const newTeamIds = [...teams].sort();
      const teamsChanged =
        oldTeamIds.length !== newTeamIds.length ||
        oldTeamIds.some((id, i) => id !== newTeamIds[i]);

      if (teamsChanged) {
        await tx.dispatchTeam.deleteMany({ where: { dispatch_id: id } });
        if (teams.length > 0) {
          data.teams = {
            create: teams.map((technician_id) => ({ technician_id })),
          };
        }
      }
    }

    if (jobDetail !== undefined) {
      const jobDetailData = buildJobDetailData(jobDetail as Record<string, unknown>);
      if (Object.keys(jobDetailData).length > 0 && existing.monitoring_id) {
        await tx.jobDetail.upsert({
          where: { record_id: existing.monitoring_id },
          create: { record_id: existing.monitoring_id, ...jobDetailData },
          update: jobDetailData,
        });
      }
    }

    const result = await tx.dispatch.update({
      where: { id, deleted_at: null },
      data,
      include: {
        statusOption: true,
        typeOption: true,
        chatTypeOption: true,
        teams: { include: { technician: true } },
        csr: { select: csrPublicSelect },
        customer: true,
        monitoring: { include: { jobDetail: true } },
      },
    });

    if (tsDone !== undefined && existing.monitoring_id) {
      const monitoringData: Record<string, unknown> = {};
      if (hasChanged(existing.monitoring?.done_at ?? null, tsDone)) {
        monitoringData.done_at = tsDone;
      }
      if (doneDuration !== undefined && hasChanged(existing.monitoring?.done_duration ?? null, doneDuration)) {
        monitoringData.done_duration = doneDuration;
      }
      if (Object.keys(monitoringData).length > 0) {
        await tx.monitoringRecord.update({
          where: { id: existing.monitoring_id },
          data: monitoringData,
        });
      }
    }

    await writeAudit(tx, {
      action: "UPDATE",
      entity_type: "Dispatch",
      entity_id: id,
      actor_id: req.user!.id,
      summary: `Updated dispatch for ${result.client}`,
      before: existing,
      after: result,
    });

    emitEntityChanged("dispatch:changed", id);
    emitAuditChanged();

    return result;
  });

  res.json({ success: true, data: updated });
}

export async function deleteDispatch(req: Request, res: Response) {
  const id = parseIdParam(req.params.id);
  const { confirm_name } = req.body;

  await prisma.$transaction(async (tx) => {
    const existing = await tx.dispatch.findFirst({
      where: { id, deleted_at: null },
      include: {
        statusOption: true,
        typeOption: true,
        chatTypeOption: true,
        teams: { include: { technician: true } },
        csr: { select: csrPublicSelect },
        customer: true,
      },
    });
    if (!existing) throw new NotFoundError("Dispatch");

    if (confirm_name !== existing.client) {
      throw new BadRequestError("Client name does not match");
    }

    const deleted = await tx.dispatch.update({
      where: { id },
      data: { deleted_at: new Date() },
    });

    await writeAudit(tx, {
      action: "DELETE",
      entity_type: "Dispatch",
      entity_id: id,
      actor_id: req.user!.id,
      summary: `Deleted dispatch for ${existing.client}`,
      before: existing,
      after: deleted,
    });

    emitEntityChanged("dispatch:changed", id);
    emitAuditChanged();
  });

  res.json({ success: true, message: "Dispatch deleted" });
}