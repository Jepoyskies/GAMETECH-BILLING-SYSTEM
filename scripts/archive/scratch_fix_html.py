import re

with open('billing/templates/billing/changelog.html', 'r', encoding='utf-8') as f:
    html = f.read()

replacement = """                        <!-- AUGUST 28 -->
                        <div class="tab-pane fade" id="list-aug28" role="tabpanel" aria-labelledby="list-aug28-list">
                            <h3 class="fw-bold mb-4 border-bottom pb-3" style="color: #1e3a8a;">August 28, 2026: Sync Audits, Payment Reversals, & Cignal Play</h3>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#059669; padding: 8px 12px;"><i class="fas fa-coins me-1"></i> Staggered Payments</span>
                                    Fractional Staggered Payments System
                                </h5>
                                <div class="p-4 rounded-4" style="background: #f0fdf4; border: 1px solid #a7f3d0;">
                                    <p class="mb-2 text-dark" style="font-size:1.05rem;"><strong>The Problem:</strong> Customers were bringing in partial payments (e.g. paying ₱300 out of a ₱1,000 monthly bill). The old system forced admins to either deny the payment or manually calculate days. <br><strong>The Fix:</strong> We overhauled <code>PaymentView</code> in Python. The math engine now accepts the exact cash amount, divides it against the plan's monthly cost, derives a percentage, and extends the active days based on that exact fraction (down to the hour). We added a "Quick Pay Grid" to the frontend so staff can just click "1/2" or "3/4" payment buttons.</p>
                                </div>
                            </div>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#b91c1c; padding: 8px 12px;"><i class="fas fa-exchange-alt me-1"></i> Payment Fixes</span>
                                    Surgical Payment Transfers
                                </h5>
                                <div class="p-4 rounded-4" style="background: #fef2f2; border: 1px solid #fecaca;">
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;"><strong>The Problem:</strong> A CSR credits payment to the wrong 'Juan Dela Cruz'. Deleting the log destroys accounting records.<br><strong>The Fix:</strong> We built a "Transfer Payment" modal inside the Audit Logs. Admins can select the mistaken payment, pick the correct customer, and execute a transfer. The Python backend algorithmically rolls back Customer A's expiration date, pushes Customer B's expiration date forward, and preserves the financial audit trail seamlessly.</p>
                                </div>
                            </div>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#7c3aed; padding: 8px 12px;"><i class="fas fa-search-dollar me-1"></i> Sync Manager V2</span>
                                    Rogue Account Detection
                                </h5>
                                <div class="p-4 rounded-4" style="background: #fdf4ff; border: 1px solid #e9d5ff;">
                                    <p class="mb-2 text-dark" style="font-size:1.05rem;"><strong>The Problem:</strong> Technicians could secretly create PPPoE accounts in Winbox directly, bypassing the billing system entirely, resulting in stolen bandwidth.<br><strong>The Fix:</strong> We turned the Sync Manager into a weaponized audit tool. It pulls all Mikrotik Secrets and compares them to the Django SQL database. It actively hunts for "Suspicious Accounts"—users missing strict bandwidth profiles (using 'default'), missing comments, or lacking a Gametech account. <br><strong>Hygiene Rule:</strong> Any update made in Django now automatically overwrites the Mikrotik's PPPoE Comment field to exactly <code>Full Name | Barangay</code>.</p>
                                </div>
                            </div>
                        </div>

                        <!-- AUGUST 26 -->
                        <div class="tab-pane fade" id="list-aug26" role="tabpanel" aria-labelledby="list-aug26-list">
                            <h3 class="fw-bold mb-4 border-bottom pb-3" style="color: #1e3a8a;">August 26, 2026: The DigitalOcean Live Deployment</h3>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#1d4ed8; padding: 8px 12px;"><i class="fas fa-server me-1"></i> Production Build</span>
                                    Live Production Architecture Build
                                </h5>
                                <div class="p-4 rounded-4" style="background: #eff6ff; border: 1px solid #bfdbfe;">
                                    <p class="mb-2 text-dark" style="font-size:1.05rem;"><strong>The Mission:</strong> Move from local host to the open internet safely. <br><strong>The Execution:</strong> We provisioned a DigitalOcean Droplet. We containerized the entire application ecosystem using Docker. We wrote a massive <code>docker-compose.yml</code> file orchestrating the Django Web container, the PostgreSQL Database, the Redis Cache, the Celery Worker, and the Celery Beat scheduler.</p>
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;"><strong>The Stress:</strong> The web container refused to boot due to Windows CRLF line endings attached to the <code>start_web.sh</code> script. We had to enforce LF line endings via git configs (<code>chore: enforce LF line endings</code>). We also faced a fierce battle configuring Nginx to properly serve static files, writing custom block directives to proxy headers securely to Gunicorn.</p>
                                </div>
                            </div>
                            
                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#0891b2; padding: 8px 12px;"><i class="fas fa-cogs me-1"></i> CI/CD Pipeline</span>
                                    GitHub Actions Automated Deployment
                                </h5>
                                <div class="p-4 rounded-4" style="background: #ecfeff; border: 1px solid #a5f3fc;">
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;">We refused to manually upload files via FTP. We coded a GitHub Actions YAML pipeline. Every time a commit is pushed to the <code>main</code> branch, GitHub's servers automatically SSH into our DigitalOcean server using an encrypted key, pull the new code, rebuild the Docker containers, and restart the web server autonomously. True Silicon Valley grade deployments.</p>
                                </div>
                            </div>
                            
                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#c026d3; padding: 8px 12px;"><i class="fas fa-user-secret me-1"></i> Auditing</span>
                                    ThreadLocalUserMiddleware Implementation
                                </h5>
                                <div class="p-4 rounded-4" style="background: #fdf4ff; border: 1px solid #f5d0fe;">
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;"><strong>The Problem:</strong> Our Django Signals (which trigger when a model is saved) had no idea *who* triggered them, causing logs to say "System" made the change.<br><strong>The Fix:</strong> We implemented <code>ThreadLocalUserMiddleware</code>, a highly advanced Python concept that captures the HTTP Request user and stores it in thread-local storage, allowing our deep backend Signals to attribute exactly which admin made the modification to the <code>SystemLog</code>.</p>
                                </div>
                            </div>
                        </div>

                        <!-- AUGUST 25 -->
                        <div class="tab-pane fade" id="list-aug25" role="tabpanel" aria-labelledby="list-aug25-list">
                            <h3 class="fw-bold mb-4 border-bottom pb-3" style="color: #1e3a8a;">August 25, 2026: Celery Beat, Stability, & Live Monitoring Fixes</h3>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#ea580c; padding: 8px 12px;"><i class="fas fa-satellite-dish me-1"></i> Live Monitoring Fixes</span>
                                    Polling Loop Logic Fix
                                </h5>
                                <div class="p-4 rounded-4" style="background: #fff7ed; border: 1px solid #fed7aa;">
                                    <p class="mb-2 text-dark" style="font-size:1.05rem;"><strong>The Problem:</strong> The javascript polling the Mikrotik API for active sessions was creating duplicate loops every time the dropdown changed, effectively DDOSing our own router.<br><strong>The Fix:</strong> We completely rewrote the Javascript polling logic using strict <code>clearInterval()</code> state management, ensuring only one active websocket/fetch loop existed at a time.</p>
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;">We also programmed the <strong>Offline User Diagnostics</strong>. If a customer drops offline, the system queries all other customers in their exact Barangay. If they are also offline, the UI pops up a massive alert indicating a "Barangay-Wide Fiber Cut" rather than a single NAP issue.</p>
                                </div>
                            </div>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#059669; padding: 8px 12px;"><i class="fas fa-tasks me-1"></i> Background Workers</span>
                                    Auto-Reconciliation via Celery Beat
                                </h5>
                                <div class="p-4 rounded-4" style="background: #f0fdf4; border: 1px solid #a7f3d0;">
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;">We needed background tasks to run automatically without human intervention. We deployed <strong>Celery Beat</strong> to act as a chronometer. We wrote a script (<code>auto_reconcile_routers.py</code>) that constantly attempts to push failed PPPoE profiles to the Mikrotik if the router was previously offline during activation. We also set up the <code>auto_suspend</code> command to run at midnight to execute expirations.</p>
                                </div>
                            </div>
                        </div>

                        <!-- AUGUST 24 -->
                        <div class="tab-pane fade" id="list-aug24" role="tabpanel" aria-labelledby="list-aug24-list">
                            <h3 class="fw-bold mb-4 border-bottom pb-3" style="color: #1e3a8a;">August 24, 2026: Notifications Engine & API Hardening</h3>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#ca8a04; padding: 8px 12px;"><i class="fas fa-bell me-1"></i> Notifications</span>
                                    Global Notification System
                                </h5>
                                <div class="p-4 rounded-4" style="background: #fefce8; border: 1px solid #fef08a;">
                                    <p class="mb-2 text-dark" style="font-size:1.05rem;">Built an entire standalone <code>Notification</code> database model. We wired this model to intercept core events (Customer Expired, Cignal Request added). The top-bar Bell icon uses an AJAX payload to fetch unread counts.</p>
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;">Added a "Mark All as Read" Javascript function, and created a massive, paginated <code>notifications.html</code> archive page allowing admins to review alerts from months ago.</p>
                                </div>
                            </div>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#b91c1c; padding: 8px 12px;"><i class="fas fa-shield-alt me-1"></i> API Hardening</span>
                                    RouterOS API Error Handling Rescue
                                </h5>
                                <div class="p-4 rounded-4" style="background: #fef2f2; border: 1px solid #fecaca;">
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;"><strong>The Problem:</strong> When the Mikrotik went offline, the <code>routeros_api</code> was silently swallowing the connection error and returning empty lists. The frontend assumed everyone was offline and crashed.<br><strong>The Fix:</strong> We dive-bombed the API wrapper code, explicitly checked the <code>_connection_failed</code> flag, and forced the backend to raise an <code>API Unreachable</code> exception, passing this cleanly to the frontend to display a graceful "Router Unreachable" tooltip rather than nuking the UI.</p>
                                </div>
                            </div>
                        </div>

                        <!-- AUGUST 22 -->
                        <div class="tab-pane fade" id="list-aug22" role="tabpanel" aria-labelledby="list-aug22-list">
                            <h3 class="fw-bold mb-4 border-bottom pb-3" style="color: #1e3a8a;">August 22, 2026: Gametech Premium UI Overhaul</h3>
                            
                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#9333ea; padding: 8px 12px;"><i class="fas fa-paint-brush me-1"></i> UI Overhaul</span>
                                    The theme.css Masterpiece
                                </h5>
                                <div class="p-4 rounded-4" style="background: #faf5ff; border: 1px solid #e9d5ff;">
                                    <p class="mb-2 text-dark" style="font-size:1.05rem;">We ripped out default Bootstrap. We wrote a massive, custom <code>theme.css</code> file injecting SaaS aesthetics system-wide.</p>
                                    <ul class="mb-0 text-dark" style="font-size: 1.05rem;">
                                        <li><strong>CSS Gradients:</strong> Apple-style blue-to-purple diagonal gradients on headers and primary buttons.</li>
                                        <li><strong>Avatar Generator:</strong> A Python engine extracts customer initials, hashes their name to a unique color, and renders SVG profile pictures dynamically.</li>
                                        <li><strong>Glassmorphism:</strong> <code>backdrop-filter: blur(16px)</code> applied to navigation bars and floating modals.</li>
                                        <li><strong>Micro-Interactions:</strong> Table rows hover-lift, buttons cast dynamic drop shadows on click, and forms utilize a 0.4s ease-out fade-in animation. All edges rounded to 16px.</li>
                                    </ul>
                                </div>
                            </div>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#0891b2; padding: 8px 12px;"><i class="fas fa-chart-line me-1"></i> Analytics</span>
                                    Chart.js Financial Dashboard
                                </h5>
                                <div class="p-4 rounded-4" style="background: #ecfeff; border: 1px solid #a5f3fc;">
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;">Integrated Chart.js on the main dashboard. We wrote backend aggregation logic to sum up payments grouped by day over the last 7 days, passing the JSON array to the frontend to render a breathtaking, animated Spline Chart of total revenue, paired with 4 hard-coded KPI boxes (Active, Suspended, Expired, Revenue).</p>
                                </div>
                            </div>
                        </div>

                        <!-- AUGUST 20 - 21 -->
                        <div class="tab-pane fade" id="list-aug20" role="tabpanel" aria-labelledby="list-aug20-list">
                            <h3 class="fw-bold mb-4 border-bottom pb-3" style="color: #1e3a8a;">August 20 - 21, 2026: RBAC, Master Data, & Migration Tech</h3>
                            
                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#059669; padding: 8px 12px;"><i class="fas fa-user-lock me-1"></i> Security</span>
                                    Role-Based Access Control (RBAC) Gating
                                </h5>
                                <div class="p-4 rounded-4" style="background: #f0fdf4; border: 1px solid #a7f3d0;">
                                    <p class="mb-2 text-dark" style="font-size:1.05rem;">We wrapped every single URL in the application with Django's <code>@permission_required</code> decorators.</p>
                                    <ul class="mb-0 text-dark" style="font-size: 1.05rem;">
                                        <li><strong>Admins:</strong> Allowed to access <code>delete_customer</code>, edit financial ledgers, and view massive system logs.</li>
                                        <li><strong>Technicians:</strong> Allowed to access <code>network_manager</code> and sync features, but locked completely out of payment routes.</li>
                                        <li><strong>CSRs:</strong> Allowed to access <code>add_payment</code> and <code>view_customer</code>, but strictly denied destructive actions.</li>
                                    </ul>
                                </div>
                            </div>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#db2777; padding: 8px 12px;"><i class="fas fa-route me-1"></i> Migration Engine</span>
                                    The Bulk Router Migration Engine
                                </h5>
                                <div class="p-4 rounded-4" style="background: #fdf2f8; border: 1px solid #fbcfe8;">
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;">A terrifying engineering feat. We built a tool that allows Admins to checkbox 100 customers, click "Transfer Router", and select new hardware. The Python backend iterates through the array, logs into Router A, issues a <code>/ppp/secret/remove</code> command, logs into Router B, issues a <code>/ppp/secret/add</code> command, and updates the local SQL foreign keys simultaneously.</p>
                                </div>
                            </div>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#4f46e5; padding: 8px 12px;"><i class="fas fa-fingerprint me-1"></i> MAC Spoofing</span>
                                    MAC Address Spoof Tracking
                                </h5>
                                <div class="p-4 rounded-4" style="background: #e0e7ff; border: 1px solid #c7d2fe;">
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;">Created a dedicated model to trace hardware theft/spoofing. If a PPPoE account connects with a new MAC Address, the system intercepts the change, records the old MAC vs new MAC, and stamps the exact timestamp into a permanent security log.</p>
                                </div>
                            </div>
                        </div>

                        <!-- AUGUST 13 - 19 -->
                        <div class="tab-pane fade" id="list-aug13" role="tabpanel" aria-labelledby="list-aug13-list">
                            <h3 class="fw-bold mb-4 border-bottom pb-3" style="color: #1e3a8a;">August 13 - 19, 2026: Portals, SOA, Rebates, & Maps</h3>
                            
                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#0284c7; padding: 8px 12px;"><i class="fas fa-laptop-house me-1"></i> User Portal</span>
                                    The End-User Customer Portal
                                </h5>
                                <div class="p-4 rounded-4" style="background: #f0f9ff; border: 1px solid #bae6fd;">
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;">We built an entirely separate Django App called <code>customer_portal</code>. We designed a mobile-first interface where users log in with their Account ID and PIN. They can instantly see their live Mikrotik IP address, check their payment ledger, and monitor their exact expiration date without bothering support.</p>
                                </div>
                            </div>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#16a34a; padding: 8px 12px;"><i class="fas fa-print me-1"></i> Invoicing</span>
                                    Dynamic Statement of Account (SOA)
                                </h5>
                                <div class="p-4 rounded-4" style="background: #f0fdf4; border: 1px solid #bbf7d0;">
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;">Constructed the <code>portal_statement.html</code> view. The backend scrapes the last 12 months of payments, calculates arrears, formats the text onto an official Gametech Letterhead, and triggers browser print-CSS rules so the document comes out of a physical printer perfectly formatted for distribution.</p>
                                </div>
                            </div>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#eab308; padding: 8px 12px;"><i class="fas fa-hand-holding-usd me-1"></i> Rebates & Rollbacks</span>
                                    Surgical Adjustments UI
                                </h5>
                                <div class="p-4 rounded-4" style="background: #fefce8; border: 1px solid #fef08a;">
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;">Built dedicated HTML views: <code>customer_rebate.html</code> to grant free internet days to users as compensation, and <code>customer_rollback.html</code> to brutally revert false payments and forcefully subtract days from an account.</p>
                                </div>
                            </div>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#14b8a6; padding: 8px 12px;"><i class="fas fa-map-marker-alt me-1"></i> Geolocation</span>
                                    OpenStreetMap API Integration
                                </h5>
                                <div class="p-4 rounded-4" style="background: #f0fdfa; border: 1px solid #99f6e4;">
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;">Integrated Leaflet.js and OpenStreetMap directly into the <code>add_customer.html</code> and <code>edit_customer.html</code> pages. Admins can drag a physical pin to a house, saving the exact GPS coordinates into the Django PostgreSQL database, which then plots on a massive master map.</p>
                                </div>
                            </div>
                        </div>

                        <!-- AUGUST 11 - 12 -->
                        <div class="tab-pane fade" id="list-aug11" role="tabpanel" aria-labelledby="list-aug11-list">
                            <h3 class="fw-bold mb-4 border-bottom pb-3" style="color: #1e3a8a;">August 11 - 12, 2026: Genesis, Core Setup, & Router Link</h3>
                            
                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#dc2626; padding: 8px 12px;"><i class="fas fa-skull-crossbones me-1"></i> Demolition</span>
                                    Destruction of Legacy PHP & Data Migration
                                </h5>
                                <div class="p-4 rounded-4" style="background: #fef2f2; border: 1px solid #fecaca;">
                                    <p class="mb-2 text-dark" style="font-size:1.05rem;">The project began by tearing down the unscalable, insecure PHP codebase. We bootstrapped a fresh Django environment.</p>
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;"><strong>The Stress:</strong> We had to carefully export the legacy MySQL database, map the old column names to the new Django ORM models, and pipe thousands of old payment logs and customer records into PostgreSQL without destroying referential integrity. Not a single byte was lost.</p>
                                </div>
                            </div>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#1d4ed8; padding: 8px 12px;"><i class="fas fa-plug me-1"></i> Mikrotik Link</span>
                                    Direct RouterOS API Engineering
                                </h5>
                                <div class="p-4 rounded-4" style="background: #eff6ff; border: 1px solid #bfdbfe;">
                                    <p class="mb-2 text-dark" style="font-size:1.05rem;">The hardest problem of the early phase: talking to the hardware. We wrote Python scripts utilizing the <code>routeros_api</code> package to open TCP ports to 192.168.88.2.</p>
                                    <ul class="mb-0 text-dark" style="font-size: 1.05rem;">
                                        <li><strong>Automated Activations:</strong> Creating a Django user fires a <code>/ppp/secret/add</code> command instantly.</li>
                                        <li><strong>Live Connection Polling:</strong> A view queries <code>/ppp/active/print</code> to read live bytes in/out and session uptime.</li>
                                        <li><strong>Instant Terminations:</strong> When suspended, the system fires <code>/ppp/active/remove</code> kicking the user instantly.</li>
                                    </ul>
                                </div>
                            </div>

                            <!-- Item -->
                            <div class="mb-4">
                                <h5 class="fw-bold d-flex align-items-center gap-2 mb-3">
                                    <span class="badge" style="background:#6d28d9; padding: 8px 12px;"><i class="fas fa-flask me-1"></i> Math Engine</span>
                                    Data Seeding & The Expiration Engine
                                </h5>
                                <div class="p-4 rounded-4" style="background: #fdf4ff; border: 1px solid #e9d5ff;">
                                    <p class="mb-2 text-dark" style="font-size:1.05rem;">We wrote the mathematical foundation for expirations (<code>expires_at = current_date + timedelta(days=30)</code>).</p>
                                    <p class="mb-0 text-dark" style="font-size:1.05rem;"><strong>The Testing:</strong> To ensure this math wouldn't crash under load, we wrote <code>seed.py</code> and <code>seed_data.py</code> scripts to flood the local database with thousands of fake users. We fast-forwarded time locally to watch the suspension logic successfully flag expired users en-masse without breaking.</p>
                                </div>
                            </div>
                        </div>"""

start_idx = html.find('                        <!-- AUGUST 28 -->')
end_idx = html.find('                    </div>\n                </div>\n            </div>\n        </div>\n    </div>\n</div>')

new_html = html[:start_idx] + replacement + '\n' + html[end_idx:]

with open('billing/templates/billing/changelog.html', 'w', encoding='utf-8') as f:
    f.write(new_html)
