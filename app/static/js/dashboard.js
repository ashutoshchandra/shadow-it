// app/static/js/dashboard.js
"use strict";

// --- Global Variables & State ---
let allAppsData = []; // Stores the full dataset fetched from the API
let riskDistributionChart = null;
let spendByCategoryChart = null;
let usageTrendChart = null;
const appDetailModal = new bootstrap.Modal(document.getElementById('appDetailModal')); // Modal instance
let currentSortColumn = null;
let currentSortDirection = 'asc';

// --- Configuration (from HTML or global JS settings if needed) ---
const API_ENDPOINTS = {
    stats: '/api/summary_stats',
    apps: '/api/apps',
    behavior: '/api/behavior_insights',
    riskChart: '/api/chart_data/risk_distribution',
    spendChart: '/api/chart_data/spend_by_category',
    trendChart: '/api/chart_data/usage_trend',
    resolveApp: '/api/apps/:app_id/resolve' // Placeholder for app_id
};

const RISK_LEVEL_CLASSES = {
    'High': 'table-danger',
    'Medium': 'table-warning',
    'Low': 'table-light', // Bootstrap default or light gray
    'Info': 'table-info' // Using info for irrelevant/FP
};

const STATUS_BADGES = {
    'unknown': 'bg-secondary',
    'sanctioned': 'bg-success',
    'unsanctioned': 'bg-danger',
    'irrelevant': 'bg-info text-dark',
    'conditionally_approved': 'bg-primary',
};

const RESOLUTION_STATUS_ICONS = {
    'Sanctioned': '<i class="fas fa-check-circle text-success me-1" title="Sanctioned"></i>',
    'Blocked': '<i class="fas fa-ban text-danger me-1" title="Blocked"></i>',
    'Investigating': '<i class="fas fa-magnifying-glass text-warning me-1" title="Investigating"></i>',
    'FalsePositive': '<i class="fas fa-low-vision text-info me-1" title="False Positive/Irrelevant"></i>'
}


// --- Utility Functions ---
const formatCurrency = (value) => `$${(value || 0).toFixed(2)}`;
const formatDate = (isoString) => isoString ? moment(isoString).format('YYYY-MM-DD HH:mm') : 'N/A';
const formatNumber = (value) => (value || 0).toLocaleString();
const formatMB = (value) => `${(value || 0).toFixed(1)}`; // Megabytes with 1 decimal

// Function to display status messages (e.g., for API updates)
function showStatusMessage(message, type = 'info') { // type: success, danger, warning, info
    const container = document.getElementById('status-message-container');
    const alertClass = `alert-${type}`;
    const alert = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>`;
    container.innerHTML = alert; // Replace previous message
    // Optional: auto-dismiss after some time
    setTimeout(() => {
        const activeAlert = container.querySelector('.alert');
        if (activeAlert) {
             bootstrap.Alert.getOrCreateInstance(activeAlert).close();
         }
     }, 5000); // Dismiss after 5 seconds
}

// --- API Fetch Functions ---
async function fetchData(endpoint) {
    try {
        const response = await fetch(endpoint);
        if (!response.ok) {
            console.error(`API Error ${response.status}: ${response.statusText} for ${endpoint}`);
            showStatusMessage(`Error fetching data from ${endpoint}. Status: ${response.status}`, 'danger');
             return null; // Indicate failure
         }
        return await response.json();
     } catch (error) {
         console.error(`Network or fetch error for ${endpoint}:`, error);
         showStatusMessage(`Network error fetching data from ${endpoint}. Check console.`, 'danger');
        return null; // Indicate failure
     }
}

async function postData(endpoint, data) {
     try {
         const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
         if (!response.ok) {
             const errorData = await response.json().catch(() => ({})); // Try get error details
             console.error(`API POST Error ${response.status}: ${response.statusText} for ${endpoint}`, errorData);
             showStatusMessage(`API Error on update: ${errorData?.error || response.statusText}`, 'danger');
            return null;
        }
        return await response.json();
     } catch (error) {
         console.error(`Network or fetch error for POST to ${endpoint}:`, error);
         showStatusMessage(`Network error during update. Check console.`, 'danger');
         return null;
     }
}

// --- Charting Functions ---
function createOrUpdateChart(chartInstance, canvasId, chartType, chartData, options = {}) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) {
        console.error(`Canvas element with ID ${canvasId} not found.`);
        return null;
     }

    const defaultOptions = {
         responsive: true,
        maintainAspectRatio: false,
         plugins: {
             legend: { display: true, position: 'top' },
             title: { display: false }, // Use card headers instead
             tooltip: {
                callbacks: { // Example custom tooltip
                    label: function(context) {
                         let label = context.dataset.label || '';
                        if (label) label += ': ';
                         if (context.parsed !== null) {
                             // Handle pie/doughnut where parsed is the value
                             let value = context.parsed;
                             // Handle bar/line where parsed is {x, y}
                            if (typeof context.parsed === 'object' && context.parsed.y !== undefined) {
                                 value = context.parsed.y;
                            }
                             label += formatNumber(value); // Use consistent number formatting
                        }
                         return label;
                     }
                }
             }
        }
     };

     // Deep merge options if needed (simple merge here)
     const finalOptions = { ...defaultOptions, ...options };

    if (chartInstance) {
        // Update existing chart
         chartInstance.data.labels = chartData.labels;
         chartInstance.data.datasets[0].data = chartData.values; // Assumes single dataset for updates
         // Could update dataset properties (colors etc.) if needed
         chartInstance.update();
         // console.log(`Chart ${canvasId} updated.`); // Debug
         return chartInstance;
     } else {
        // Create new chart
         // Define default colors - adjust as needed
         const backgroundColors = chartType === 'doughnut' || chartType === 'pie'
            ? ['rgba(220, 53, 69, 0.7)', 'rgba(255, 193, 7, 0.7)', 'rgba(200, 200, 200, 0.7)', 'rgba(108, 117, 125, 0.5)', 'rgba(13, 110, 253, 0.5)', 'rgba(25, 135, 84, 0.5)'] // Bootstrap colors approx
             : ['rgba(13, 110, 253, 0.6)']; // Default bar/line color

         const borderColors = chartType === 'doughnut' || chartType === 'pie'
             ? ['rgba(220, 53, 69, 1)', 'rgba(255, 193, 7, 1)', 'rgba(150, 150, 150, 1)', 'rgba(108, 117, 125, 1)', 'rgba(13, 110, 253, 1)', 'rgba(25, 135, 84, 1)']
             : ['rgba(13, 110, 253, 1)'];

        const chartConfig = {
             type: chartType,
            data: {
                labels: chartData.labels,
                 datasets: [{
                     label: '# of Items', // Default label, override via options if needed
                    data: chartData.values,
                    backgroundColor: backgroundColors.slice(0, chartData.labels.length),
                    borderColor: borderColors.slice(0, chartData.labels.length),
                     borderWidth: 1
                }]
             },
             options: finalOptions
         };
         // console.log(`Creating chart ${canvasId}.`); // Debug
         return new Chart(ctx, chartConfig);
     }
 }

// --- Table Rendering and Interaction ---
function renderAppTable(apps) {
    const tableBody = document.getElementById('app-table-body');
    const tableCount = document.getElementById('app-table-count');
    if (!tableBody || !tableCount) return;

    tableBody.innerHTML = ''; // Clear existing rows
    tableCount.textContent = apps.length; // Update count

     if (apps.length === 0) {
         tableBody.innerHTML = '<tr><td colspan="12" class="text-center">No applications match the criteria.</td></tr>';
         return;
     }

    const fragment = document.createDocumentFragment(); // Efficient DOM manipulation
    apps.forEach((app, index) => {
        const row = document.createElement('tr');
        const riskClass = RISK_LEVEL_CLASSES[app.calculated_risk_level] || 'table-light';
        const statusBadge = STATUS_BADGES[app.status] || 'bg-secondary';
         const resolutionIcon = app.resolution_status ? RESOLUTION_STATUS_ICONS[app.resolution_status] || '' : '<i class="fas fa-question-circle text-muted" title="Not Resolved"></i>';

         // Keep data simple for table display, details in modal
         row.className = riskClass;
         row.innerHTML = `
            <td data-label="Domain">${app.domain}</td>
            <td data-label="App Name">${app.app_name}</td>
            <td data-label="Category">${app.category}</td>
            <td data-label="Status"><span class="badge ${statusBadge}">${app.status}</span></td>
             <td data-label="Risk Level"><b>${app.calculated_risk_level}</b></td>
             <td data-label="Risk Score">${app.calculated_risk_score}</td>
             <td data-label="Accesses">${formatNumber(app.network_access_count)}</td>
             <td data-label="Users">${formatNumber(app.unique_users_network?.length || 0)}</td>
            <td data-label="Upload MB">${formatMB(app.total_data_uploaded_mb)}</td>
            <td data-label="Spend">${formatCurrency(app.linked_expense_total)}</td>
             <td data-label="Resolution" class="text-center">${resolutionIcon}</td>
            <td data-label="Details">
                <button type="button" class="btn btn-outline-primary btn-sm action-details" data-bs-toggle="modal" data-bs-target="#appDetailModal" data-app-id="${app.id}">
                    <i class="fas fa-info-circle"></i>
                </button>
             </td>
        `;
         // Store full app data against the row or button for easy access later
         // Using JS objects is better than embedding all data-* attributes
        row.querySelector('.action-details').appData = app;
        fragment.appendChild(row);
     });
     tableBody.appendChild(fragment);
     // console.log(`Rendered ${apps.length} apps.`); // Debug
 }

function sortTable(apps, column, direction) {
     const sortFunctions = {
        string: (a, b) => direction === 'asc' ? a.localeCompare(b) : b.localeCompare(a),
         number: (a, b) => direction === 'asc' ? a - b : b - a,
         users_count: (a, b) => { // Special case for array length
             const valA = a?.length || 0;
             const valB = b?.length || 0;
             return direction === 'asc' ? valA - valB : valB - valA;
        }
    };

     // Determine sort type based on column name (add more complex logic if needed)
     let sortType = 'string';
    const numberColumns = ['calculated_risk_score', 'network_access_count', 'total_data_uploaded_mb', 'linked_expense_total'];
     if (numberColumns.includes(column)) {
        sortType = 'number';
     } else if (column === 'unique_users_network') {
         sortType = 'users_count'; // Use custom comparator
     }

     apps.sort((a, b) => {
        // Handle potentially missing or null values gracefully
         let valA = a[column] ?? (sortType === 'number' ? 0 : '');
         let valB = b[column] ?? (sortType === 'number' ? 0 : '');

         if (sortType === 'users_count') {
             valA = a[column]; // Pass the array itself to the comparator
             valB = b[column];
         }

         return sortFunctions[sortType](valA, valB);
     });

     renderAppTable(apps);
     updateSortIcons(column, direction);
     // console.log(`Sorted by ${column} (${direction})`); // Debug
}

function updateSortIcons(activeColumn, direction) {
    document.querySelectorAll('#app-table thead th i.fa-sort').forEach(icon => {
        icon.classList.remove('fa-sort-up', 'fa-sort-down');
         const th = icon.closest('th');
        if (th && th.dataset.sort === activeColumn) {
            icon.classList.add(direction === 'asc' ? 'fa-sort-up' : 'fa-sort-down');
         }
    });
 }

 function filterTable() {
     const filterText = document.getElementById('app-table-filter').value.toLowerCase();
    if (!allAppsData || allAppsData.length === 0) return; // No data to filter

     const filteredApps = allAppsData.filter(app => {
         // Simple text search across key fields
        return (
             app.domain.toLowerCase().includes(filterText) ||
             app.app_name.toLowerCase().includes(filterText) ||
            app.category.toLowerCase().includes(filterText) ||
             app.status.toLowerCase().includes(filterText) ||
             app.calculated_risk_level.toLowerCase().includes(filterText)
         );
     });
     // console.log(`Filtering: ${filteredApps.length} apps match "${filterText}"`); // Debug
     renderAppTable(filteredApps);
     // Reapply sort after filtering if needed
     if (currentSortColumn) {
         sortTable(filteredApps, currentSortColumn, currentSortDirection);
     }
 }

// --- Modal Handling ---
 function populateAppDetailModal(app) {
    const modalBody = document.getElementById('modal-content-area');
     const modalTitle = document.getElementById('appDetailModalLabel');
     const modalSpinner = document.getElementById('modal-spinner');
     const modalActionStatus = document.getElementById('modal-action-status');
     if (!modalBody || !modalTitle || !modalSpinner) return;

     modalSpinner.classList.remove('d-none'); // Show spinner
     modalBody.innerHTML = ''; // Clear previous content
     modalActionStatus.textContent = ''; // Clear previous action status

     modalTitle.textContent = `${app.app_name} (${app.domain})`;

     // Simulating a brief load time - remove in production
    // setTimeout(() => {
         modalBody.innerHTML = `
            <div class="row">
                 <div class="col-md-6">
                     <h6><i class="fas fa-shield-halved me-2"></i>Risk Assessment</h6>
                     <p><strong>Level: ${app.calculated_risk_level} (Score: ${app.calculated_risk_score})</strong></p>
                    <ul class="list-unstyled small">
                         ${app.risk_factors && app.risk_factors.length > 0
                            ? app.risk_factors.map(factor => `<li><i class="fas fa-caret-right me-1 text-muted"></i>${factor}</li>`).join('')
                             : '<li>No specific risk factors logged.</li>'
                         }
                     </ul>
                    <hr>
                    <h6><i class="fas fa-cogs me-2"></i>Application Info</h6>
                    <ul class="list-unstyled small">
                        <li><strong>Category:</strong> ${app.category}</li>
                        <li><strong>Internal Status:</strong> ${app.status}</li>
                        <li><strong>Resolution Status:</strong> ${app.resolution_status || 'None'}</li>
                         <li><strong>GDPR Compliant:</strong> ${app.compliance_gdpr ? '<i class="fas fa-check text-success"></i>' : '<i class="fas fa-times text-danger"></i>'}</li>
                         <li><strong>HIPAA Compliant:</strong> ${app.compliance_hipaa ? '<i class="fas fa-check text-success"></i>' : '<i class="fas fa-times text-danger"></i>'}</li>
                         <li><strong>Known Breach History:</strong> ${app.known_breach ? '<i class="fas fa-exclamation-triangle text-warning"></i> Yes' : '<i class="fas fa-check text-success"></i> No'}</li>
                     </ul>
                 </div>
                <div class="col-md-6">
                    <h6><i class="fas fa-network-wired me-2"></i>Usage Information</h6>
                     <ul class="list-unstyled small">
                         <li><strong>Access Count:</strong> ${formatNumber(app.network_access_count)}</li>
                        <li><strong>Unique Users (${app.unique_users_network?.length || 0}):</strong>
                             <span class="user-list-modal">${app.unique_users_network?.join(', ') || 'N/A'}</span>
                        </li>
                         <li><strong>Total Data Uploaded:</strong> ${formatMB(app.total_data_uploaded_mb)} MB</li>
                        <li><strong>Total Data Downloaded:</strong> ${formatMB(app.total_data_downloaded_mb)} MB</li>
                        <li><strong>First Seen:</strong> ${formatDate(app.first_seen_network)}</li>
                         <li><strong>Last Seen:</strong> ${formatDate(app.last_seen_network)}</li>
                     </ul>
                     <hr>
                    <h6><i class="fas fa-file-invoice-dollar me-2"></i>Financial Information</h6>
                    <ul class="list-unstyled small">
                        <li><strong>Linked Expense Count:</strong> ${formatNumber(app.linked_expense_count)}</li>
                         <li><strong>Linked Expense Total:</strong> ${formatCurrency(app.linked_expense_total)}</li>
                     </ul>
                </div>
            </div>
         `;
        modalSpinner.classList.add('d-none'); // Hide spinner

         // Store the current app ID on the modal for action buttons
         document.getElementById('appDetailModal').dataset.currentAppId = app.id;

    // }, 50); // End simulated delay
 }


// --- Initialization and Data Loading ---
 async function initializeDashboard() {
    console.log("Initializing Dashboard...");
    document.getElementById('last-updated').textContent = `Updating...`;

     // Fetch all data in parallel
    const [stats, apps, behavior, riskChartData, spendChartData, trendChartData] = await Promise.all([
         fetchData(API_ENDPOINTS.stats),
         fetchData(API_ENDPOINTS.apps),
        fetchData(API_ENDPOINTS.behavior),
        fetchData(API_ENDPOINTS.riskChart),
         fetchData(API_ENDPOINTS.spendChart),
         fetchData(API_ENDPOINTS.trendChart),
     ]);

    document.getElementById('last-updated').textContent = `Updated: ${moment().format('HH:mm:ss')}`;

     // --- Update KPIs ---
    if (stats) {
        document.getElementById('kpi-total-detected').textContent = formatNumber(stats.total_detected);
         document.getElementById('kpi-shadow-count').textContent = formatNumber(stats.shadow_count);
         document.getElementById('kpi-high-risk').textContent = formatNumber(stats.high_risk);
        document.getElementById('kpi-medium-risk').textContent = formatNumber(stats.medium_risk);
        // document.getElementById('kpi-low-risk').textContent = formatNumber(stats.low_risk); // If you add this back
        document.getElementById('kpi-linked-spend').textContent = formatCurrency(stats.linked_spend);
    }

    // --- Render Table ---
    if (apps) {
         allAppsData = apps; // Store full dataset
        renderAppTable(allAppsData); // Render initial full table
         filterTable(); // Apply filter immediately if needed (initially empty filter)
     } else {
        // Handle error case - show message in table
         document.getElementById('app-table-body').innerHTML = '<tr><td colspan="12" class="text-center text-danger">Error loading application data.</td></tr>';
     }

    // --- Create/Update Charts ---
    if (riskChartData) {
         riskDistributionChart = createOrUpdateChart(
            riskDistributionChart,
            'riskDistributionChart',
            'doughnut',
            riskChartData,
            { plugins: { legend: { position: 'right' } } }
         );
     }
     if (spendChartData) {
        spendByCategoryChart = createOrUpdateChart(
             spendByCategoryChart,
            'spendByCategoryChart',
             'bar', // Bar chart for spend
             spendChartData,
            {
                indexAxis: 'y', // Horizontal bar chart
                 plugins: { legend: { display: false } },
                 scales: { x: { beginAtZero: true } }
             }
         );
    }
     if (trendChartData) {
        usageTrendChart = createOrUpdateChart(
            usageTrendChart,
            'usageTrendChart',
             'line', // Line chart for trend
            trendChartData,
            {
                 plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true } }
             }
        );
     }

     // --- Update Behavior Insights ---
    const topUsersList = document.getElementById('top-users-app-count');
     const highUploadList = document.getElementById('high-upload-apps');
    if (behavior && topUsersList && highUploadList) {
         topUsersList.innerHTML = behavior.top_shadow_users_by_app_count.length > 0
             ? behavior.top_shadow_users_by_app_count.map(item => `<li>${item[0]} (${item[1]} apps)</li>`).join('')
            : '<li>No significant shadow IT usage detected.</li>';

         highUploadList.innerHTML = behavior.apps_with_high_data_upload.length > 0
            ? behavior.apps_with_high_data_upload.map(item => `<li>${item.app_name} (${item.domain}): ${formatMB(item.uploaded_mb)} MB</li>`).join('')
            : '<li>No apps with high data uploads detected.</li>';
     } else if (topUsersList && highUploadList) {
        topUsersList.innerHTML = '<li>Error loading insights.</li>';
         highUploadList.innerHTML = '<li>Error loading insights.</li>';
     }

     console.log("Dashboard Initialized.");
 }


// --- Event Listeners ---
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM Loaded. Initializing...");

    // --- Initial Data Load ---
    initializeDashboard();

    // --- Table Filtering ---
    const filterInput = document.getElementById('app-table-filter');
    if (filterInput) {
         filterInput.addEventListener('keyup', filterTable);
     }

     // --- Table Sorting ---
    const tableHeaders = document.querySelectorAll('#app-table thead th[data-sort]');
     tableHeaders.forEach(th => {
        th.addEventListener('click', () => {
            const column = th.dataset.sort;
            if (column === 'none') return; // Ignore columns marked as non-sortable

             let direction = 'asc';
             // If clicking the same column, reverse direction
            if (currentSortColumn === column && currentSortDirection === 'asc') {
                 direction = 'desc';
             }

            currentSortColumn = column;
             currentSortDirection = direction;

            // Use the currently filtered data if a filter is active, else use all data
            const filterText = document.getElementById('app-table-filter').value.toLowerCase();
             const dataToSort = filterText
                 ? allAppsData.filter(app => (
                     app.domain.toLowerCase().includes(filterText) ||
                     app.app_name.toLowerCase().includes(filterText) ||
                     app.category.toLowerCase().includes(filterText) ||
                    app.status.toLowerCase().includes(filterText) ||
                     app.calculated_risk_level.toLowerCase().includes(filterText)
                 ))
                : [...allAppsData]; // Sort a copy

             sortTable(dataToSort, column, direction);
         });
    });

    // --- Modal Population ---
    document.getElementById('appDetailModal').addEventListener('show.bs.modal', (event) => {
         const button = event.relatedTarget; // Button that triggered the modal
        // Access the data stored earlier
         const appData = button ? button.appData : null;

        if (appData) {
            populateAppDetailModal(appData);
         } else {
             console.error("Could not get app data for modal.");
            // Display error in modal
            const modalBody = document.getElementById('modal-content-area');
             modalBody.innerHTML = '<p class="text-danger">Error: Could not load application details.</p>';
        }
     });

    // --- Modal Workflow Actions ---
    const modalActionButtons = document.querySelectorAll('.modal-action-button');
     modalActionButtons.forEach(button => {
        button.addEventListener('click', async (event) => {
            const action = event.target.dataset.action;
            const appId = document.getElementById('appDetailModal').dataset.currentAppId;
             const statusIndicator = document.getElementById('modal-action-status');

             if (!appId || !action) {
                 showStatusMessage("Error identifying app or action.", 'danger');
                return;
             }

            statusIndicator.textContent = `Updating to ${action}...`;
            event.target.disabled = true; // Disable button while processing

            const endpoint = API_ENDPOINTS.resolveApp.replace(':app_id', appId);
             const result = await postData(endpoint, { resolution_status: action });

             event.target.disabled = false; // Re-enable button
             statusIndicator.textContent = ''; // Clear status indicator

            if (result && result.success) {
                 showStatusMessage(result.message, 'success');
                appDetailModal.hide(); // Close modal on success
                 // Refresh dashboard data to show the change
                 initializeDashboard(); // Re-fetch everything
             } else {
                // Error message already shown by postData
                 console.error("Failed to update resolution status via API");
            }
        });
     });

}); // End DOMContentLoaded