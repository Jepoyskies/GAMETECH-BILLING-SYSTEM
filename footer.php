        </main> <!-- close main content if needed; adjust in index.php if you have extra wrappers -->
    </div> <!-- close .main-content -->

    <!-- Layout scripts (put at end for better performance) -->
    <script>
    document.addEventListener("DOMContentLoaded", function() {
        const sidebar = document.getElementById('sidebar');
        const openSidebarBtn = document.getElementById('openSidebar');
        const closeSidebarBtn = document.getElementById('closeSidebar');
        const sidebarOverlay = document.getElementById('sidebarOverlay');
        const hideSidebarBtn = document.getElementById('hideSidebar');
        const mainContent = document.getElementById('mainContent');
        const showSidebarBtn = document.getElementById('showSidebar');

        function openSidebar() {
            sidebar.classList.add('open');
            sidebar.classList.remove('collapsed');
            mainContent.classList.remove('full');
            if (window.innerWidth < 992) {
                sidebarOverlay.classList.add('active');
            }
            if (window.innerWidth >= 992) {
                showSidebarBtn.style.display = 'none';
            }
        }

        function closeSidebar() {
            sidebar.classList.remove('open');
            sidebar.classList.remove('collapsed');
            if (window.innerWidth < 992) {
                sidebarOverlay.classList.remove('active');
            } else {
                mainContent.classList.add('full');
            }
            if (window.innerWidth >= 992) {
                showSidebarBtn.style.display = 'inline-block';
            }
        }

        function hideSidebar() {
            if (window.innerWidth >= 992) {
                sidebar.classList.add('collapsed');
                sidebar.classList.remove('open');
                mainContent.classList.add('full');
                showSidebarBtn.style.display = 'inline-block';
            }
        }

        function showSidebar() {
            if (window.innerWidth >= 992) {
                sidebar.classList.remove('collapsed');
                sidebar.classList.add('open');
                mainContent.classList.remove('full');
                showSidebarBtn.style.display = 'none';
            }
        }

        if (openSidebarBtn) openSidebarBtn.addEventListener('click', openSidebar);
        if (closeSidebarBtn) closeSidebarBtn.addEventListener('click', closeSidebar);
        if (sidebarOverlay) sidebarOverlay.addEventListener('click', closeSidebar);
        if (hideSidebarBtn) hideSidebarBtn.addEventListener('click', hideSidebar);
        if (showSidebarBtn) showSidebarBtn.addEventListener('click', showSidebar);

        window.addEventListener('resize', function() {
            if (window.innerWidth >= 992) {
                sidebarOverlay.classList.remove('active');
                if (sidebar.classList.contains('collapsed')) {
                    showSidebarBtn.style.display = 'inline-block';
                    mainContent.classList.add('full');
                } else {
                    showSidebarBtn.style.display = 'none';
                    mainContent.classList.remove('full');
                }
                if (!sidebar.classList.contains('collapsed')) {
                    sidebar.classList.add('open');
                }
            } else {
                sidebar.classList.remove('open', 'collapsed');
                mainContent.classList.remove('full');
                showSidebarBtn.style.display = 'none';
            }
        });

        // Initial state
        if (window.innerWidth >= 992) {
            sidebar.classList.add('open');
            showSidebarBtn.style.display = sidebar.classList.contains('collapsed') ? 'inline-block' : 'none';
            mainContent.classList.remove('full');
        }
    });
    </script>

    <!-- Bootstrap JS (optional, if you need Bootstrap components) -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
