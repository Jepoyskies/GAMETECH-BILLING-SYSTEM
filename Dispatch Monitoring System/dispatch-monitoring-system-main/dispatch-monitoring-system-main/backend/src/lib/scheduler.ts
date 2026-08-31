import { schedule, ScheduledTask } from "node-cron";
import { createBackup } from "./backup";
import logger from "./logger";

let hourlyTask: ScheduledTask | null = null;
let dailyTask: ScheduledTask | null = null;

export function startScheduler(): void {
  hourlyTask = schedule("0 * * * *", async () => {
    logger.info("Starting hourly incremental backup...");
    const result = await createBackup("HOURLY", "SCHEDULED");
    if (result.success) {
      logger.info({ filename: result.filename, fileSize: result.fileSize }, "Hourly backup completed");
    } else {
      logger.error({ error: result.error }, "Hourly backup failed");
    }
  });

  dailyTask = schedule("0 2 * * *", async () => {
    logger.info("Starting daily full backup...");
    const result = await createBackup("FULL", "SCHEDULED");
    if (result.success) {
      logger.info({ filename: result.filename, fileSize: result.fileSize }, "Daily full backup completed");
    } else {
      logger.error({ error: result.error }, "Daily full backup failed");
    }
  });

  logger.info("Backup scheduler started (hourly at :00, daily at 02:00)");
}

export function stopScheduler(): void {
  if (hourlyTask) {
    hourlyTask.stop();
    hourlyTask = null;
  }
  if (dailyTask) {
    dailyTask.stop();
    dailyTask = null;
  }
  logger.info("Backup scheduler stopped");
}
