<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
const cpuHistoryLabels = <?php echo json_encode($time_labels); ?>;
const cpuHistoryData = <?php echo json_encode($cpu_history); ?>;
const memHistoryData = <?php echo json_encode(array_map(function($b) { return round($b/1048576,2); }, $mem_history)); ?>;
const totalMem = <?php echo round($total_memory/1048576,2); ?>;

// CPU Line Chart
new Chart(document.getElementById('cpuHistoryChart'), {
    type: 'line',
    data: {
        labels: cpuHistoryLabels,
        datasets: [{
            label: 'CPU Load (%)',
            data: cpuHistoryData,
            borderColor: '#007bff',
            backgroundColor: 'rgba(0, 123, 255, 0.1)',
            fill: true,
            tension: 0.4,
            pointRadius: 2
        }]
    },
    options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            y: { beginAtZero: true, max: 100, title: { display: true, text: '%' } }
        }
    }
});

// Memory Line Chart
new Chart(document.getElementById('memHistoryChart'), {
    type: 'line',
    data: {
        labels: cpuHistoryLabels,
        datasets: [{
            label: 'Memory Used (MB)',
            data: memHistoryData,
            borderColor: '#28a745',
            backgroundColor: 'rgba(40, 167, 69, 0.1)',
            fill: true,
            tension: 0.4,
            pointRadius: 2
        }]
    },
    options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            y: { beginAtZero: true, max: totalMem, title: { display: true, text: 'MB' } }
        }
    }
});
</script>
