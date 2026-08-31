import { PrismaClient } from "@prisma/client";

type Module = "DISPATCH" | "MONITORING";
type ListType = "STATUS" | "TYPE" | "CHAT_TYPE";

const STATUS_COLORS: Record<string, string> = {
  "Resched":          "#8b5cf6",
  "Transition":       "#0ea5e9",
  "Cancelled":        "#ef4444",
  "Incorrect Number": "#dc2626",
  "PROSPECT":         "#0d9488",

  "For Follow Up": "#ec4899",
  "Resched ":      "#8b5cf6",
  "No action yet": "#94a3b8",
};

const TYPE_COLORS: Record<string, string> = {
  "Transition":        "#0ea5e9",
  "Mainline Repair":   "#dc2626",
  "OSP":               "#7c3aed",
  "PULL_OUT":          "#64748b",
  "Configuration":     "#f59e0b",
  "Technical Support": "#8b5cf6",
};

const DISPATCH_TYPE_LABELS = [
  "Transition",
  "Mainline Repair",
  "OSP",
  "PULL_OUT",
  "Configuration",
  "Technical Support",
];

interface StatusSeed {
  label: string;
  dispatch_equivalent?: string;
}

const MONITORING_STATUS_LABELS: StatusSeed[] = [
  { label: "Resched" },
  { label: "Transition" },
  { label: "Incorrect Number" },
  { label: "PROSPECT" },
  { label: "For Follow Up" },
  { label: "No action yet" },
];

const SEED_CONFIG: {
  list_type: ListType;
  module: Module;
  statuses?: StatusSeed[];
  labels?: string[];
  colors: Record<string, string>;
}[] = [
  { list_type: "TYPE", module: "DISPATCH", colors: TYPE_COLORS,
    labels: DISPATCH_TYPE_LABELS },
  { list_type: "STATUS", module: "MONITORING", colors: STATUS_COLORS,
    statuses: MONITORING_STATUS_LABELS },
];

const prisma = new PrismaClient();

async function seedStatusList(
  module: Module,
  statuses: StatusSeed[],
  colors: Record<string, string>
) {
  for (let i = 0; i < statuses.length; i++) {
    const { label, dispatch_equivalent } = statuses[i];
    const existing = await prisma.configOption.findFirst({
      where: { list_type: "STATUS", module, label: { equals: label, mode: "insensitive" } },
    });
    if (existing) continue;
    const created = await prisma.configOption.create({
      data: {
        list_type: "STATUS",
        module,
        label,
        color: colors[label] ?? "#64748b",
        sort_order: i,
      },
    });

    if (dispatch_equivalent) {
      const target = await prisma.configOption.findFirst({
        where: { list_type: "STATUS", module: "DISPATCH", label: { equals: dispatch_equivalent, mode: "insensitive" } },
      });
      if (target) {
        await prisma.configOption.update({
          where: { id: created.id },
          data: { dispatch_equivalent_id: target.id },
        });
      }
    }
  }
}

async function seedPlainList(
  list_type: ListType,
  module: Module,
  labels: string[],
  colors: Record<string, string>
) {
  for (let i = 0; i < labels.length; i++) {
    const label = labels[i];
    const existing = await prisma.configOption.findFirst({
      where: { list_type, module, label: { equals: label, mode: "insensitive" } },
    });
    if (existing) continue;
    await prisma.configOption.create({
      data: { list_type, module, label, color: colors[label] ?? "#64748b", sort_order: i },
    });
  }
}

async function main() {
  for (const entry of SEED_CONFIG) {
    if (entry.statuses) {
      await seedStatusList(entry.module, entry.statuses, entry.colors);
    } else if (entry.labels) {
      await seedPlainList(entry.list_type, entry.module, entry.labels, entry.colors);
    }
  }
  console.log("✓ Config options seeded.");
}

main().finally(() => prisma.$disconnect());