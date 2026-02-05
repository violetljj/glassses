/**
 * ============================================
 * 辅助视觉系统前端控制器 (Frontend Controller)
 * ============================================
 */

// 自动检测后端地址：
// 1. 如果当前端口是 5500 (Live Server)，则假设后端在同域名的 5000 端口
// 2. 否则，假设后端与前端同源 (Flask 托管)
const isLiveServer = window.location.port === "5500";
const DEFAULT_BASE = isLiveServer
    ? `${window.location.protocol}//${window.location.hostname}:5000`
    : window.location.origin;
const POLL_INTERVAL = 250; // 默认轮询间隔 (毫秒)

// =========================
// DOM 元素引用 (Element References)
// =========================
const el = {
    // 鼠标/光标跟随效果
    dot: document.getElementById("cursor-dot"),
    outline: document.getElementById("cursor-outline"),

    // 核心显示区域
    video: document.getElementById("video-stream"),
    videoShell: document.querySelector(".video-hud-container"),

    // HUD 数据面板
    fps: document.getElementById("fps-val"),
    delay: document.getElementById("delay-val"),
    infer: document.getElementById("infer-val"),
    count: document.getElementById("count-val"),
    shape: document.getElementById("shape-val"),

    // 目标详细信息 (Video HUD Overlay)
    targetMeta: document.getElementById("target-meta"),

    // 系统控制
    baseUrl: document.getElementById("base-url"),
    applyUrl: document.getElementById("apply-url"),

    // 功能按钮
    toggleBtn: document.getElementById("toggle-btn"),
    refreshBtn: document.getElementById("refresh-btn"),
    pixelBtn: document.getElementById("pixel-btn"),
    fitBtn: document.getElementById("fit-btn"),
    rotateBtn: document.getElementById("rotate-btn"),

    // 警报 Banner
    alertBanner: document.getElementById("alert-banner"),
    alertHeader: document.getElementById("alert-header"),
    alertTitle: document.getElementById("alert-title"),
    alertDesc: document.getElementById("alert-desc"),

    // 状态指示灯
    dotInfer: document.getElementById("dot-infer"),
    dotAudio: document.getElementById("dot-audio"),

    // 语音助手 (Voice Assistant)
    voiceStatusBadge: document.getElementById("voice-status-badge"),
    voiceLogContainer: document.getElementById("voice-log-container"),

    // Footer
    lastUpdate: document.getElementById("last-update"),
};

// =========================
// 全局状态变量
// =========================
let baseUrl = DEFAULT_BASE;
let pollTimer = null;    // 轮询定时器句柄
let lastOk = 0;          // 上次请求成功的时间戳
let pollInterval = POLL_INTERVAL;
let backoffMs = 0;       // 请求失败后的退避时间
let inflight = false;    // 是否有正在进行的请求
let rotateStep = 0;      // 旋转角度 (0, 1=90, 2=180, 3=270)
let isCover = false;     // 是否铺满容器
let isPixel = false;     // 是否开启像素化
let autoRotated = false; // 是否已经自动根据画面比例旋转过
let lastShape = null;    // 上次获取到的画面分辨率
let lastVoiceTs = 0;     // 上次语音日志更新时间戳
let lastVideoBaseUrl = null; // 上次设置的视频流基础URL，用于防止重复刷新

// =========================
// 辅助函数 (Utils)
// =========================

// --- 调试辅助：在 UI 上显示错误 ---
function showDebugError(msg) {
    let debugBox = document.getElementById("debug-error-box");
    if (!debugBox) {
        debugBox = document.createElement("div");
        debugBox.id = "debug-error-box";
        debugBox.style.position = "fixed";
        debugBox.style.top = "10px";
        debugBox.style.right = "10px";
        debugBox.style.backgroundColor = "rgba(255, 0, 0, 0.8)";
        debugBox.style.color = "white";
        debugBox.style.padding = "10px";
        debugBox.style.zIndex = "9999";
        debugBox.style.fontSize = "12px";
        debugBox.style.maxWidth = "300px";
        debugBox.style.borderRadius = "4px";
        document.body.appendChild(debugBox);
    }
    debugBox.textContent = `Error: ${msg}`;
    // 5秒后自动清除
    setTimeout(() => { debugBox.remove(); }, 8000);
}

function setText(node, value) {
    if (!node) return;
    node.textContent = value;
}

function fmtNumber(value, digits = 1) {
    if (typeof value !== "number" || !isFinite(value)) {
        return "--";
    }
    return value.toFixed(digits);
}

/**
 * 更新服务器连接状态 UI
 */
function setServerStatus(ok) {
    // 这里的逻辑现在简化了，主要靠 polling 失败时的退避处理
    // 在 footer 或 indicator 表现
    if (el.dotInfer) {
        if (!ok) el.dotInfer.classList.remove("active");
    }
}

function updateLinks() {
    // 这些链接元素在当前 HTML 中不存在，安全地检查后更新
    if (el.linkHealth) el.linkHealth.href = `${baseUrl}/health`;
    if (el.linkDetect) el.linkDetect.href = `${baseUrl}/detect`;
    if (el.linkVideo) el.linkVideo.href = `${baseUrl}/video`;
}

/**
 * 刷新 MJPEG 视频流 (通过更新 src 时间戳)
 * 增加防抖逻辑：只有当 baseUrl 真正改变时才更新，避免频繁刷新
 * @param {boolean} force - 是否强制刷新，即使 URL 没变
 */
function updateVideo(force = false) {
    if (!el.video) {
        console.error("Video element not found!");
        return;
    }

    // 只有当 baseUrl 改变或强制刷新时才更新视频源
    if (!force && lastVideoBaseUrl === baseUrl && el.video.src) {
        console.log("Video URL unchanged, skipping refresh");
        return;
    }

    lastVideoBaseUrl = baseUrl;
    const videoUrl = `${baseUrl}/video?ts=${Date.now()}`;
    console.log("Setting video src to:", videoUrl);
    el.video.src = videoUrl;
}

// =========================
// UI 更新逻辑 (UI Updates)
// =========================

// 注意：updateAlert 和 updateRisk 函数已移除，因为引用的 HTML 元素已不存在
// 警报状态现在通过 alert-banner 组件在 updateFromDetect 中处理

/**
 * 根据后端返回的分辨率，自动调整容器比例
 * 并在第一次检测到竖屏时自动旋转画面
 */
function updateAspect(shape) {
    if (!shape || !shape.w || !shape.h) return;

    const w = shape.w;
    const h = shape.h;
    const isPortrait = h > w;

    // 自动旋转逻辑：如果是竖屏且未手动调整过
    if (isPortrait && !autoRotated) {
        rotateStep = 1;
        autoRotated = true;
        applyRotate();
        setText(el.rotateBtn, `旋转 ${rotateStep * 90}`);
    }

    // 如果画面被旋转了 90 或 270 度，宽高比需要互换
    const rotated = rotateStep === 1 || rotateStep === 3;
    const ratioW = rotated ? h : w;
    const ratioH = rotated ? w : h;
    el.videoShell.style.aspectRatio = `${ratioW} / ${ratioH}`;
}

/**
 * 更新语音助手 UI
 */
function updateVoiceUI(status, logs) {
    if (!el.voiceStatusBadge || !el.voiceLogContainer) return;

    // 1. Update Status Badge
    const s = (status || "idle").toLowerCase();
    const badge = el.voiceStatusBadge;

    // Reset classes
    badge.className = "px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider transition-colors duration-300";

    if (s === "processing" || s === "listening") {
        badge.classList.add("bg-blue-500/20", "text-blue-400", "animate-pulse");
        badge.textContent = s === "listening" ? "Listening" : "Thinking...";
    } else if (s === "speaking") {
        badge.classList.add("bg-green-500/20", "text-green-400");
        badge.textContent = "Speaking";
    } else {
        badge.classList.add("bg-white/10", "text-white/50");
        badge.textContent = "Idle";
    }

    // 2. Update Logs (Only if new logs exist)
    if (!logs || logs.length === 0) return;

    const latestTs = logs[logs.length - 1].ts;
    if (latestTs > lastVoiceTs) {
        lastVoiceTs = latestTs;

        // Re-render logs
        el.voiceLogContainer.innerHTML = "";
        logs.forEach(log => {
            const item = document.createElement("div");
            item.className = "flex flex-col gap-1 anim-fade-in";

            const isUser = log.role === "user";

            const meta = document.createElement("div");
            meta.className = "flex items-center gap-2 opacity-40 text-[9px] uppercase tracking-wider";
            meta.innerHTML = isUser
                ? `<span class="text-accent">User</span> <span>${new Date(log.ts * 1000).toLocaleTimeString()}</span>`
                : `<span class="text-green-400">AI</span> <span>${new Date(log.ts * 1000).toLocaleTimeString()}</span>`;

            const content = document.createElement("div");
            content.className = isUser ? "text-white/80" : "text-white/60 pl-2 border-l border-white/10";
            content.textContent = log.content;

            item.appendChild(meta);
            item.appendChild(content);
            el.voiceLogContainer.appendChild(item);
        });

        // Auto scroll to bottom
        el.voiceLogContainer.scrollTop = el.voiceLogContainer.scrollHeight;
    }
}

/**
 * 核心：解析 /detect 接口返回的 JSON 数据并刷新所有 UI
 */
function updateFromDetect(data) {
    // 1. 更新基础指标
    setText(el.fps, `${fmtNumber(data.fps_infer)}`);
    setText(el.delay, `${fmtNumber(data.delay_ms, 0)} ms`);
    setText(el.infer, `${fmtNumber(data.infer_ms, 0)} ms`);
    setText(el.count, String(data.count ?? 0));
    setText(el.notify, data.should_notify ? "是" : "否");

    // 2. 更新音频状态
    const audioState = data.last_send_ok ? "成功" : (data.last_send_ts ? "失败" : "待命");
    setText(el.audio, audioState);

    const lastSend = data.last_send_ts ? new Date(data.last_send_ts * 1000) : null;
    setText(el.lastSend, lastSend ? lastSend.toLocaleTimeString() : "--");

    // 3. 更新分辨率与比例
    if (data.shape && data.shape.w && data.shape.h) {
        setText(el.shape, `${data.shape.w}x${data.shape.h}`);
    } else {
        setText(el.shape, "--");
    }
    lastShape = data.shape || null;
    updateAspect(lastShape);

    // 4. 更新状态指示灯
    if (el.dotInfer) el.dotInfer.classList.toggle("active", data.infer_ms > 0);
    if (el.dotAudio) el.dotAudio.classList.toggle("active", data.should_notify);

    // 8. 更新目标详情 (Video Overlay)
    if (data.alert_target) {
        const t = data.alert_target;
        setText(el.targetMeta, `追踪中: ${t.label.toUpperCase()} (等级${t.level})`);
    } else {
        setText(el.targetMeta, "扫描区域中...");
    }

    // 9. 更新 Banner 状态
    if (el.alertBanner) {
        const level = data.alert_level ?? 0;
        const count = data.count ?? 0;
        const label = data.alert_target && data.alert_target.label ? data.alert_target.label : "目标";

        if (level >= 3) {
            el.alertBanner.classList.add("danger");
            el.alertBanner.classList.remove("safe", "warn");
            setText(el.alertHeader, "紧急警报");
            setText(el.alertTitle, "检测到危险");
            setText(el.alertDesc, `请立即停止！前方有 ${label} (共${count}个)。`);
        } else if (level === 2) {
            el.alertBanner.classList.add("warn");
            el.alertBanner.classList.remove("safe", "danger");
            setText(el.alertHeader, "警告");
            setText(el.alertTitle, "请注意");
            setText(el.alertDesc, `前方有障碍物: ${label} (${count}个)，请减速。`);
        } else if (level === 1) {
            el.alertBanner.classList.add("warn");
            el.alertBanner.classList.remove("safe", "danger");
            setText(el.alertHeader, "提示");
            setText(el.alertTitle, "检测到物体");
            setText(el.alertDesc, `视野中检测到 ${label}。`);
        } else {
            el.alertBanner.classList.add("safe");
            el.alertBanner.classList.remove("warn", "danger");
            setText(el.alertHeader, "安全状态");
            setText(el.alertTitle, "未检测到威胁");
            setText(el.alertDesc, "前方畅通，可正常前行。");
        }

        // Update banner time
        const now = new Date();
        const timeEl = document.getElementById("alert-time");
        if (timeEl) timeEl.textContent = now.toLocaleTimeString();
    }

    // 更新时间戳
    const stamp = new Date();
    setText(el.lastUpdate, `最近更新：${stamp.toLocaleTimeString()}`);
    setText(el.railTime, stamp.toLocaleTimeString());

    // 10. 更新语音助手
    updateVoiceUI(data.voice_status, data.voice_log);
}

// =========================
// 轮询机制 (Polling Logic)
// =========================

async function pollDetect() {
    if (inflight) return; // 避免请求堆积
    try {
        inflight = true;
        // 使用 no-store 避免缓存
        const res = await fetch(`${baseUrl}/detect`, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        updateFromDetect(data);

        lastOk = Date.now();
        backoffMs = 0; // 重置退避
        setServerStatus(true);
    } catch (err) {
        console.error("Poll error:", err);
        // 如果连续失败，显示错误到 UI
        if (Date.now() - lastOk > 2000) {
            showDebugError(err.message + " @ " + baseUrl);
        }

        // 如果超过 1.5秒 连接失败，视为离线
        if (Date.now() - lastOk > 1500) {
            setServerStatus(false);
            setText(el.stateStream, "离线");
            setText(el.stateInfer, "等待中");
            setText(el.stateAudio, "待命");
        }
        // 指数退避 (最大4秒)
        backoffMs = Math.min(backoffMs ? backoffMs * 1.6 : 600, 4000);
    } finally {
        inflight = false;
    }
}

function schedulePolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(() => {
        // 页面不可见时停止轮询，省电
        if (document.hidden) return;

        if (backoffMs) {
            // 如果处于退避状态，使用 setTimeout 延迟执行
            setTimeout(pollDetect, backoffMs);
        } else {
            pollDetect();
        }
    }, pollInterval);
}

function startPolling() {
    if (pollTimer) return;
    schedulePolling();
    pollDetect();
    if (el.toggleBtn) setText(el.toggleBtn, "暂停检测");
}

function stopPolling() {
    if (!pollTimer) return;
    clearInterval(pollTimer);
    pollTimer = null;
    if (el.toggleBtn) setText(el.toggleBtn, "恢复检测");
}

function applyBaseUrl() {
    const value = el.baseUrl.value.trim() || DEFAULT_BASE;
    baseUrl = value.replace(/\/+$/, "");
    updateLinks();
    updateVideo(true); // 用户明确更改了地址，强制刷新
    lastOk = 0;
    pollDetect();
    setText(el.statusBase, baseUrl.replace(/^https?:\/\//, ""));
}

function applyRotate() {
    el.video.classList.remove("rot-90", "rot-180", "rot-270");
    if (rotateStep === 1) el.video.classList.add("rot-90");
    else if (rotateStep === 2) el.video.classList.add("rot-180");
    else if (rotateStep === 3) el.video.classList.add("rot-270");
}

// =========================
// 事件监听 (Event Listeners)
// =========================

// 为存在的元素添加事件监听器，在添加前先检查元素是否存在
if (el.toggleBtn) el.toggleBtn.addEventListener("click", () => pollTimer ? stopPolling() : startPolling());
if (el.refreshBtn) el.refreshBtn.addEventListener("click", () => updateVideo(true)); // 强制刷新
// 注意：当前 HTML 中没有 rotateBtn，所以这里用可选链式调用
if (el.rotateBtn) {
    el.rotateBtn.addEventListener("click", () => {
        rotateStep = (rotateStep + 1) % 4;
        applyRotate();
        setText(el.rotateBtn, `旋转 ${rotateStep * 90}`);
        updateAspect(lastShape);
    });
}
if (el.pixelBtn) {
    el.pixelBtn.addEventListener("click", () => {
        isPixel = !isPixel;
        el.video.classList.toggle("pixel", isPixel);
        setText(el.pixelBtn, `锐化：${isPixel ? "开" : "关"}`);
    });
}
if (el.fitBtn) {
    el.fitBtn.addEventListener("click", () => {
        isCover = !isCover;
        el.videoShell.classList.toggle("fit-cover", isCover);
        setText(el.fitBtn, `适配：${isCover ? "铺满" : "留白"}`);
    });
}
if (el.applyUrl) el.applyUrl.addEventListener("click", applyBaseUrl);
if (el.baseUrl) el.baseUrl.addEventListener("keydown", (e) => { if (e.key === "Enter") applyBaseUrl(); });

// =========================
// 初始化与生命周期 (Init)
// =========================

// 自动纠正默认地址逻辑
// 如果输入框值包含 127.0.0.1 且当前不是 127.0.0.1 (IP访问)，或者处于 Live Server 模式
if (el.baseUrl && ((el.baseUrl.value.includes("127.0.0.1") && !window.location.hostname.includes("127.0.0.1")) || isLiveServer)) {
    el.baseUrl.value = DEFAULT_BASE;
    baseUrl = DEFAULT_BASE;
    console.log("Auto-corrected baseUrl to:", baseUrl);
} else if (el.baseUrl) {
    // 读取输入框的值，但不调用 applyBaseUrl() 避免重复初始化
    const value = el.baseUrl.value.trim() || DEFAULT_BASE;
    baseUrl = value.replace(/\/+$/, "");
}

// 初始化：只在启动时设置一次视频流
updateLinks();
updateVideo(); // 这里会设置 lastVideoBaseUrl，后续不会重复刷新
startPolling();
applyRotate();
if (el.statusBase) setText(el.statusBase, baseUrl.replace(/^https?:\/\//, ""));

// 页面可见性改变时调整轮询策略
document.addEventListener("visibilitychange", () => {
    pollInterval = document.hidden ? 1200 : POLL_INTERVAL; // 后台时降低频率
    if (pollTimer) schedulePolling();
});

// =========================
// GSAP 动画与特效
// =========================
if (window.gsap) {
    let mouseX = 0, mouseY = 0;
    let outlineX = 0, outlineY = 0;

    // 自定义光标跟随
    document.addEventListener("mousemove", (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
        gsap.set(el.dot, { x: mouseX - 4, y: mouseY - 4 });
    });

    function updateOutline() {
        outlineX += (mouseX - outlineX) * 0.35;
        outlineY += (mouseY - outlineY) * 0.35;
        gsap.set(el.outline, { x: outlineX - 20, y: outlineY - 20 });
        requestAnimationFrame(updateOutline);
    }
    updateOutline();

    // 入场动画 Timeline (Updated for snappier feel)
    const tl = gsap.timeline({ defaults: { ease: "power3.out", duration: 1.0 } });
    tl.from(".reveal-item", { y: 40, opacity: 0, stagger: 0.05 })
        .from(".nav-item", { y: -20, opacity: 0, duration: 0.8 }, "-=0.8")
        .set(".reveal-item", { clearProps: "transform" });

    // 磁性按钮效果
    const interactives = document.querySelectorAll(".nav-link, .magnetic-btn, .magnetic-item");
    interactives.forEach(item => {
        item.addEventListener("mouseenter", () => gsap.to(el.outline, { scale: 1.5, background: "rgba(255,255,255,0.1)", borderColor: "transparent", duration: 0.2 }));
        item.addEventListener("mouseleave", () => gsap.to(el.outline, { scale: 1, background: "transparent", borderColor: "rgba(255,255,255,0.5)", duration: 0.2 }));
    });

    document.querySelectorAll(".magnetic-btn").forEach(btn => {
        btn.addEventListener("mousemove", (e) => {
            const rect = btn.getBoundingClientRect();
            const x = (e.clientX - rect.left - rect.width / 2) * 0.4;
            const y = (e.clientY - rect.top - rect.height / 2) * 0.4;
            gsap.to(btn, { x, y, duration: 0.3 });
        });
        btn.addEventListener("mouseleave", () => gsap.to(btn, { x: 0, y: 0, duration: 0.5, ease: "elastic.out(1, 0.3)" }));
    });
}

// =========================
// 背景动态粒子 (Canvas Blobs)
// =========================
// 只有在 canvas-bg 元素存在时才初始化粒子特效
const canvas = document.getElementById("canvas-bg");
if (canvas) {
    const ctx = canvas.getContext("2d");
    let w, h;

    function resize() {
        w = canvas.width = window.innerWidth;
        h = canvas.height = window.innerHeight;
    }
    window.addEventListener("resize", resize);
    resize();

    class Blob {
        constructor() {
            this.x = Math.random() * w;
            this.y = Math.random() * h;
            this.r = Math.random() * 300 + 200;
            this.vx = (Math.random() - 0.5) * 0.2;
            this.vy = (Math.random() - 0.5) * 0.2;
            // 极度弱化背景：降低亮度和透明度
            this.color = `hsla(${Math.random() * 60 + 180}, 60%, 20%, 0.03)`;
        }
        update() {
            this.x += this.vx; this.y += this.vy;
            if (this.x < -this.r || this.x > w + this.r) this.vx *= -1;
            if (this.y < -this.r || this.y > h + this.r) this.vy *= -1;
            const grad = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, this.r);
            grad.addColorStop(0, this.color); grad.addColorStop(1, "transparent");
            ctx.fillStyle = grad; ctx.beginPath(); ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2); ctx.fill();
        }
    }

    const blobs = Array.from({ length: 3 }, () => new Blob());

    function render() {
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, w, h);
        ctx.globalCompositeOperation = "screen";
        blobs.forEach(b => b.update());
        requestAnimationFrame(render);
    }
    render();
}
