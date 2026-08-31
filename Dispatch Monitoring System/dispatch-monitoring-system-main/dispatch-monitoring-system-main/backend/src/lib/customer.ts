import { Prisma } from "@prisma/client";

type TransactionClient = Prisma.TransactionClient;

export interface CustomerSnapshot {
  name: string;
  address: string;
  contact_number: string;
  account_number?: string | null;
  email?: string | null;
  barangay_city?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

interface ResolveCustomerLinkInput {
  customerId?: number | null;
  updateCustomer?: boolean;
  snapshot: CustomerSnapshot;
  actorId: number;
  allowAutoCreate: boolean;
}

export function snapshotDiffersFromMaster(
  snapshot: CustomerSnapshot,
  master: {
    name: string;
    address: string;
    contact_number: string;
    account_number: string | null;
    email: string | null;
    barangay_city: string | null;
    latitude: number | null;
    longitude: number | null;
  }
): boolean {
  const coordsDiffer =
    (snapshot.latitude !== undefined && snapshot.latitude !== master.latitude) ||
    (snapshot.longitude !== undefined && snapshot.longitude !== master.longitude);
  const emailDiffers =
    snapshot.email !== undefined && snapshot.email !== master.email;
  const brgyDiffers =
    snapshot.barangay_city !== undefined && snapshot.barangay_city !== master.barangay_city;
  const acctDiffers =
    snapshot.account_number !== undefined && snapshot.account_number !== master.account_number;
  return (
    snapshot.name.trim() !== master.name.trim() ||
    snapshot.address.trim() !== master.address.trim() ||
    snapshot.contact_number.trim() !== master.contact_number.trim() ||
    coordsDiffer ||
    emailDiffers ||
    brgyDiffers ||
    acctDiffers
  );
}

export async function resolveCustomerLink(
  tx: TransactionClient,
  input: ResolveCustomerLinkInput
): Promise<number | undefined> {
  const { customerId, updateCustomer, snapshot, allowAutoCreate } = input;

  const existing =
    customerId && customerId > 0
      ? await tx.customer.findFirst({ where: { id: customerId, deleted_at: null } })
      : null;

  if (!existing) {
    if (!allowAutoCreate) return undefined;

    const created = await tx.customer.create({
      data: {
        name: snapshot.name,
        address: snapshot.address,
        contact_number: snapshot.contact_number,
        ...(snapshot.account_number !== undefined && { account_number: snapshot.account_number }),
        ...(snapshot.email !== undefined && { email: snapshot.email }),
        ...(snapshot.barangay_city !== undefined && { barangay_city: snapshot.barangay_city }),
        ...(snapshot.latitude !== undefined && { latitude: snapshot.latitude }),
        ...(snapshot.longitude !== undefined && { longitude: snapshot.longitude }),
      },
    });
    return created.id;
  }

  if (updateCustomer) {
    const data: Record<string, unknown> = {};
    if (snapshot.name !== undefined) data.name = snapshot.name;
    if (snapshot.address !== undefined) data.address = snapshot.address;
    if (snapshot.contact_number !== undefined) data.contact_number = snapshot.contact_number;
    if (snapshot.account_number !== undefined) data.account_number = snapshot.account_number;
    if (snapshot.email !== undefined) data.email = snapshot.email;
    if (snapshot.barangay_city !== undefined) data.barangay_city = snapshot.barangay_city;
    if (snapshot.latitude !== undefined) data.latitude = snapshot.latitude;
    if (snapshot.longitude !== undefined) data.longitude = snapshot.longitude;

    if (Object.keys(data).length > 0) {
      await tx.customer.updateMany({
        where: {
          id: existing.id,
          name: existing.name,
          address: existing.address,
          contact_number: existing.contact_number,
        },
        data,
      });
    }
  }

  return existing.id;
}