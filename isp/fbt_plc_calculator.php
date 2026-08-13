
<!DOCTYPE html>
<html>
  <head>
    <title>Mikrotik - Cloud</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="csrf-param" content="authenticity_token" />
<meta name="csrf-token" content="YOV_2wlJqnV7BL9JtMuX02K2zRw9YMZrAlndcs5q-cq3B7Ie-IUuRBaHV8shVp4zQCvksKF6yGf7RnNlfljJVg" />
    
    <script src="/assets/application-26ec2c55.js" type="module" data-turbo-track="reload" defer="defer"></script>
    


    <link rel="icon" href="/icon.png" type="image/png">
    <link rel="apple-touch-icon" href="/icon.png">

    <link rel="stylesheet" href="/assets/application-0bd925fc.css" data-turbo-track="reload" />

    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css">

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/css/bootstrap.min.css" rel="stylesheet">

    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/admin-lte@3.2/dist/css/adminlte.min.css">
    <meta name="sentry-trace" content="64d905f5b3654183869ff891c807f9c2-6857908252fa472c">
<meta name="baggage" content="sentry-trace_id=64d905f5b3654183869ff891c807f9c2,sentry-sample_rand=0.715446,sentry-environment=production,sentry-public_key=9ad401b41bc8a264416f7210b0a220a6">
  </head>

  <body class="hold-transition sidebar-mini layout-fixed" data-controller="pushmenu">
    
    <div class="wrapper">
      
<style>
  .splitter-hero {
    background: linear-gradient(135deg, #9f272b 0%, #06aedc 100%);
    color: white;
    padding: 1.5rem 0;
    text-align: center;
    position: relative;
    overflow: hidden;
  }

  .splitter-hero::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
    opacity: 0.5;
  }

  .splitter-hero-content {
    position: relative;
    z-index: 1;
  }

  .splitter-hero h1 {
    font-size: 1.75rem;
    font-weight: 800;
    margin-bottom: 0.5rem;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .splitter-hero p {
    font-size: 0.95rem;
    opacity: 0.95;
    max-width: 800px;
    margin: 0 auto;
  }

  .calculator-container {
    max-width: 1600px;
    margin: 0 auto;
    padding: 1.5rem 0;
    background: #f9fafb;
  }

  .config-panel {
    background: white;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .config-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
  }

  .config-item label {
    display: block;
    font-weight: 600;
    color: #374151;
    margin-bottom: 0.25rem;
    font-size: 0.8rem;
  }

  .config-item input {
    width: 100%;
    padding: 0.5rem;
    border: 2px solid #e5e7eb;
    border-radius: 6px;
    font-size: 0.875rem;
  }

  .config-item input:focus {
    outline: none;
    border-color: #06aedc;
  }

  /* Network Tree Builder */
  .network-builder {
    background: white;
    border-radius: 8px;
    padding: 1rem;
    min-height: 300px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .tree-node {
    margin-bottom: 1rem;
  }

  .node-card {
    background: white;
    border: 2px solid #e5e7eb;
    border-radius: 8px;
    padding: 0.75rem;
    position: relative;
    transition: all 0.3s ease;
  }

  .node-card:hover {
    border-color: #06aedc;
    box-shadow: 0 4px 12px rgba(6, 174, 220, 0.2);
  }

  .node-card.pon-node {
    background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    border-color: #f59e0b;
  }

  .node-card.plc-node {
    border-color: #06aedc;
    border-left-width: 4px;
  }

  .node-card.fbt-node {
    border-color: #9f272b;
    border-left-width: 4px;
  }

  .node-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .node-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #1f2937;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .node-icon {
    font-size: 1.1rem;
  }

  .node-power {
    font-size: 1rem;
    font-weight: 800;
  }

  .node-power.excellent { color: #10b981; }
  .node-power.good { color: #3b82f6; }
  .node-power.acceptable { color: #f59e0b; }
  .node-power.marginal { color: #ef4444; }
  .node-power.poor { color: #991b1b; }

  .node-details {
    display: flex;
    gap: 1rem;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
  }

  .node-detail-item {
    display: flex;
    flex-direction: column;
  }

  .node-detail-label {
    font-size: 0.65rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    font-weight: 600;
  }

  .node-detail-value {
    font-size: 0.8rem;
    font-weight: 700;
    color: #1f2937;
    margin-top: 0.15rem;
  }

  .node-actions {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .btn-add-splitter {
    background: linear-gradient(135deg, #06aedc 0%, #9f272b 100%);
    color: white;
    padding: 0.4rem 0.8rem;
    border: none;
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.8rem;
  }

  .btn-add-splitter:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(6, 174, 220, 0.4);
  }

  .btn-remove {
    background: #ef4444;
    color: white;
    padding: 0.3rem 0.6rem;
    border: none;
    border-radius: 4px;
    font-weight: 600;
    cursor: pointer;
    font-size: 0.75rem;
  }

  .btn-remove:hover {
    background: #dc2626;
  }

  /* Child nodes container - HORIZONTAL LAYOUT */
  .child-nodes {
    display: flex;
    gap: 0.75rem;
    margin-top: 0.75rem;
    padding-left: 1rem;
    flex-wrap: wrap;
  }

  .child-nodes .tree-node {
    flex: 1;
    min-width: 200px;
    margin-bottom: 0;
  }

  /* Modal */
  .modal-overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    z-index: 1000;
    align-items: center;
    justify-content: center;
  }

  .modal-overlay.active {
    display: flex;
  }

  .modal-content {
    background: white;
    border-radius: 12px;
    padding: 1.5rem;
    max-width: 900px;
    width: 90%;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    padding-bottom: 0.75rem;
    border-bottom: 2px solid #e5e7eb;
  }

  .modal-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #1f2937;
  }

  .modal-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: #6b7280;
    line-height: 1;
    padding: 0;
    width: 1.5rem;
    height: 1.5rem;
  }

  .modal-close:hover {
    color: #1f2937;
  }

  .splitter-type-tabs {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }

  .type-tab {
    flex: 1;
    padding: 0.75rem;
    border: 2px solid #e5e7eb;
    border-radius: 8px;
    background: white;
    cursor: pointer;
    text-align: center;
    transition: all 0.3s ease;
  }

  .type-tab:hover {
    border-color: #06aedc;
  }

  .type-tab.active {
    border-color: #06aedc;
    background: rgba(6, 174, 220, 0.1);
  }

  .type-tab.fbt-tab.active {
    border-color: #9f272b;
    background: rgba(159, 39, 43, 0.1);
  }

  .type-tab-title {
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
  }

  .type-tab-desc {
    font-size: 0.75rem;
    color: #6b7280;
  }

  .splitter-options {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 0.75rem;
  }

  .splitter-option {
    padding: 0.75rem;
    border: 2px solid #e5e7eb;
    border-radius: 8px;
    cursor: pointer;
    text-align: center;
    transition: all 0.3s ease;
    background: white;
  }

  .splitter-option:hover {
    border-color: #06aedc;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(6, 174, 220, 0.2);
  }

  .splitter-option-ratio {
    font-size: 1.1rem;
    font-weight: 800;
    color: #1f2937;
    margin-bottom: 0.25rem;
  }

  .splitter-option-loss {
    font-size: 0.7rem;
    color: #6b7280;
    margin-bottom: 0.15rem;
  }

  .splitter-option-desc {
    font-size: 0.65rem;
    color: #9ca3af;
  }

  @media (max-width: 768px) {
    .splitter-hero h1 {
      font-size: 1.5rem;
    }

    .splitter-hero p {
      font-size: 0.85rem;
    }

    .child-nodes {
      flex-direction: column;
      padding-left: 0.5rem;
    }

    .child-nodes .tree-node {
      min-width: 100%;
    }

    .config-grid {
      grid-template-columns: 1fr;
    }

    .splitter-options {
      grid-template-columns: repeat(2, 1fr);
    }

    .node-details {
      flex-direction: column;
      gap: 0.5rem;
    }

    .node-title {
      font-size: 0.85rem;
    }

    .node-power {
      font-size: 0.9rem;
    }
  }
</style>

<div class="splitter-hero">
  <div class="container">
    <div class="splitter-hero-content">
      <h1>🔌 Dynamic Fiber Network Calculator</h1>
      <p>Build your PON network with unlimited cascading | FBT Tap Couplers & PLC Splitters</p>
    </div>
  </div>
</div>

<div class="calculator-container">
  <div class="container-fluid">
    <!-- Breadcrumb -->
    <nav aria-label="breadcrumb" style="margin-bottom: 1rem;">
      <ol class="breadcrumb" style="background: transparent; padding: 0; font-size: 0.85rem;">
        <li class="breadcrumb-item">
          <a style="color: #06aedc; text-decoration: none;" href="/fiber_splitter_calculator">
            <i class="fas fa-calculator"></i> Tools
</a>        </li>
        <li class="breadcrumb-item">
          <a style="color: #06aedc; text-decoration: none;" href="/knowledge_base">
            <i class="fas fa-book-open"></i> Knowledge Base
</a>        </li>
        <li class="breadcrumb-item active" aria-current="page">Fiber Network Calculator</li>
      </ol>
    </nav>

    <!-- Configuration Panel -->
    <div class="config-panel">
      <div class="config-grid">
        <div class="config-item">
          <label for="ponPower">PON OLT Output Power (dBm)</label>
          <input type="number" id="ponPower" value="6" step="0.1" oninput="recalculateAll()">
        </div>
        <div class="config-item">
          <label for="defaultCableLoss">Default Cable Loss per Connection (dB)</label>
          <input type="number" id="defaultCableLoss" value="0.5" step="0.1" oninput="recalculateAll()">
        </div>
        <div class="config-item">
          <label>Network Statistics</label>
          <div style="padding: 0.5rem; background: #f3f4f6; border-radius: 6px;">
            <div style="font-size: 0.75rem; color: #6b7280;">
              Total Endpoints: <strong id="totalEndpoints">1</strong> |
              Avg Power: <strong id="avgPower">+6.0 dBm</strong>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Network Tree Builder -->
    <div class="network-builder">
      <div id="networkTree">
        <!-- PON Root Node -->
        <div class="tree-node" id="pon-root">
          <div class="node-card pon-node">
            <div class="node-header">
              <div class="node-title">
                <span class="node-icon">📡</span>
                <span>PON OLT</span>
              </div>
              <div class="node-power excellent" id="pon-power">+6.0 dBm</div>
            </div>
            <div class="node-details">
              <div class="node-detail-item">
                <span class="node-detail-label">Output Power</span>
                <span class="node-detail-value" id="pon-power-detail">+6.0 dBm</span>
              </div>
              <div class="node-detail-item">
                <span class="node-detail-label">Status</span>
                <span class="node-detail-value">🟢 Active</span>
              </div>
            </div>
            <div class="node-actions">
              <button class="btn-add-splitter" onclick="openSplitterModal('pon-root')">
                <span>➕</span>
                <span>Add Splitter / FBT</span>
              </button>
            </div>
          </div>
          <!-- Child splitters will be added here -->
          <div class="child-nodes" id="pon-root-children"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Splitter Selection Modal -->
<div class="modal-overlay" id="splitterModal">
  <div class="modal-content">
    <div class="modal-header">
      <h2 class="modal-title">Select Splitter Type</h2>
      <button class="modal-close" onclick="closeSplitterModal()">&times;</button>
    </div>

    <!-- Type Tabs -->
    <div class="splitter-type-tabs">
      <div class="type-tab active" onclick="switchSplitterTab('plc')">
        <div class="type-tab-title">PLC Splitter</div>
        <div class="type-tab-desc">Equal split, low loss</div>
      </div>
      <div class="type-tab fbt-tab" onclick="switchSplitterTab('fbt')">
        <div class="type-tab-title">FBT Tap Coupler</div>
        <div class="type-tab-desc">Tap ratios, flexible</div>
      </div>
    </div>

    <!-- PLC Options -->
    <div id="plc-options" class="splitter-options">
      <!-- Generated dynamically -->
    </div>

    <!-- FBT Options -->
    <div id="fbt-options" class="splitter-options" style="display: none;">
      <!-- Generated dynamically -->
    </div>
  </div>
</div>

<script>
  // Network tree data structure
  let networkTree = {
    root: {
      id: 'pon-root',
      type: 'pon',
      power: 6.0,
      children: []
    }
  };

  let nextNodeId = 1;
  let currentModalParent = null;
  let currentSplitterTab = 'plc';

  // Splitter configurations
  const splitterConfig = {
    plc: {
      '1:2': { ports: 2, loss: 3.3, desc: 'Low loss, 2 outputs' },
      '1:4': { ports: 4, loss: 6.8, desc: 'Medium density' },
      '1:8': { ports: 8, loss: 10.5, desc: 'Standard deployment' },
      '1:16': { ports: 16, loss: 13.7, desc: 'High density' },
      '1:32': { ports: 32, loss: 17.0, desc: 'Very high density' },
      '1:64': { ports: 64, loss: 20.5, desc: 'Maximum split' }
    },
    fbt: {
      '90/10': { through: 90, tap: 10, throughLoss: 0.8, tapLoss: 10.5, desc: '10% tap, 90% through' },
      '80/20': { through: 80, tap: 20, throughLoss: 1.3, tapLoss: 7.5, desc: '20% tap, 80% through' },
      '70/30':{ through: 70, tap: 30, throughLoss: 2.0, tapLoss: 5.5, desc: '30% tap, 70% through' },
      '50/50': { through: 50, tap: 50, throughLoss: 3.5, tapLoss: 3.5, desc: '50/50 equal split' },
      '30/70': { through: 30, tap: 70, throughLoss: 5.5, tapLoss: 2.0, desc: '70% tap, 30% through' },
      '20/80': { through: 20, tap: 80, throughLoss: 7.5, tapLoss: 1.3, desc: '80% tap, 20% through' },
      '10/90': { through: 10, tap: 90, throughLoss: 10.5, tapLoss: 0.8, desc: '90% tap, 10% through' }
    }
  };

  // Initialize modal options
  function initializeModalOptions() {
    // PLC options
    const plcContainer = document.getElementById('plc-options');
    plcContainer.innerHTML = '';
    Object.keys(splitterConfig.plc).forEach(ratio => {
      const config = splitterConfig.plc[ratio];
      const option = document.createElement('div');
      option.className = 'splitter-option';
      option.onclick = () => addSplitter('plc', ratio);
      option.innerHTML = `
        <div class="splitter-option-ratio">${ratio}</div>
        <div class="splitter-option-loss">${config.loss} dB loss</div>
        <div class="splitter-option-desc">${config.desc}</div>
      `;
      plcContainer.appendChild(option);
    });

    // FBT options
    const fbtContainer = document.getElementById('fbt-options');
    fbtContainer.innerHTML = '';
    Object.keys(splitterConfig.fbt).forEach(ratio => {
      const config = splitterConfig.fbt[ratio];
      const option = document.createElement('div');
      option.className = 'splitter-option';
      option.onclick = () => addSplitter('fbt', ratio);
      option.innerHTML = `
        <div class="splitter-option-ratio">${ratio}</div>
        <div class="splitter-option-loss">Through: ${config.throughLoss} dB | Tap: ${config.tapLoss} dB</div>
        <div class="splitter-option-desc">${config.desc}</div>
      `;
      fbtContainer.appendChild(option);
    });
  }

  function switchSplitterTab(type) {
    currentSplitterTab = type;
    document.querySelectorAll('.type-tab').forEach(tab => tab.classList.remove('active'));
    event.target.closest('.type-tab').classList.add('active');

    document.getElementById('plc-options').style.display = type === 'plc' ? 'grid' : 'none';
    document.getElementById('fbt-options').style.display = type === 'fbt' ? 'grid' : 'none';
  }

  function openSplitterModal(parentId) {
    currentModalParent = parentId;
    document.getElementById('splitterModal').classList.add('active');
  }

  function closeSplitterModal() {
    document.getElementById('splitterModal').classList.remove('active');
    currentModalParent = null;
  }

  function addSplitter(type, ratio) {
    if (!currentModalParent) return;

    const nodeId = `node-${nextNodeId++}`;
    const config = splitterConfig[type][ratio];

    const parentElement = document.getElementById(`${currentModalParent}-children`);

    if (type === 'plc') {
      // Add PLC splitter node
      const nodeHTML = createPLCNode(nodeId, ratio, config, currentModalParent);
      parentElement.insertAdjacentHTML('beforeend', nodeHTML);
    } else {
      // Add FBT tap coupler node
      const nodeHTML = createFBTNode(nodeId, ratio, config, currentModalParent);
      parentElement.insertAdjacentHTML('beforeend', nodeHTML);
    }

    closeSplitterModal();
    recalculateAll();
  }

  function createPLCNode(nodeId, ratio, config, parentId) {
    const children = [];
    for (let i = 1; i <= config.ports; i++) {
      children.push(`
        <div class="tree-node" id="${nodeId}-port${i}" data-parent="${nodeId}" data-port="${i}">
          <div class="node-card">
            <div class="node-header">
              <div class="node-title">
                <span class="node-icon">🔌</span>
                <span>Port ${i}</span>
              </div>
              <div class="node-power" id="${nodeId}-port${i}-power">-4.5 dBm</div>
            </div>
            <div class="node-actions">
              <button class="btn-add-splitter" onclick="openSplitterModal('${nodeId}-port${i}')">
                <span>➕</span>
                <span>Add Splitter</span>
              </button>
            </div>
          </div>
          <div class="child-nodes" id="${nodeId}-port${i}-children"></div>
        </div>
      `);
    }

    return `
      <div class="tree-node" id="${nodeId}" data-type="plc" data-ratio="${ratio}" data-parent="${parentId}">
        <div class="node-card plc-node">
          <div class="node-header">
            <div class="node-title">
              <span class="node-icon">🔀</span>
              <span>PLC ${ratio}</span>
            </div>
            <div class="node-power" id="${nodeId}-power">+2.0 dBm</div>
          </div>
          <div class="node-details">
            <div class="node-detail-item">
              <span class="node-detail-label">Type</span>
              <span class="node-detail-value">PLC Splitter</span>
            </div>
            <div class="node-detail-item">
              <span class="node-detail-label">Loss</span>
              <span class="node-detail-value">${config.loss} dB</span>
            </div>
            <div class="node-detail-item">
              <span class="node-detail-label">Ports</span>
              <span class="node-detail-value">${config.ports}</span>
            </div>
          </div>
          <div class="node-actions">
            <button class="btn-remove" onclick="removeNode('${nodeId}')">🗑️ Remove</button>
          </div>
        </div>
        <div class="child-nodes" id="${nodeId}-children">
          ${children.join('')}
        </div>
      </div>
    `;
  }

  function createFBTNode(nodeId, ratio, config, parentId) {
    return `
      <div class="tree-node" id="${nodeId}" data-type="fbt" data-ratio="${ratio}" data-parent="${parentId}">
        <div class="node-card fbt-node">
          <div class="node-header">
            <div class="node-title">
              <span class="node-icon">↔️</span>
              <span>FBT ${ratio}</span>
            </div>
            <div class="node-power" id="${nodeId}-power">+4.0 dBm</div>
          </div>
          <div class="node-details">
            <div class="node-detail-item">
              <span class="node-detail-label">Type</span>
              <span class="node-detail-value">FBT Tap Coupler</span>
            </div>
            <div class="node-detail-item">
              <span class="node-detail-label">Through Loss</span>
              <span class="node-detail-value">${config.throughLoss} dB</span>
            </div>
            <div class="node-detail-item">
              <span class="node-detail-label">Tap Loss</span>
              <span class="node-detail-value">${config.tapLoss} dB</span>
            </div>
          </div>
          <div class="node-actions">
            <button class="btn-remove" onclick="removeNode('${nodeId}')">🗑️ Remove</button>
          </div>
        </div>
        <div class="child-nodes" id="${nodeId}-children">
          <!-- Through Port -->
          <div class="tree-node" id="${nodeId}-through" data-parent="${nodeId}" data-port="through">
            <div class="node-card">
              <div class="node-header">
                <div class="node-title">
                  <span class="node-icon">➡️</span>
                  <span>Through (${config.through}%)</span>
                </div>
                <div class="node-power" id="${nodeId}-through-power">+5.0 dBm</div>
              </div>
              <div class="node-actions">
                <button class="btn-add-splitter" onclick="openSplitterModal('${nodeId}-through')">
                  <span>➕</span>
                  <span>Add Splitter</span>
                </button>
              </div>
            </div>
            <div class="child-nodes" id="${nodeId}-through-children"></div>
          </div>
          <!-- Tap Port -->
          <div class="tree-node" id="${nodeId}-tap" data-parent="${nodeId}" data-port="tap">
            <div class="node-card">
              <div class="node-header">
                <div class="node-title">
                  <span class="node-icon">📡</span>
                  <span>Tap (${config.tap}%)</span>
                </div>
                <div class="node-power" id="${nodeId}-tap-power">-1.0 dBm</div>
              </div>
              <div class="node-actions">
                <button class="btn-add-splitter" onclick="openSplitterModal('${nodeId}-tap')">
                  <span>➕</span>
                  <span>Add Splitter</span>
                </button>
              </div>
            </div>
            <div class="child-nodes" id="${nodeId}-tap-children"></div>
          </div>
        </div>
      </div>
    `;
  }

  function removeNode(nodeId) {
    if (confirm('Remove this splitter and all its children?')) {
      document.getElementById(nodeId).remove();
      recalculateAll();
    }
  }

  function recalculateAll() {
    const ponPower = parseFloat(document.getElementById('ponPower').value) || 0;
    const cableLoss = parseFloat(document.getElementById('defaultCableLoss').value) || 0;

    // Update PON display
    document.getElementById('pon-power').textContent = formatPower(ponPower);
    document.getElementById('pon-power-detail').textContent = formatPower(ponPower);
    updatePowerClass(document.getElementById('pon-power'), ponPower);

    // Calculate all nodes recursively
    const rootChildren = document.getElementById('pon-root-children');
    calculateNodePower(rootChildren, ponPower, cableLoss);

    // Update statistics
    updateStatistics();
  }

  function calculateNodePower(container, inputPower, cableLoss) {
    const children = container.children;

    for (let child of children) {
      const nodeId = child.id;
      const type = child.dataset.type;
      const ratio = child.dataset.ratio;

      if (!type) {
        // This is a port node
        const powerElement = document.getElementById(`${nodeId}-power`);
        if (powerElement) {
          powerElement.textContent = formatPower(inputPower);
          updatePowerClass(powerElement, inputPower);
        }

        // Recurse into port's children
        const portChildren = document.getElementById(`${nodeId}-children`);
        if (portChildren) {
          calculateNodePower(portChildren, inputPower, cableLoss);
        }
      } else if (type === 'plc') {
        // PLC splitter
        const config = splitterConfig.plc[ratio];
        const outputPower = inputPower - config.loss - cableLoss;

        const powerElement = document.getElementById(`${nodeId}-power`);
        if (powerElement) {
          powerElement.textContent = formatPower(outputPower);
          updatePowerClass(powerElement, outputPower);
        }

        // Update all ports with same power
        const nodeChildren = document.getElementById(`${nodeId}-children`);
        if (nodeChildren) {
          calculateNodePower(nodeChildren, outputPower, cableLoss);
        }
      } else if (type === 'fbt') {
        // FBT tap coupler
        const config = splitterConfig.fbt[ratio];

        // Through port
        const throughPower = inputPower - config.throughLoss - cableLoss;
        const throughElement = document.getElementById(`${nodeId}-through-power`);
        if (throughElement) {
          throughElement.textContent = formatPower(throughPower);
          updatePowerClass(throughElement, throughPower);
        }

        // Tap port
        const tapPower = inputPower - config.tapLoss - cableLoss;
        const tapElement = document.getElementById(`${nodeId}-tap-power`);
        if (tapElement) {
          tapElement.textContent = formatPower(tapPower);
          updatePowerClass(tapElement, tapPower);
        }

        // Recurse
        const throughChildren = document.getElementById(`${nodeId}-through-children`);
        if (throughChildren) {
          calculateNodePower(throughChildren, throughPower, cableLoss);
        }

        const tapChildren = document.getElementById(`${nodeId}-tap-children`);
        if (tapChildren) {
          calculateNodePower(tapChildren, tapPower, cableLoss);
        }
      }
    }
  }

  function formatPower(power) {
    return `${power >= 0 ? '+' : ''}${power.toFixed(1)} dBm`;
  }

  function updatePowerClass(element, power) {
    element.classList.remove('excellent', 'good', 'acceptable', 'marginal', 'poor');
    if (power > 0) {
      element.classList.add('excellent');
    } else if (power > -3) {
      element.classList.add('good');
    } else if (power > -8) {
      element.classList.add('acceptable');
    } else if (power > -15) {
      element.classList.add('marginal');
    } else {
      element.classList.add('poor');
    }
  }

  function updateStatistics() {
    // Count all endpoint nodes (nodes without children)
    let endpoints = 0;
    let totalPower = 0;

    const allPowerElements = document.querySelectorAll('[id$="-power"]');
    allPowerElements.forEach(el => {
      const nodeId = el.id.replace('-power', '');
      const childrenContainer = document.getElementById(`${nodeId}-children`);

      // Check if this is an endpoint (no children or empty children)
      if (childrenContainer && childrenContainer.children.length === 0) {
        endpoints++;
        const powerText = el.textContent;
        const power = parseFloat(powerText.replace(/[^-\d.]/g, ''));
        totalPower += power;
      }
    });

    const avgPower = endpoints > 0 ? totalPower / endpoints : parseFloat(document.getElementById('ponPower').value) || 0;

    document.getElementById('totalEndpoints').textContent = endpoints || 1;
    document.getElementById('avgPower').textContent = formatPower(avgPower);
  }

  // Initialize
  document.addEventListener('DOMContentLoaded', function() {
    initializeModalOptions();
    recalculateAll();
  });
</script>

    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.js"></script>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.6.2/dist/js/bootstrap.bundle.min.js"></script>

    <script src="https://cdn.jsdelivr.net/npm/admin-lte@3.2/dist/js/adminlte.min.js"></script>

    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js"></script>

    

  <script defer src="https://static.cloudflareinsights.com/beacon.min.js/v8c78df7c7c0f484497ecbca7046644da1771523124516" integrity="sha512-8DS7rgIrAmghBFwoOTujcf6D9rXvH8xm8JQ1Ja01h9QX8EzXldiszufYa4IFfKdLUKTTrnSFXLDkUEOTrZQ8Qg==" data-cf-beacon='{"version":"2024.11.0","token":"6df8fe60743e4dd685c1bf3bf7d2723f","r":1,"server_timing":{"name":{"cfCacheStatus":true,"cfEdge":true,"cfExtPri":true,"cfL4":true,"cfOrigin":true,"cfSpeedBrain":true},"location_startswith":null}}' crossorigin="anonymous"></script>
</body>
</html>