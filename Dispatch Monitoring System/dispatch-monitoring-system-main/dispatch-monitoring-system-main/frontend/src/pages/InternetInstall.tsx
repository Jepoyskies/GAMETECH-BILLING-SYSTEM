import { Wifi } from "lucide-react";
import MonitoringListPage from "../components/MonitoringListPage";

const pendingColumnKeys = ["actions", "statusOption", "date", "client", "concern", "chatTypeOption", "csr", "sales_agent", "address", "contact_number", "schedule_date", "schedule_time", "account_no", "job_order", "remarks"];
const ongoingColumnKeys = ["actions", "statusOption", "date", "client", "concern", "time_start", "time_accomplish", "teams", "chatTypeOption", "csr", "sales_agent", "address", "contact_number", "remarks"];

export default function InternetInstall() {
  return (
    <MonitoringListPage
      tabType="INTERNET_INSTALL"
      title="Internet Install"
      icon={Wifi}
      pendingColumnKeys={pendingColumnKeys}
      ongoingColumnKeys={ongoingColumnKeys}
    />
  );
}