import { Headphones } from "lucide-react";
import MonitoringListPage from "../components/MonitoringListPage";

const pendingColumnKeys = ["actions", "statusOption", "date", "ticket_number", "client", "concern", "typeOption", "csr", "actions_taken", "address", "contact_number", "schedule_date", "schedule_time", "remarks"];
const ongoingColumnKeys = ["actions", "statusOption", "date", "ticket_number", "client", "concern", "typeOption", "time_start", "time_accomplish", "teams", "csr", "actions_taken", "address", "contact_number", "remarks"];

export default function ClientConcerns() {
  return (
    <MonitoringListPage
      tabType="CLIENT_CONCERNS"
      title="Client Concerns"
      icon={Headphones}
      newButtonLabel="+ New Concern"
      pendingColumnKeys={pendingColumnKeys}
      ongoingColumnKeys={ongoingColumnKeys}
    />
  );
}