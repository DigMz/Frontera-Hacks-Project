const STORAGE_KEY = "breather.todos.v1";

function clampNumber(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function isValidHttpUrl(value) {
  if (!value) return false;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function safeText(value) {
  return String(value ?? "");
}

function uid() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function loadTodos() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item) => item && typeof item === "object")
      .map((item) => ({
        id: safeText(item.id) || uid(),
        text: safeText(item.text).slice(0, 140),
        completed: Boolean(item.completed),
      }))
      .filter((item) => item.text.trim().length > 0);
  } catch {
    return [];
  }
}

function saveTodos(todos) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(todos));
}

function qs(sel) {
  const el = document.querySelector(sel);
  if (!el) throw new Error(`Missing element: ${sel}`);
  return el;
}

const durationSelect = qs("#durationSelect");
const customUrl = qs("#customUrl");
const gateStatus = qs("#gateStatus");
const gateModal = qs("#gateModal");
const countdownEl = qs("#countdown");
const ring = qs("#ring");
const openLink = qs("#openLink");
const cancelGate = qs("#cancelGate");
const closeModal = qs("#closeModal");

const todoForm = qs("#todoForm");
const todoInput = qs("#todoInput");
const todoList = qs("#todoList");
const clearCompleted = qs("#clearCompleted");
const clearAll = qs("#clearAll");

let todos = loadTodos();

function renderTodos() {
  todoList.innerHTML = "";

  for (const todo of todos) {
    const li = document.createElement("li");
    li.className = `todoItem${todo.completed ? " completed" : ""}`;

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = todo.completed;
    checkbox.ariaLabel = "Mark complete";

    const label = document.createElement("label");
    label.textContent = todo.text;

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "smallBtn";
    removeBtn.textContent = "Remove";

    checkbox.addEventListener("change", () => {
      todos = todos.map((t) => (t.id === todo.id ? { ...t, completed: checkbox.checked } : t));
      saveTodos(todos);
      renderTodos();
    });

    removeBtn.addEventListener("click", () => {
      todos = todos.filter((t) => t.id !== todo.id);
      saveTodos(todos);
      renderTodos();
    });

    li.appendChild(checkbox);
    li.appendChild(label);
    li.appendChild(removeBtn);
    todoList.appendChild(li);
  }
}

todoForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = todoInput.value.trim();
  if (!text) return;

  todos = [{ id: uid(), text: text.slice(0, 140), completed: false }, ...todos];
  saveTodos(todos);
  todoInput.value = "";
  renderTodos();
});

clearCompleted.addEventListener("click", () => {
  todos = todos.filter((t) => !t.completed);
  saveTodos(todos);
  renderTodos();
});

clearAll.addEventListener("click", () => {
  todos = [];
  saveTodos(todos);
  renderTodos();
});

renderTodos();

let gateTimerId = null;
let ringTimerId = null;
let targetUrl = null;
let remainingSeconds = 0;

function setGateStatus(text) {
  gateStatus.textContent = text;
}

function stopGateTimers() {
  if (gateTimerId) {
    clearInterval(gateTimerId);
    gateTimerId = null;
  }
  if (ringTimerId) {
    clearInterval(ringTimerId);
    ringTimerId = null;
  }
}

function setOpenEnabled(enabled) {
  openLink.classList.toggle("disabled", !enabled);
  openLink.setAttribute("aria-disabled", enabled ? "false" : "true");
}

function startBreathingRing(totalSeconds) {
  const periodMs = 4000;
  const start = performance.now();

  ringTimerId = setInterval(() => {
    const elapsed = performance.now() - start;
    const phase = (elapsed % periodMs) / periodMs;
    const scale = 0.86 + Math.sin(phase * Math.PI * 2 - Math.PI / 2) * 0.08;
    ring.style.transform = `scale(${scale.toFixed(3)})`;

    const t = clampNumber(elapsed / (totalSeconds * 1000), 0, 1);
    const opacity = 0.95 - t * 0.25;
    ring.style.opacity = String(opacity);
  }, 30);
}

function openGateModal(url, seconds) {
  targetUrl = url;
  remainingSeconds = seconds;

  openLink.href = url;
  setOpenEnabled(false);
  countdownEl.textContent = String(remainingSeconds);

  stopGateTimers();
  ring.style.transform = "scale(0.92)";
  ring.style.opacity = "0.95";

  setGateStatus(`Breathing break started: ${seconds}s`);

  if (typeof gateModal.showModal === "function") {
    gateModal.showModal();
  } else {
    gateModal.setAttribute("open", "");
  }

  startBreathingRing(seconds);

  gateTimerId = setInterval(() => {
    remainingSeconds -= 1;
    countdownEl.textContent = String(Math.max(0, remainingSeconds));

    if (remainingSeconds <= 0) {
      stopGateTimers();
      setOpenEnabled(true);
      setGateStatus("Timer finished. You can open the app.");
    }
  }, 1000);
}

function closeGateModal() {
  stopGateTimers();
  setOpenEnabled(false);
  targetUrl = null;
  setGateStatus("Ready.");

  if (typeof gateModal.close === "function") {
    gateModal.close();
  } else {
    gateModal.removeAttribute("open");
  }
}

function getSelectedDurationSeconds() {
  const seconds = Number(durationSelect.value);
  if (!Number.isFinite(seconds)) return 10;
  return clampNumber(seconds, 3, 120);
}

function resolveUrlFromButton(buttonUrl) {
  const custom = customUrl.value.trim();
  if (isValidHttpUrl(custom)) return custom;
  if (custom.length > 0) return null;
  return buttonUrl;
}

for (const btn of document.querySelectorAll(".appButton")) {
  btn.addEventListener("click", () => {
    const buttonUrl = btn.getAttribute("data-url");
    const resolved = resolveUrlFromButton(buttonUrl);

    if (!resolved) {
      setGateStatus("Custom link is not a valid http(s) URL.");
      customUrl.focus();
      return;
    }

    const durationSeconds = getSelectedDurationSeconds();
    openGateModal(resolved, durationSeconds);
  });
}

cancelGate.addEventListener("click", closeGateModal);
closeModal.addEventListener("click", closeGateModal);

gateModal.addEventListener("cancel", (e) => {
  e.preventDefault();
  closeGateModal();
});

openLink.addEventListener("click", () => {
  if (openLink.classList.contains("disabled")) return;
  stopGateTimers();
  setGateStatus("Opened. Come back anytime.");

  setTimeout(() => {
    closeGateModal();
  }, 250);
});
