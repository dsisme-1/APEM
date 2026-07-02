let chartInstance = null;

// Fungsi otomatis berjalan saat halaman pertama kali dimuat
document.addEventListener("DOMContentLoaded", () => {
    initChart();
    fetchDashboardData();
    // Jalankan polling otomatis rutin setiap 3 detik sekali
    setInterval(fetchDashboardData, 3000);
});

// 1. INISIALISASI GRAFIK CHART.JS CHANNELS
function initChart() {
    const ctx = document.getElementById('trendsChart').getContext('2d');
    chartInstance = new Chart(ctx, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Jumlah Kicauan Terdeteksi', data: [], borderColor: '#3498db', tension: 0.2, fill: true, backgroundColor: 'rgba(52, 152, 219, 0.05)' }] },
        options: { responsive: true, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
    });
}

// 2. FETCH DATA DASHBOARD UTAMA (REST API POLLING)
async function fetchDashboardData() {
    try {
        const response = await fetch('/api/dashboard');
        const data = await response.json();

        // Update metrik atas
        document.getElementById('metric-today').innerText = data.total_detections_today;
        document.getElementById('metric-species').innerText = data.unique_species_count;
        document.getElementById('metric-latency').innerText = data.average_latency_ms + " ms";
        document.getElementById('lora-queue-val').innerText = data.lora_queue_count + " Paket";

        // Update status badge pemantauan mikrofon
        const badge = document.getElementById('system-status-badge');
        const btnStart = document.getElementById('btn-start');
        const btnStop = document.getElementById('btn-stop');

        if (data.monitor_active) {
            badge.innerText = `STATUS: ${data.monitor_state}`;
            badge.className = "badge badge-active";
            btnStart.disabled = true;
            btnStop.disabled = false;
        } else {
            badge.innerText = "STATUS: IDLE";
            badge.className = "badge badge-idle";
            btnStart.disabled = false;
            btnStop.disabled = true;
        }

        // Update status telemetri lora
        document.getElementById('lora-status-text').innerText = data.lora_enabled ? "🟢 Connected / Active" : "⚪ Disabled (Pasif Queue)";

        // Update grafik tren
        const labels = data.chart_data.map(item => item.date);
        const values = data.chart_data.map(item => item.total);
        chartInstance.data.labels = labels;
        chartInstance.data.datasets[0].data = values;
        chartInstance.update();

        // Update tabel log riwayat deteksi terbaru
        const tableBody = document.getElementById('detections-table-body');
        if (data.latest_detections.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">Belum ada rekaman data burung di SQLite database.</td></tr>`;
            return;
        }

        tableBody.innerHTML = data.latest_detections.map(row => {
            const timeFormatted = new Date(row.timestamp).toLocaleTimeString('id-ID', {hour: '2-digit', minute:'2-digit', second:'2-digit'});
            return `
                <tr>
                    <td>${timeFormatted}</td>
                    <td><span class="highlight">${row.audio_source}</span></td>
                    <td><em>${row.species}</em></td>
                    <td><strong>${(row.confidence * 100).toFixed(1)}%</strong></td>
                    <td>${row.latency_ms.toFixed(1)} ms</td>
                </tr>
            `;
        }).join('');

    } catch (error) {
        console.error("Gagal melakukan Sinkronisasi data REST API:", error);
    }
}

// 3. SAKELAR ON/OFF KENDALI BACKGROUND REALTIME STATE MACHINE
async function toggleMonitoring(enable) {
    try {
        const response = await fetch('/api/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable: enable })
        });
        const resData = await response.json();
        if (resData.success) {
            fetchDashboardData();
        }
    } catch (error) {
        alert("Gagal mengirimkan instruksi sakelar kendali hardware.");
    }
}

// 4. HANDLING UNGGAL BERKAS AUDIO MANUAL VIA REST API
async function handleManualUpload(event) {
    event.preventDefault();
    const fileInput = document.getElementById('audio-file');
    const btnUpload = document.getElementById('btn-upload');
    const resultBox = document.getElementById('upload-result');

    if (fileInput.files.length === 0) return;

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    btnUpload.disabled = true;
    btnUpload.innerText = "Menganalisis...";
    resultBox.classList.remove('hidden');
    resultBox.innerHTML = "<em>Sedang memproses berkas WAV...</em>";

    try {
        const response = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await response.json();

        if (data.status === "success") {
            if (data.detections_count === 0) {
                resultBox.innerHTML = `<strong>Hasil Analisis:</strong><br><span style="color:red">⚠️ Tidak ada kicauan burung terdeteksi di atas batas threshold.</span>`;
            } else {
                let htmlRes = `<strong>Hasil Deteksi (${data.detections_count}):</strong><br><ul>`;
                data.detections.forEach(d => {
                    htmlRes += `<li>🐦 <em>${d.label}</em> - Akurasi: ${(d.confidence*100).toFixed(1)}% (${d.latency_ms.toFixed(1)}ms)</li>`;
                });
                htmlRes += `</ul>`;
                resultBox.innerHTML = htmlRes;
            }
            fetchDashboardData(); // Segarkan tampilan tabel log secara instan
        } else {
            resultBox.innerHTML = `<span style="color:red">Gagal menganalisis berkas.</span>`;
        }
    } catch (error) {
        resultBox.innerHTML = `<span style="color:red">Terjadi gangguan koneksi server API.</span>`;
    } finally {
        btnUpload.disabled = false;
        btnUpload.innerText = "Analisis Audio";
        fileInput.value = ""; // Reset input file
    }
}