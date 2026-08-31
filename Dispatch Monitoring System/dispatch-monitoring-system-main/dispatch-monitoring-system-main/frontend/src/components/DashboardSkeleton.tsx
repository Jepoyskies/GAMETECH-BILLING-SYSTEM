export default function DashboardSkeleton() {
  return (
    <>
      <div className="dashboard-section">
        <div className="skeleton skeleton-section-title" />
        <div className="kpi-grid kpi-grid--4">
          <div className="skeleton skeleton-kpi" />
          <div className="skeleton skeleton-kpi" />
          <div className="skeleton skeleton-kpi" />
          <div className="skeleton skeleton-kpi" />
        </div>
      </div>

      <div className="dashboard-section">
        <div className="skeleton skeleton-section-title" />
        <div className="overview-layout">
          <div className="kpi-stack">
            <div className="skeleton skeleton-kpi" />
            <div className="skeleton skeleton-kpi" />
            <div className="skeleton skeleton-kpi" />
            <div className="skeleton skeleton-kpi" />
          </div>
          <div className="skeleton skeleton-donut" />
        </div>
      </div>

      <div className="dashboard-section">
        <div className="skeleton skeleton-section-title" />
        <div className="monitoring-summary-grid">
          <div className="skeleton skeleton-monitoring-card" />
          <div className="skeleton skeleton-monitoring-card" />
          <div className="skeleton skeleton-monitoring-card" />
        </div>
      </div>

      <div className="dashboard-section">
        <div className="skeleton skeleton-section-title" />
        <div className="skeleton skeleton-chart" />
      </div>

      <div className="dashboard-section">
        <div className="skeleton skeleton-section-title" />
        <div className="skeleton skeleton-table" />
      </div>

      <div className="dashboard-section">
        <div className="skeleton skeleton-section-title" />
        <div className="skeleton skeleton-table" />
      </div>
    </>
  );
}
