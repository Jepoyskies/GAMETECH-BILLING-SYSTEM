/**
 * Network Monitor - Shared polling and network telemetry utilities
 */
(function (global) {
    const NetworkMonitor = {
        /**
         * Fetch customer Mikrotik status and update target UI containers.
         * Optionally updates a Chart.js instance with live bandwidth points.
         *
         * @param {string|number} customerId
         * @param {Object} [options]
         * @param {string} [options.endpoint] - Custom API endpoint format
         * @param {Object} [options.chart] - Chart.js instance to push RX/TX points to
         * @param {Function} [options.onSuccess] - Callback receiving the raw JSON data
         * @param {Function} [options.onError] - Error callback
         * @returns {Promise<Object>}
         */
        fetchCustomerStatus: function (customerId, options) {
            options = options || {};
            const endpoint = options.endpoint || `/customers/api/status/${customerId}/`;

            return fetch(endpoint)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    const statusContainer = document.getElementById('mt-status-container');
                    const macEl = document.getElementById('mt-live-mac');
                    const uptimeEl = document.getElementById('mt-uptime');
                    const uptimeContainer = document.getElementById('uptime-container');
                    const lastLoggedOutEl = document.getElementById('mt-last-logged-out');
                    const lastLoggedOutContainer = document.getElementById('last-logged-out-container');
                    const stabilityBadge = document.getElementById('live-stability-badge');
                    const dlVal = document.getElementById('live-dl-val');
                    const ulVal = document.getElementById('live-ul-val');

                    const isConnected = data.mt_status === 'Connected';

                    if (statusContainer) {
                        if (isConnected) {
                            statusContainer.innerHTML = '<span class="text-success"><i class="fas fa-circle me-1" style="font-size:0.6rem;"></i>Connected</span>';
                        } else {
                            statusContainer.innerHTML = '<span class="text-danger"><i class="fas fa-circle me-1" style="font-size:0.6rem;"></i>' + (data.mt_status || 'Error') + '</span>';
                        }
                    }

                    if (macEl && data.live_mac !== undefined) {
                        macEl.innerText = data.live_mac;
                    }

                    if (isConnected) {
                        if (uptimeEl && data.uptime !== undefined) uptimeEl.innerText = data.uptime;
                        if (uptimeContainer) uptimeContainer.style.display = 'flex';
                        if (lastLoggedOutContainer) lastLoggedOutContainer.style.display = 'none';

                        if (stabilityBadge && data.stability) {
                            stabilityBadge.innerText = data.stability;
                            stabilityBadge.className = 'badge ms-2 bg-' + (data.stability_color || 'info');
                            stabilityBadge.style.display = 'inline-block';
                        }

                        if (data.rx_mbps !== undefined && data.tx_mbps !== undefined) {
                            if (dlVal) dlVal.innerHTML = data.rx_mbps + ' <span style="font-size: 0.9rem; font-weight: 600;">Mbps</span>';
                            if (ulVal) ulVal.innerHTML = data.tx_mbps + ' <span style="font-size: 0.9rem; font-weight: 600;">Mbps</span>';

                            if (options.chart && options.chart.data && options.chart.data.datasets) {
                                const now = new Date().toLocaleTimeString('en-US', {
                                    hour12: false,
                                    hour: "numeric",
                                    minute: "numeric",
                                    second: "numeric"
                                });

                                options.chart.data.labels.push(now);
                                options.chart.data.datasets[0].data.push(parseFloat(data.rx_mbps));
                                options.chart.data.datasets[1].data.push(parseFloat(data.tx_mbps));

                                if (options.chart.data.labels.length > 15) {
                                    options.chart.data.labels.shift();
                                    options.chart.data.datasets[0].data.shift();
                                    options.chart.data.datasets[1].data.shift();
                                }
                                options.chart.update('none');
                            }
                        }
                    } else {
                        if (stabilityBadge) stabilityBadge.style.display = 'none';

                        if (lastLoggedOutEl && data.last_logged_out !== undefined && data.last_logged_out !== 'N/A') {
                            lastLoggedOutEl.innerText = data.last_logged_out;
                            if (lastLoggedOutContainer) lastLoggedOutContainer.style.display = 'flex';
                        } else if (lastLoggedOutContainer) {
                            lastLoggedOutContainer.style.display = 'none';
                        }

                        if (uptimeContainer) uptimeContainer.style.display = 'none';
                        if (dlVal) dlVal.innerHTML = '0 <span style="font-size: 0.9rem; font-weight: 600;">Mbps</span>';
                        if (ulVal) ulVal.innerHTML = '0 <span style="font-size: 0.9rem; font-weight: 600;">Mbps</span>';
                    }

                    if (typeof options.onSuccess === 'function') {
                        options.onSuccess(data);
                    }

                    return data;
                })
                .catch(error => {
                    console.error("Error fetching Mikrotik status:", error);
                    const statusContainer = document.getElementById('mt-status-container');
                    if (statusContainer) {
                        statusContainer.innerHTML = '<span class="text-danger" title="' + error.message + '"><i class="fas fa-exclamation-triangle me-1" style="font-size:0.6rem;"></i>Error</span>';
                    }

                    const uptimeContainer = document.getElementById('uptime-container');
                    const lastLoggedOutContainer = document.getElementById('last-logged-out-container');
                    const macEl = document.getElementById('mt-live-mac');

                    if (uptimeContainer) uptimeContainer.style.display = 'none';
                    if (lastLoggedOutContainer) lastLoggedOutContainer.style.display = 'none';
                    if (macEl) macEl.innerText = 'N/A';

                    if (typeof options.onError === 'function') {
                        options.onError(error);
                    }
                    throw error;
                });
        },

        /**
         * Start polling customer status continuously
         * @param {string|number} customerId
         * @param {number} intervalMs
         * @param {Object} [options]
         * @returns {number} timer ID for clearInterval
         */
        pollCustomerStatus: function (customerId, intervalMs, options) {
            intervalMs = intervalMs || 5000;
            this.fetchCustomerStatus(customerId, options);
            return setInterval(() => {
                this.fetchCustomerStatus(customerId, options);
            }, intervalMs);
        },

        /**
         * Fetch Router Uplink Ping/Status and update UI card
         * @param {string} endpoint
         * @param {Object} [selectors]
         * @returns {Promise<Object>}
         */
        fetchRouterUplink: function (endpoint, selectors) {
            selectors = selectors || {};
            const statusElId = selectors.statusId || 'uplinkStatus';
            const pingElId = selectors.pingId || 'uplinkPing';
            const boxElId = selectors.boxId || 'kpi-uplink-box';

            return fetch(endpoint)
                .then(r => r.json())
                .then(d => {
                    const statusText = document.getElementById(statusElId);
                    const pingText = document.getElementById(pingElId);
                    const box = document.getElementById(boxElId);

                    if (statusText) statusText.classList.remove('syncing');

                    if (d.routers && d.routers.length > 0) {
                        const r = d.routers[0];
                        if (statusText) statusText.innerText = r.uplink_status;
                        if (pingText) pingText.innerText = "Ping: " + r.uplink_ping;

                        if (box) {
                            box.classList.remove('border-danger', 'border-warning', 'border-info', 'border-success');
                            box.style.setProperty('border-color', '', 'important');

                            if (r.uplink_status === 'Offline') {
                                box.classList.add('border-danger');
                            } else if (r.uplink_status === 'Unstable') {
                                box.classList.add('border-warning');
                            } else {
                                box.classList.add('border-info');
                            }
                        }
                    }
                    return d;
                })
                .catch(err => {
                    console.error("Uplink ping error", err);
                    const box = document.getElementById(boxElId);
                    const statusText = document.getElementById(statusElId);
                    const pingText = document.getElementById(pingElId);

                    if (statusText) {
                        statusText.innerText = "Error";
                        statusText.classList.remove('syncing');
                    }
                    if (pingText) pingText.innerText = "ping: failed";
                    if (box) {
                        box.classList.remove('border-info', 'border-warning', 'border-success');
                        box.classList.add('border-danger');
                    }
                    throw err;
                });
        },

        /**
         * Update modal customer search card with live stats
         * @param {string|number} customerId
         * @param {string} [endpoint]
         */
        fetchModalCustomerStatus: function (customerId, endpoint) {
            endpoint = endpoint || `/api/customer/${customerId}/mikrotik-status/`;
            return fetch(endpoint)
                .then(response => response.json())
                .then(data => {
                    const statusEl = document.getElementById('searchCustStatus');
                    const uptimeEl = document.getElementById('searchCustUptime');
                    const macEl = document.getElementById('searchCustMac');
                    const stabilityEl = document.getElementById('searchCustStability');
                    const dlEl = document.getElementById('searchCustDl');
                    const ulEl = document.getElementById('searchCustUl');

                    if (statusEl) {
                        const statusColor = data.mt_status === 'Connected' ? 'text-success' : 'text-danger';
                        statusEl.innerHTML = `<span class="${statusColor}">${data.mt_status}</span>`;
                    }

                    if (uptimeEl) {
                        uptimeEl.innerText = data.uptime !== 'N/A'
                            ? data.uptime
                            : (data.last_logged_out !== 'N/A' ? 'Offline since ' + data.last_logged_out : 'N/A');
                    }

                    if (macEl && data.live_mac !== undefined) {
                        macEl.innerText = data.live_mac;
                    }

                    if (stabilityEl) {
                        if (data.stability) {
                            stabilityEl.innerHTML = `<span class="text-${data.stability_color || 'info'}">${data.stability}</span>`;
                        } else {
                            stabilityEl.innerText = 'N/A';
                        }
                    }

                    if (dlEl && ulEl) {
                        if (data.rx_mbps !== undefined && data.tx_mbps !== undefined) {
                            dlEl.innerText = data.tx_mbps + ' Mbps';
                            ulEl.innerText = data.rx_mbps + ' Mbps';
                        } else {
                            dlEl.innerText = '0.0 Mbps';
                            ulEl.innerText = '0.0 Mbps';
                        }
                    }

                    return data;
                })
                .catch(error => {
                    console.error('Error fetching customer modal live status:', error);
                    throw error;
                });
        },

        /**
         * Generic batch status updater helper
         * @param {Array<Object>} users
         */
        updateConnectionStatuses: function (users) {
            if (!Array.isArray(users)) return;
            users.forEach(u => {
                const el = document.querySelector(`[data-user-status="${u.username || u.user}"]`);
                if (el) {
                    el.className = 'badge ' + (u.status === 'Connected' ? 'bg-success' : 'bg-danger');
                    el.textContent = u.status;
                }
            });
        }
    };

    global.NetworkMonitor = NetworkMonitor;
})(window);
