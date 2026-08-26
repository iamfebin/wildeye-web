document.addEventListener('DOMContentLoaded', function () {
    console.log('DOMContentLoaded fired. Enhanced layout script executing. v3');

    const sidebar = document.getElementById('sidebar');
    const sidebarToggler = document.getElementById('sidebar-toggler');
    const pageOverlay = document.querySelector('.sidebar-page-overlay');
    const body = document.body;

    function showAllSubmenus() {
        if (!sidebar) return;
        const submenus = sidebar.querySelectorAll('ul.components > li.has-submenu > ul.submenu');
        const submenuToggles = sidebar.querySelectorAll('ul.components > li.has-submenu > a.nav-link[data-bs-toggle="collapse"]');

        submenus.forEach(submenuEl => {
            let S_submenu = bootstrap.Collapse.getInstance(submenuEl);
            if (!S_submenu) {
                S_submenu = new bootstrap.Collapse(submenuEl, { toggle: false });
            }
            S_submenu.show();
        });
        submenuToggles.forEach(toggle => {
            toggle.setAttribute('aria-expanded', 'true');
            // Add .active class to parent toggler if its submenu is now shown (optional, for styling consistency)
            // if (!toggle.classList.contains('active') && /* condition for when to make it active */ ) {
            //     toggle.classList.add('active');
            // }
        });
    }

    function hideAllSubmenus() {
        if (!sidebar) return;
        const submenus = sidebar.querySelectorAll('ul.components > li.has-submenu > ul.submenu.show'); // Act only on shown
        const submenuToggles = sidebar.querySelectorAll('ul.components > li.has-submenu > a.nav-link[data-bs-toggle="collapse"]');

        submenus.forEach(submenuEl => {
            let S_submenu = bootstrap.Collapse.getInstance(submenuEl);
            if (S_submenu) {
                S_submenu.hide();
            }
        });
        submenuToggles.forEach(toggle => {
            toggle.setAttribute('aria-expanded', 'false');
            // Remove .active class from parent toggler if it's not active based on URL (optional)
            // if (toggle.classList.contains('active') && /* condition to check if it should remain active */) {
            //    // keep active
            // } else {
            //    toggle.classList.remove('active');
            // }
        });
    }

    function expandSidebar() {
        if (sidebar) sidebar.classList.add('expanded');
        if (pageOverlay) pageOverlay.classList.add('active');
        if (body) body.classList.add('sidebar-expanded-overlay');
        showAllSubmenus(); // Always show submenus when sidebar is expanded
    }

    function collapseSidebar() {
        if (sidebar) sidebar.classList.remove('expanded');
        if (pageOverlay) pageOverlay.classList.remove('active');
        if (body) body.classList.remove('sidebar-expanded-overlay');
        hideAllSubmenus(); // Hide submenus when sidebar is collapsed
    }

    // --- Sidebar Toggle Functionality (Hamburger and Overlay) ---
    if (sidebar && sidebarToggler && pageOverlay) {
        sidebarToggler.addEventListener('click', function () {
            if (sidebar.classList.contains('expanded')) {
                collapseSidebar();
            } else {
                expandSidebar();
            }
        });

        pageOverlay.addEventListener('click', function () {
            collapseSidebar();
        });
    } else {
        console.error('Core sidebar toggle elements not found!');
    }

    // --- Make Mini-Sidebar Icons (except Dashboard) Expand Sidebar ---
    if (sidebar && window.dashboardUrl) {
        const navLinks = sidebar.querySelectorAll('ul.components > li.nav-item > a.nav-link');
        const dashboardLinkHref = window.dashboardUrl;

        navLinks.forEach(link => {
            if (link.getAttribute('href') !== dashboardLinkHref) {
                link.addEventListener('click', function (event) {
                    if (!sidebar.classList.contains('expanded')) {
                        event.preventDefault(); // Prevent navigation/collapse if it's a toggle
                        expandSidebar();
                    }
                    // If sidebar is expanded and link is a toggle, Bootstrap would normally handle it.
                    // But now submenus are always shown when expanded, so parent links don't toggle.
                    // If the link is a direct navigation link (not data-bs-toggle), let it navigate.
                    else if (sidebar.classList.contains('expanded') && link.matches('[data-bs-toggle="collapse"]')) {
                        event.preventDefault(); // Prevent Bootstrap from trying to collapse the always-shown submenu
                    }
                });
            }
        });
    } else {
        if (!sidebar) console.error("Sidebar element not found for icon click handlers.");
        if (!window.dashboardUrl) console.error("window.dashboardUrl not defined. Cannot distinguish dashboard link.");
    }


    // --- Chart Initialization (Keep your specific chart configs) ---
    const cameraStatusCtxEl = document.getElementById('cameraStatusChart');
    if (cameraStatusCtxEl) {
        const existingCameraChart = Chart.getChart(cameraStatusCtxEl);
        if (existingCameraChart) {
            existingCameraChart.destroy();
        }
        new Chart(cameraStatusCtxEl, {
            type: 'doughnut', data: { labels: ['Online', 'Offline'], datasets: [{ data: [10,5], backgroundColor:['green','red']}] }, options: { responsive: true}
        });
        console.log('cameraStatusChart initialized.');
    }

    function loadAlertsTrendChart() {
        const alertsCtxEl = document.getElementById('alertsChart');
        if (!alertsCtxEl) {
            console.log('alertsCtx not found on this page. Skipping alerts chart load.');
            return;
        }
        const apiUrl = '/api/alerts-trend/';

        fetch(apiUrl)
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                const existingAlertsChart = Chart.getChart(alertsCtxEl);
                if (existingAlertsChart) existingAlertsChart.destroy();
                new Chart(alertsCtxEl, {
                    type: 'line', data: { labels: data.labels || [], datasets: [{ label: 'Alerts', data: data.data || [], borderColor: 'red'}] }, options: { responsive: true }
                });
                console.log('alertsChart initialized.');
            })
            .catch(error => {
                console.error('Error fetching alerts trend data:', error);
                if (alertsCtxEl && alertsCtxEl.parentElement) {
                    const existingAlertsChart = Chart.getChart(alertsCtxEl);
                    if(!existingAlertsChart) {
                        alertsCtxEl.parentElement.innerHTML = '<p class="text-danger text-center">Could not load alerts trend data.</p>';
                    }
                }
            });
    }

    if (document.getElementById('alertsChart')) {
        loadAlertsTrendChart();
    }

    // --- Active Link Highlighting (Focuses on styling, not opening/closing) ---
    const currentPath = window.location.pathname;
    const sidebarNavLinks = document.querySelectorAll('#sidebar ul.components > li.nav-item > a.nav-link');

    sidebarNavLinks.forEach(link => {
        let linkPath = link.getAttribute('href');
        let isDropdownToggle = link.matches('[data-bs-toggle="collapse"]');

        // Reset active states first to handle navigation correctly
        link.classList.remove('active');
        if(link.closest('.nav-item')) {
            link.closest('.nav-item').classList.remove('active');
        }
        // For submenu items, remove active-submenu from their li
        if (!isDropdownToggle) { // Only for actual links, not toggles
            let parentLi = link.closest('li');
            if (parentLi && parentLi.classList.contains('active-submenu')) {
                parentLi.classList.remove('active-submenu');
            }
        }


        if (isDropdownToggle) {
            const submenuId = link.getAttribute('href');
            const submenu = document.querySelector(submenuId);
            if (submenu) {
                const activeSubmenuLink = submenu.querySelector(`a[href="${currentPath}"]`);
                if (activeSubmenuLink) {
                    link.classList.add('active'); // Style parent toggle if a child is active
                    if (activeSubmenuLink.closest('li')) {
                        activeSubmenuLink.closest('li').classList.add('active-submenu');
                    }
                }
            }
        } else if (linkPath === currentPath) { // Direct link
            if(link.closest('.nav-item')) {
                link.closest('.nav-item').classList.add('active'); // Style the nav-item (top level li)
            }
            // If this direct link is inside a submenu, ensure its parent toggle is also styled as active
            let parentSubmenu = link.closest('ul.submenu.collapse');
            if(parentSubmenu) {
                 let parentToggler = document.querySelector(`a.nav-link[data-bs-toggle="collapse"][href="#${parentSubmenu.id}"]`);
                 if(parentToggler) {
                     parentToggler.classList.add('active'); // Style parent toggle
                 }
                 if (link.closest('li')) {
                    link.closest('li').classList.add('active-submenu'); // Style this specific child's li
                 }
            } else {
                // This is a direct top-level link, ensure its 'a' tag gets 'active' if not already via .nav-item
                 link.classList.add('active');
            }
        }
    });

    // If sidebar is expanded on page load (e.g. not mobile), ensure submenus are shown
    // This is primarily for cases where Django might not add .show but a child is active
    if (sidebar && sidebar.classList.contains('expanded')) {
        // Check if any submenu's parent toggle is marked 'active' by the logic above
        // and ensure its submenu is shown. This might be redundant if showAllSubmenus()
        // is robust or if initial state is handled well.
        // For simplicity, if sidebar is expanded, just ensure all submenus are shown:
        // showAllSubmenus(); // Already called if expandSidebar() is part of initial setup
    } else if (sidebar && !sidebar.classList.contains('expanded')) {
        // Ensure submenus are hidden if sidebar is not expanded on load
        // hideAllSubmenus(); // Already called if collapseSidebar() is part of initial setup
    }


}); // End DOMContentLoaded