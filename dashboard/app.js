// Monitor Listrik Pintar - Dashboard Application
(function () {
    "use strict";

    // State
    const urlParams = new URLSearchParams(window.location.search);
    const tokenFromUrl = urlParams.get("token");
    let authToken = tokenFromUrl || sessionStorage.getItem("token") || localStorage.getItem("token") || "";
    if (tokenFromUrl) {
        sessionStorage.setItem("token", authToken);
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    let activeDeviceId = "";
    let devicesList = [];
    let currentSettings = null;
    let pollTimer = null;
    let powerChartInstance = null;
    let dailyChartInstance = null;
    let currentPowerRange = "5h"; // 5h, 24h, 3d, 30d

    // DOM Elements
    const loginModal = document.getElementById("login-modal");
    const loginForm = document.getElementById("login-form");
    const passwordInput = document.getElementById("password-input");
    const loginError = document.getElementById("login-error");
    const appContainer = document.getElementById("app-container");
    const btnLogout = document.getElementById("btn-logout");
    const deviceSelect = document.getElementById("device-select");
    const deviceStatusBadge = document.getElementById("device-status-badge");
    const warningBanner = document.getElementById("warning-banner");
    const warningBannerText = document.getElementById("warning-banner-text");

    // Real-time elements
    const valPower = document.getElementById("val-power");
    const powerProgressFill = document.getElementById("power-progress-fill");
    const powerProgressText = document.getElementById("power-progress-text");
    const valVoltage = document.getElementById("val-voltage");
    const valFreq = document.getElementById("val-freq");
    const valCurrent = document.getElementById("val-current");
    const valPf = document.getElementById("val-pf");
    const valRssi = document.getElementById("val-rssi");
    const valLastSeen = document.getElementById("val-last-seen");

    // Energy / Cost elements
    const todayCost = document.getElementById("today-cost");
    const todayKwh = document.getElementById("today-kwh");
    const todayPeak = document.getElementById("today-peak");
    const badgeTodayEstimated = document.getElementById("badge-today-estimated");

    const weekCost = document.getElementById("week-cost");
    const weekKwh = document.getElementById("week-kwh");
    const weekAvg = document.getElementById("week-avg");

    const monthCost = document.getElementById("month-cost");
    const monthKwh = document.getElementById("month-kwh");
    const monthPeak = document.getElementById("month-peak");

    const forecastCost = document.getElementById("forecast-cost");
    const forecastKwh = document.getElementById("forecast-kwh");
    const forecastNote = document.getElementById("forecast-note");
    const forecastStatusTag = document.getElementById("forecast-status-tag");

    // Settings Modal elements
    const settingsModal = document.getElementById("settings-modal");
    const btnOpenSettings = document.getElementById("btn-open-settings");
    const btnCloseSettings = document.getElementById("btn-close-settings");
    const btnCancelSettings = document.getElementById("btn-cancel-settings");
    const settingsForm = document.getElementById("settings-form");
    const inputTariff = document.getElementById("input-tariff");
    const inputPowerLimit = document.getElementById("input-power-limit");
    const inputMcbInfo = document.getElementById("input-mcb-info");
    const inputCooldown = document.getElementById("input-cooldown");
    const inputExtraPercent = document.getElementById("input-extra-percent");
    const inputReportHour = document.getElementById("input-report-hour");
    const settingsStatus = document.getElementById("settings-status");

    // Formatters (Strict Intl Asia/Jakarta)
    const formatRp = (val) => {
        if (val === null || val === undefined || isNaN(val)) return "Rp -";
        return new Intl.NumberFormat("id-ID", {
            style: "currency",
            currency: "IDR",
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        }).format(val);
    };

    const formatNum = (val, decimals = 1) => {
        if (val === null || val === undefined || isNaN(val)) return "-";
        return new Intl.NumberFormat("id-ID", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        }).format(val);
    };

    const formatTimeWIB = (epochSec) => {
        if (!epochSec) return "-";
        return new Intl.DateTimeFormat("id-ID", {
            timeZone: "Asia/Jakarta",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        }).format(new Date(epochSec * 1000));
    };

    const formatDateTimeWIB = (epochSec) => {
        if (!epochSec) return "-";
        return new Intl.DateTimeFormat("id-ID", {
            timeZone: "Asia/Jakarta",
            day: "numeric",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
        }).format(new Date(epochSec * 1000));
    };

    const formatDateWIB = (epochSec) => {
        if (!epochSec) return "-";
        return new Intl.DateTimeFormat("id-ID", {
            timeZone: "Asia/Jakarta",
            day: "numeric",
            month: "short",
        }).format(new Date(epochSec * 1000));
    };

    // API Client Helper
    async function apiRequest(endpoint, options = {}) {
        const headers = options.headers || {};
        if (authToken) {
            headers["Authorization"] = `Bearer ${authToken}`;
        }
        if (options.body && typeof options.body === "object") {
            headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(options.body);
        }
        options.headers = headers;

        try {
            const resp = await fetch(endpoint, options);
            if (resp.status === 401) {
                // Sesi habis atau token tidak valid
                handleLogout();
                throw new Error("Sesi telah berakhir. Silakan login kembali.");
            }
            if (resp.status === 429) {
                const retryAfter = resp.headers.get("Retry-After") || "30";
                const errData = await resp.json().catch(() => ({}));
                const msg = errData?.error?.message || `Terlalu banyak percobaan. Coba lagi dalam ${retryAfter} detik.`;
                throw new Error(msg);
            }
            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                const msg = errData?.error?.message || `Error ${resp.status}: Permintaan gagal.`;
                throw new Error(msg);
            }
            return await resp.json();
        } catch (err) {
            throw err;
        }
    }

    // Auth Handlers
    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        loginError.classList.add("hidden");
        loginError.textContent = "";

        const password = passwordInput.value;
        try {
            const data = await apiRequest("/api/login", {
                method: "POST",
                body: { password },
            });
            authToken = data.token;
            sessionStorage.setItem("token", authToken);
            loginModal.classList.add("hidden");
            appContainer.classList.remove("hidden");
            passwordInput.value = "";
            await initApp();
        } catch (err) {
            loginError.textContent = err.message;
            loginError.classList.remove("hidden");
        }
    });

    btnLogout.addEventListener("click", () => {
        handleLogout();
    });

    function handleLogout() {
        stopPolling();
        authToken = "";
        sessionStorage.removeItem("token");
        localStorage.removeItem("token");
        appContainer.classList.add("hidden");
        loginModal.classList.remove("hidden");
    }

    // App Initialization
    async function initApp() {
        try {
            await loadSettings();
            await loadDevices();
            startPolling();
            await loadSummaryCards();
            await loadForecast();
            await loadPowerChart(currentPowerRange);
            await loadDailyChart();
        } catch (err) {
            console.error("Gagal inisialisasi aplikasi:", err);
        }
    }

    // Settings
    async function loadSettings() {
        try {
            currentSettings = await apiRequest("/api/settings");
            updateWarningBanner();
        } catch (err) {
            console.error("Gagal memuat pengaturan:", err);
        }
    }

    function updateWarningBanner() {
        if (!currentSettings || !activeDeviceId) return;
        const curDev = devicesList.find((d) => d.id === activeDeviceId);
        if (!curDev) return;

        const pLimit = parseInt(currentSettings.power_limit_w, 10);
        const mcbWatt = parseInt(curDev.mcb_watt, 10);

        if (pLimit > mcbWatt) {
            warningBannerText.textContent = `Peringatan: Batas daya PLN (${pLimit} W) melebihi kapasitas MCB perangkat (${mcbWatt} W)!`;
            warningBanner.classList.remove("hidden");
        } else {
            warningBanner.classList.add("hidden");
            warningBannerText.textContent = "";
        }
    }

    // Devices
    async function loadDevices() {
        devicesList = await apiRequest("/api/devices");
        deviceSelect.replaceChildren();

        if (devicesList.length === 0) {
            const opt = document.createElement("option");
            opt.value = "";
            opt.textContent = "Tidak ada perangkat terdaftar";
            deviceSelect.appendChild(opt);
            return;
        }

        devicesList.forEach((d) => {
            const opt = document.createElement("option");
            opt.value = d.id;
            opt.textContent = `${d.name || d.id} (${d.mcb_watt} W)`;
            deviceSelect.appendChild(opt);
        });

        // Set default device (prefer sim-warung if present)
        if (!activeDeviceId || !devicesList.some((d) => d.id === activeDeviceId)) {
            const defaultDev = devicesList.find((d) => d.id === "sim-warung") || devicesList[0];
            activeDeviceId = defaultDev.id;
        }
        deviceSelect.value = activeDeviceId;
        updateDeviceStatusBadge();
        updateWarningBanner();
    }

    function updateDeviceStatusBadge(lastDataTs) {
        const curDev = devicesList.find((d) => d.id === activeDeviceId);
        if (!curDev) return;

        const ts = lastDataTs || curDev.last_data_ts;
        const nowSec = Math.floor(Date.now() / 1000);
        const isStale = ts ? (nowSec - ts) > 30 : true;

        if (curDev.status === "online" && !isStale) {
            deviceStatusBadge.textContent = "Online";
            deviceStatusBadge.className = "badge badge-online";
        } else {
            if (ts) {
                deviceStatusBadge.textContent = `Offline, data terakhir ${formatDateTimeWIB(ts)} WIB`;
            } else {
                deviceStatusBadge.textContent = "Offline (belum ada data)";
            }
            deviceStatusBadge.className = "badge badge-offline";
        }
    }

    deviceSelect.addEventListener("change", async (e) => {
        activeDeviceId = e.target.value;
        updateDeviceStatusBadge();
        updateWarningBanner();
        await pollLatest();
        await loadSummaryCards();
        await loadForecast();
        await loadPowerChart(currentPowerRange);
        await loadDailyChart();
    });

    // Polling Real-time (every 5 seconds) - kartu real-time & summary hari ini saja
    async function pollLatest() {
        if (!activeDeviceId) return;
        try {
            const latest = await apiRequest(`/api/devices/${activeDeviceId}/latest`);
            if (latest) {
                renderRealtimeData(latest);
                updateDeviceStatusBadge(latest.ts);
            }
        } catch (err) {
            console.error("Gagal mengambil data terbaru:", err);
        }

        try {
            // Perbarui juga data ringkasan hari ini agar biaya real-time berjalan
            const sumToday = await apiRequest(`/api/devices/${activeDeviceId}/summary?range=today`);
            if (sumToday) {
                renderTodaySummary(sumToday);
            }
        } catch (err) {
            console.error("Gagal memperbarui summary hari ini:", err);
        }
    }

    function renderRealtimeData(d) {
        valPower.textContent = `${formatNum(d.p, 1)} W`;
        valVoltage.textContent = `${formatNum(d.v, 1)} V`;
        valFreq.textContent = `Frekuensi: ${formatNum(d.f, 1)} Hz`;
        valCurrent.textContent = `${formatNum(d.i, 2)} A`;
        valPf.textContent = `Power Factor: ${formatNum(d.pf, 2)}`;
        valRssi.textContent = `${d.rssi} dBm`;
        valLastSeen.textContent = `Update: ${formatTimeWIB(d.ts)}`;

        // Progress bar batas daya
        if (currentSettings && currentSettings.power_limit_w) {
            const limit = parseFloat(currentSettings.power_limit_w);
            const pct = Math.min(100, Math.max(0, (d.p / limit) * 100));
            powerProgressFill.style.width = `${pct.toFixed(1)}%`;
            powerProgressText.textContent = `${pct.toFixed(0)}% dari ${limit} W`;

            if (pct >= 90) {
                powerProgressFill.style.backgroundColor = "var(--danger)";
            } else if (pct >= 75) {
                powerProgressFill.style.backgroundColor = "var(--warning)";
            } else {
                powerProgressFill.style.backgroundColor = "var(--primary)";
            }
        }
    }

    function renderTodaySummary(d) {
        todayCost.textContent = formatRp(d.cost_rp);
        todayKwh.textContent = `${formatNum(d.kwh, 3)} kWh`;
        if (d.peak_w > 0 && d.peak_ts) {
            todayPeak.textContent = `Puncak: ${formatNum(d.peak_w, 1)} W (${formatTimeWIB(d.peak_ts)})`;
        } else {
            todayPeak.textContent = "Puncak: - W";
        }
        if (d.cost_estimated) {
            badgeTodayEstimated.classList.remove("hidden");
        } else {
            badgeTodayEstimated.classList.add("hidden");
        }
    }

    async function loadSummaryCards() {
        if (!activeDeviceId) return;

        // 1. Today
        try {
            const sumToday = await apiRequest(`/api/devices/${activeDeviceId}/summary?range=today`);
            renderTodaySummary(sumToday);
        } catch (err) {
            console.error("Gagal load summary today:", err);
        }

        // 2. Week
        try {
            const sumWeek = await apiRequest(`/api/devices/${activeDeviceId}/summary?range=week`);
            weekCost.textContent = formatRp(sumWeek.cost_rp);
            weekKwh.textContent = `${formatNum(sumWeek.kwh, 3)} kWh`;
            weekAvg.textContent = `Rata-rata: ${formatNum(sumWeek.avg_power_w, 1)} W`;
        } catch (err) {
            console.error("Gagal load summary week:", err);
        }

        // 3. Month
        try {
            const sumMonth = await apiRequest(`/api/devices/${activeDeviceId}/summary?range=month`);
            monthCost.textContent = formatRp(sumMonth.cost_rp);
            monthKwh.textContent = `${formatNum(sumMonth.kwh, 3)} kWh`;
            monthPeak.textContent = `Puncak: ${formatNum(sumMonth.peak_w, 1)} W`;
        } catch (err) {
            console.error("Gagal load summary month:", err);
        }
    }

    async function loadForecast() {
        if (!activeDeviceId) return;
        try {
            const fc = await apiRequest(`/api/devices/${activeDeviceId}/forecast`);
            if (!fc || !fc.available) {
                forecastCost.textContent = "belum tersedia";
                forecastKwh.textContent = "-";
                forecastNote.textContent = "Data hari penuh belum mencukupi (< 1 hari)";
                forecastStatusTag.textContent = "Belum Tersedia";
                forecastStatusTag.className = "badge-mini";
                return;
            }

            forecastCost.textContent = formatRp(fc.projected_cost_rp);
            forecastKwh.textContent = `${formatNum(fc.projected_kwh, 2)} kWh`;

            if (fc.low_confidence) {
                forecastStatusTag.textContent = "perkiraan kasar";
                forecastStatusTag.className = "badge-mini badge-est";
                forecastNote.textContent = `Basis data terbatas (${fc.basis_days} hari)`;
            } else {
                forecastStatusTag.textContent = `Basis ${fc.basis_days} Hari`;
                forecastStatusTag.className = "badge-mini";
                forecastNote.textContent = `Rata-rata: ${formatNum(fc.avg_daily_kwh, 2)} kWh/hari`;
            }
        } catch (err) {
            console.error("Gagal memuat proyeksi:", err);
        }
    }

    // Chart Management
    async function loadPowerChart(rangeCode) {
        if (!activeDeviceId) return;
        currentPowerRange = rangeCode;

        const nowSec = Math.floor(Date.now() / 1000);
        let fromSec = nowSec - 5 * 3600;
        let resParam = "raw";

        if (rangeCode === "5h") {
            fromSec = nowSec - 5 * 3600;
            resParam = "raw";
        } else if (rangeCode === "24h") {
            fromSec = nowSec - 24 * 3600;
            resParam = "5m";
        } else if (rangeCode === "3d") {
            fromSec = nowSec - 3 * 86400;
            resParam = "5m";
        } else if (rangeCode === "30d") {
            fromSec = nowSec - 30 * 86400;
            resParam = "1h";
        }

        try {
            const seriesData = await apiRequest(
                `/api/devices/${activeDeviceId}/series?from=${fromSec}&to=${nowSec}&resolution=${resParam}`
            );
            renderPowerChart(seriesData.points || []);
        } catch (err) {
            console.error("Gagal memuat series daya:", err);
        }
    }

    function renderPowerChart(points) {
        const ctx = document.getElementById("powerChart").getContext("2d");
        const labels = points.map((p) => {
            if (currentPowerRange === "5h") return formatTimeWIB(p.ts);
            return formatDateTimeWIB(p.ts);
        });
        const dataValues = points.map((p) => p.p);

        if (powerChartInstance) {
            powerChartInstance.destroy();
        }

        powerChartInstance = new Chart(ctx, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "Daya Aktif (Watt)",
                        data: dataValues,
                        borderColor: "#38bdf8",
                        backgroundColor: "rgba(56, 189, 248, 0.1)",
                        borderWidth: 2,
                        tension: 0.2,
                        pointRadius: points.length > 100 ? 0 : 2,
                        fill: true,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: {
                        ticks: { color: "#94a3b8", maxTicksLimit: 8 },
                        grid: { color: "rgba(51, 65, 85, 0.5)" },
                    },
                    y: {
                        ticks: { color: "#94a3b8" },
                        grid: { color: "rgba(51, 65, 85, 0.5)" },
                    },
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: "index",
                        intersect: false,
                    },
                },
            },
        });
    }

    async function loadDailyChart() {
        if (!activeDeviceId) return;
        const nowSec = Math.floor(Date.now() / 1000);
        const fromSec = nowSec - 14 * 86400;

        try {
            const seriesData = await apiRequest(
                `/api/devices/${activeDeviceId}/series?from=${fromSec}&to=${nowSec}&resolution=1d`
            );
            renderDailyChart(seriesData.points || []);
        } catch (err) {
            console.error("Gagal memuat daily chart:", err);
        }
    }

    function renderDailyChart(points) {
        const ctx = document.getElementById("dailyChart").getContext("2d");
        const labels = points.map((p) => formatDateWIB(p.ts));
        // Estimasi kWh harian = (rata-rata watt * 24) / 1000
        const dataKwh = points.map((p) => parseFloat(((p.p * 24.0) / 1000.0).toFixed(2)));

        if (dailyChartInstance) {
            dailyChartInstance.destroy();
        }

        dailyChartInstance = new Chart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Konsumsi Harian (kWh)",
                        data: dataKwh,
                        backgroundColor: "rgba(56, 189, 248, 0.8)",
                        borderRadius: 4,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: {
                        ticks: { color: "#94a3b8" },
                        grid: { display: false },
                    },
                    y: {
                        ticks: { color: "#94a3b8" },
                        grid: { color: "rgba(51, 65, 85, 0.5)" },
                    },
                },
                plugins: {
                    legend: { display: false },
                },
            },
        });
    }

    // Range Button Toggles
    const rangeButtons = document.querySelectorAll("#power-range-buttons .btn-toggle");
    rangeButtons.forEach((btn) => {
        btn.addEventListener("click", async () => {
            rangeButtons.forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            const range = btn.dataset.range;
            await loadPowerChart(range);
        });
    });

    let chartTimer = null;

    async function refreshPeriodicChartsAndSummaries() {
        if (!activeDeviceId) return;
        try {
            await loadDevices();
            await loadSummaryCards();
            await loadForecast();
            await loadPowerChart(currentPowerRange);
            await loadDailyChart();
        } catch (err) {
            console.error("Gagal refresh grafik periodik (60s):", err);
        }
    }

    // Polling Lifecycle & Visibility API (Pause when tab is hidden)
    function startPolling() {
        stopPolling();
        pollLatest();
        pollTimer = setInterval(pollLatest, 5000);
        chartTimer = setInterval(refreshPeriodicChartsAndSummaries, 60000);
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
        if (chartTimer) {
            clearInterval(chartTimer);
            chartTimer = null;
        }
    }

    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden") {
            stopPolling();
        } else if (authToken) {
            startPolling();
        }
    });

    // Settings Modal
    btnOpenSettings.addEventListener("click", () => {
        if (!currentSettings) return;
        const curDev = devicesList.find((d) => d.id === activeDeviceId);
        inputTariff.value = (parseInt(currentSettings.tariff_sen_per_kwh, 10) / 100.0).toFixed(2);
        inputPowerLimit.value = currentSettings.power_limit_w;
        inputMcbInfo.value = curDev ? `${curDev.mcb_watt} W` : "-";
        inputCooldown.value = currentSettings.alert_cooldown_min;
        inputExtraPercent.value = currentSettings.extra_percent;
        inputReportHour.value = currentSettings.report_hour;

        settingsStatus.classList.add("hidden");
        settingsStatus.textContent = "";
        settingsModal.classList.remove("hidden");
    });

    function closeSettingsModal() {
        settingsModal.classList.add("hidden");
    }

    btnCloseSettings.addEventListener("click", closeSettingsModal);
    btnCancelSettings.addEventListener("click", closeSettingsModal);

    settingsForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        settingsStatus.classList.add("hidden");
        settingsStatus.textContent = "";

        const payload = {
            tariff_rp: inputTariff.value.trim(),
            power_limit_w: parseInt(inputPowerLimit.value, 10),
            alert_cooldown_min: parseInt(inputCooldown.value, 10),
            extra_percent: parseFloat(inputExtraPercent.value),
            report_hour: parseInt(inputReportHour.value, 10),
        };

        try {
            const updated = await apiRequest("/api/settings", {
                method: "PATCH",
                body: payload,
            });
            currentSettings = updated;
            updateWarningBanner();
            settingsStatus.className = "status-msg";
            settingsStatus.textContent = "Pengaturan berhasil disimpan!";
            settingsStatus.classList.remove("hidden");
            setTimeout(closeSettingsModal, 1200);

            // Perbarui ringkasan dengan tarif baru
            await loadSummaryCards();
            await loadForecast();
        } catch (err) {
            settingsStatus.className = "error-msg";
            settingsStatus.textContent = err.message;
            settingsStatus.classList.remove("hidden");
        }
    });

    // Auto-login check on page load
    if (authToken) {
        loginModal.classList.add("hidden");
        appContainer.classList.remove("hidden");
        initApp();
    }
})();

