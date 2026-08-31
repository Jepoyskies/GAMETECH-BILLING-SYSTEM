import { useTechnicians } from "../hooks/useTechnician";
import { useTeams } from "../hooks/useTeams";
import type { Technician } from "../lib/types";

interface TechnicianTeamSelectorProps {
  selected: number[];
  onToggle: (techId: number) => void;
  onToggleMany?: (techIds: number[], select: boolean) => void;
  disabled?: boolean;
  idPrefix?: string;
}

export default function TechnicianTeamSelector({
  selected,
  onToggle,
  onToggleMany,
  disabled = false,
  idPrefix = "tech",
}: TechnicianTeamSelectorProps) {
  const { data: technicians } = useTechnicians();
  const { data: teams } = useTeams();

  const renderGroup = (label: string, key: string, members: Technician[]) => {
    if (members.length === 0) return null;
    const memberIds = members.map((m) => m.id);
    const allSelected = memberIds.every((id) => selected.includes(id));
    return (
      <div className="tech-team-group" key={key}>
        <div className="tech-team-group-header">
          <span className="tech-team-name">
            {label}
          </span>
          {onToggleMany && (
            <button
              type="button"
              className="link-like"
              disabled={disabled}
              onClick={() => onToggleMany(memberIds, !allSelected)}
            >
              {allSelected ? "Clear" : "Select all"}
            </button>
          )}
        </div>
        <div className="team-list">
          {members.map((tech) => (
            <div key={tech.id} className="team-checkbox">
              <input
                type="checkbox"
                id={`${idPrefix}-${tech.id}`}
                checked={selected.includes(tech.id)}
                onChange={() => onToggle(tech.id)}
                disabled={disabled}
              />
              <label htmlFor={`${idPrefix}-${tech.id}`}>{tech.name}</label>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const unassigned = technicians.filter((t) => t.team_id == null);

  return (
    <div className="tech-team-selector">
      {teams.map((team) =>
        renderGroup(
          team.name,
          `team-${team.id}`,
          technicians.filter((t) => t.team_id === team.id)
        )
      )}
      {renderGroup("Unassigned", "unassigned", unassigned)}
    </div>
  );
}