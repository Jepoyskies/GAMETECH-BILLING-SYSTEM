import prisma from "./prisma";
import { ValidationError } from "./errors";
import type { ConfigListType, ConfigListModule } from "@prisma/client";
import logger from "./logger";

export function tabTypeToConfigModule(tabType: string): ConfigListModule {
  switch (tabType) {
    case "INTERNET_INSTALL":
    case "CIGNAL_PLAY":
    case "CLIENT_CONCERNS":
      return "DISPATCH";
    case "DISPATCH":
      return "DISPATCH";
    default: throw new ValidationError(`Unknown tab type: ${tabType}`);
  }
}

export async function getOptionId(
  list_type: ConfigListType,
  module: ConfigListModule,
  label: string
): Promise<number> {
  const opt = await prisma.configOption.findFirst({
    where: { list_type, module, label: { equals: label, mode: "insensitive" } },
  });
  if (!opt) throw new ValidationError(`Required config option not found: ${label} (${list_type}/${module}). Please seed the database.`);
  return opt.id;
}

export async function assertActiveOption(
  list_type: ConfigListType,
  module: ConfigListModule,
  id: number
): Promise<void> {
  const opt = await prisma.configOption.findFirst({ where: { id, list_type, active: true } });
  if (!opt) throw new ValidationError(`Invalid ${list_type.toLowerCase()} option for ${module}`);
  if (opt.module !== module) {
    logger.warn({ option: opt.label, id: opt.id, actualModule: opt.module, expectedModule: module }, "Config option module mismatch");
  }
}