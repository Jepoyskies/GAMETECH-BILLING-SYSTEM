import { prisma } from "./prisma";
import { Dispatch, Prisma } from "@prisma/client";
import { csrPublicSelect } from "./select";
import { getOptionId } from "./configOptions";
import { AppError } from "./errors";

type TransactionClient = Prisma.TransactionClient;

interface AutoDispatchInput {
  monitoringRecord: {
    id: number;
    date: Date;
    client: string;
    address: string;
    contact_number: string;
    concern: string;
    status_id: number;
    sales_agent: string | null;
    type_id: number | null;
    chat_type_id: number | null;
    source_tab: "INTERNET_INSTALL" | "CIGNAL_PLAY" | "CLIENT_CONCERNS";
    latitude?: number | null;
    longitude?: number | null;
    ticket_number: string | null;
    actions_taken: string | null;
    remarks: string | null;
    csr_id: number;
    customer_id?: number | null;
    time_start?: Date | null;
    time_accomplish?: Date | null;
    done_at?: Date | null;
    done_duration?: number | null;
  };
  overrides?: {
    status_id?: number;
    remarks?: string | null;
  };
}

function computeDuration(start?: Date | null, accomplish?: Date | null): number | null {
  if (!start || !accomplish) return null;
  return Math.round((accomplish.getTime() - start.getTime()) / (1000 * 60));
}

export async function autoDispatch(
  input: AutoDispatchInput,
  tx?: TransactionClient
): Promise<Dispatch> {
  const { monitoringRecord, overrides } = input;

  const duration = computeDuration(
    monitoringRecord.time_start,
    monitoringRecord.time_accomplish
  );

  let chatTypeId: number;
  if (monitoringRecord.chat_type_id) {
    chatTypeId = monitoringRecord.chat_type_id;
  } else {
    const fallbackLabel = monitoringRecord.source_tab === "CLIENT_CONCERNS"
      ? "Concern"
      : "Inquiry";
    chatTypeId = await getOptionId("CHAT_TYPE", "DISPATCH", fallbackLabel);
  }

  let dispatchTypeId: number;
  if (monitoringRecord.type_id) {
    const sourceType = await prisma.configOption.findUnique({
      where: { id: monitoringRecord.type_id },
    });
    dispatchTypeId = sourceType
      ? await getOptionId("TYPE", "DISPATCH", sourceType.label)
      : await getOptionId("TYPE", "DISPATCH", "Installation");
  } else {
    dispatchTypeId = await getOptionId("TYPE", "DISPATCH", "Installation");
  }

  let dispatchStatusId: number;
  if (overrides?.status_id) {
    dispatchStatusId = overrides.status_id;
  } else {
    dispatchStatusId = await getOptionId("STATUS", "DISPATCH", "Done");
  }

  const run = async (client: TransactionClient) => {
    const monitoringTeams = await client.monitoringTeam.findMany({
      where: { record_id: monitoringRecord.id },
      select: { technician_id: true },
    });
    const teamIds = monitoringTeams.map((t) => t.technician_id);

    const dispatchData = {
      date: monitoringRecord.date,
      client: monitoringRecord.client,
      address: monitoringRecord.address,
      contact_number: monitoringRecord.contact_number,
      concern: monitoringRecord.concern,
      sales_agent: monitoringRecord.sales_agent ?? "",
      chat_type_id: chatTypeId,
      type_id: dispatchTypeId,
      status_id: dispatchStatusId,
      source_tab: monitoringRecord.source_tab,
      ticket_number: monitoringRecord.ticket_number,
      actions_taken: monitoringRecord.actions_taken,
      remarks: overrides?.remarks !== undefined ? overrides.remarks : monitoringRecord.remarks,
      time_start: monitoringRecord.time_start ?? null,
      time_accomplish: monitoringRecord.time_accomplish ?? null,
      duration: duration,
      done_at: monitoringRecord.done_at ?? null,
      done_duration: monitoringRecord.done_duration ?? null,
      latitude: monitoringRecord.latitude ?? null,
      longitude: monitoringRecord.longitude ?? null,
      customer_id: monitoringRecord.customer_id ?? null,
      csr_id: monitoringRecord.csr_id,
    };

    const existingDispatch = await client.dispatch.findFirst({
      where: { monitoring_id: monitoringRecord.id, deleted_at: null },
    });

    let dispatch: Dispatch;

    if (existingDispatch) {
      dispatch = await client.dispatch.update({
        where: { id: existingDispatch.id },
        data: dispatchData,
        include: {
          statusOption: true,
          typeOption: true,
          chatTypeOption: true,
          teams: { include: { technician: true } },
          csr: { select: csrPublicSelect },
          monitoring: { include: { jobDetail: true } },
        },
      });

      await client.dispatchTeam.deleteMany({ where: { dispatch_id: existingDispatch.id } });
    } else {
      dispatch = await client.dispatch.create({
        data: {
          ...dispatchData,
          monitoring_id: monitoringRecord.id,
        },
        include: {
          statusOption: true,
          typeOption: true,
          chatTypeOption: true,
          teams: { include: { technician: true } },
          csr: { select: csrPublicSelect },
          monitoring: { include: { jobDetail: true } },
        },
      });
    }

    if (teamIds.length > 0) {
      await client.dispatchTeam.createMany({
        data: teamIds.map((technician_id) => ({
          dispatch_id: dispatch.id,
          technician_id,
        })),
      });
    }

    const updated = await client.dispatch.findUnique({
      where: { id: dispatch.id },
      include: {
        statusOption: true,
        typeOption: true,
        chatTypeOption: true,
        teams: { include: { technician: true } },
        csr: { select: csrPublicSelect },
        monitoring: { include: { jobDetail: true } },
      },
    });

    if (!updated) {
      throw new AppError(`Failed to retrieve dispatch ${dispatch.id} after creation`, 500);
    }

    return updated;
  };

  if (tx) return run(tx);
  return prisma.$transaction(run);
}