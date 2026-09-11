const body = document.body;

const servicesList = document.getElementById("servicesList");
const serviceSearch = document.getElementById("serviceSearch");
const globalSearch = document.getElementById("globalSearch");
const emptyView = document.getElementById("emptyView");

const aiPanel = document.getElementById("aiPanel");
const aiInput = document.getElementById("aiInput");
const sendAi = document.getElementById("sendAi");
const chatMessages = document.getElementById("chatMessages");

const themeButton = document.getElementById("themeButton");
const closeAi = document.getElementById("closeAi");
const aiNav = document.getElementById("aiNav");
const aiCardButton = document.getElementById("aiCardButton");
const clearChat = document.getElementById("clearChat");

const categoryFilter = document.getElementById("categoryFilter");
const statusFilter = document.getElementById("statusFilter");
const resetFilters = document.getElementById("resetFilters");

const serviceModal = document.getElementById("serviceModal");
const serviceModalBackdrop = document.getElementById("serviceModalBackdrop");
const serviceModalClose = document.getElementById("serviceModalClose");
const serviceModalTitle = document.getElementById("serviceModalTitle");
const serviceModalContent = document.getElementById("serviceModalContent");

let servicesRequestId = 0;
let selectedCategory = "";
let selectedStatus = "";
let searchTimer = null;

const CHAT_STORAGE_KEY = "mfc-chat-history-v2";
const UI_STORAGE_KEY = "mfc-ui-state-v2";
const MAX_SAVED_MESSAGES = 60;

function saveChat() {
    const messages = [...chatMessages.querySelectorAll(".message")].map((item) => ({
        type: item.classList.contains("user") ? "user" : "assistant",
        text: item.querySelector(".message-bubble")?.textContent || "",
    })).filter((item) => item.text);

    localStorage.setItem(
        CHAT_STORAGE_KEY,
        JSON.stringify(messages.slice(-MAX_SAVED_MESSAGES))
    );
}

function restoreChat() {
    try {
        const raw = localStorage.getItem(CHAT_STORAGE_KEY);
        if (!raw) return;

        const messages = JSON.parse(raw);
        if (!Array.isArray(messages)) return;

        messages.forEach((message) => {
            if (!message || !message.text) return;
            addMessage(message.type === "user" ? "user" : "assistant", message.text);
        });
    } catch (error) {
        console.warn("Не удалось восстановить историю чата:", error);
    }
}

function saveUiState() {
    localStorage.setItem(
        UI_STORAGE_KEY,
        JSON.stringify({
            theme: body.classList.contains("light-theme") ? "light" : "dark",
            category: selectedCategory,
            status: selectedStatus,
            search: serviceSearch.value,
        })
    );
}

function restoreUiState() {
    try {
        const raw = localStorage.getItem(UI_STORAGE_KEY);
        if (!raw) return;

        const state = JSON.parse(raw);
        if (!state || typeof state !== "object") return;

        if (state.theme === "light" || state.theme === "dark") {
            setTheme(state.theme);
        }

        if (typeof state.category === "string") {
            selectedCategory = state.category;
            categoryFilter.value = state.category;
        }

        if (typeof state.status === "string") {
            selectedStatus = state.status;
            statusFilter.value = state.status;
        }

        if (typeof state.search === "string") {
            serviceSearch.value = state.search;
        }
    } catch (error) {
        console.warn("Не удалось восстановить настройки интерфейса:", error);
    }
}


function openAi() {
    aiPanel.classList.add("open");
    setTimeout(() => aiInput.focus(), 150);
}

function closeAiPanel() {
    aiPanel.classList.remove("open");
}

aiNav.addEventListener("click", (event) => {
    event.preventDefault();
    openAi();
});

aiCardButton.addEventListener("click", openAi);

clearChat.addEventListener("click", () => {
    chatMessages.innerHTML = "";
    localStorage.removeItem(CHAT_STORAGE_KEY);
});
closeAi.addEventListener("click", closeAiPanel);

function setTheme(theme) {
    body.classList.toggle("light-theme", theme === "light");
    localStorage.setItem("mfc-theme", theme);
}

setTheme(localStorage.getItem("mfc-theme") || "dark");

themeButton.addEventListener("click", () => {
    const nextTheme = body.classList.contains("light-theme") ? "dark" : "light";
    setTheme(nextTheme);
    saveUiState();
});

function shorten(value, maxLength = 220) {
    const text = value == null ? "" : String(value).replace(/\s+/g, " ").trim();
    if (!text) return "Описание услуги отсутствует в базе МФЦ.";
    return text.length > maxLength ? text.slice(0, maxLength - 1) + "…" : text;
}

function renderServices(services) {
    servicesList.innerHTML = "";

    if (!services.length) {
        const noResults = document.createElement("div");
        noResults.className = "no-results";
        noResults.textContent = "Услуги по вашему запросу не найдены.";
        servicesList.appendChild(noResults);
        return;
    }

    services.forEach((service) => {
        const card = document.createElement("article");
        card.className = "service-card";

        card.innerHTML = `
            <div class="service-icon">
                <svg viewBox="0 0 24 24">
                    <path d="M5 3h11l3 3v15H5z"></path>
                    <path d="M14 3v4h5"></path>
                    <path d="M8 12h8"></path>
                    <path d="M8 16h6"></path>
                </svg>
            </div>
            <div class="service-info">
                <h3></h3>
                <p></p>
                <span>Государственная услуга</span>
            </div>
            <button class="open-service" type="button">Открыть</button>
            <button class="service-arrow ai-service-button" type="button" aria-label="Спросить ИИ об услуге" title="Спросить ИИ">›</button>
        `;

        card.querySelector("h3").textContent = service.name || "Без названия";
        // В карточке показывается именно description_text из PostgreSQL, без участия ИИ.
        card.querySelector("p").textContent = shorten(service.description);
        card.querySelector(".open-service").addEventListener("click", () => openService(service.id));
        card.querySelector(".ai-service-button").addEventListener("click", () => askAiForService(service.id, service.name));
        servicesList.appendChild(card);
    });
}

async function loadServices(query = "") {
    const requestId = ++servicesRequestId;
    servicesList.innerHTML = '<div class="loading">Загрузка услуг...</div>';

    try {
        const params = new URLSearchParams({q: query, limit: "100"});
        if (selectedCategory) params.set("category", selectedCategory);
        if (selectedStatus) params.set("status", selectedStatus);

        const response = await fetch("/api/services?" + params.toString());
        if (!response.ok) throw new Error("HTTP " + response.status);
        const services = await response.json();
        if (requestId !== servicesRequestId) return;
        renderServices(Array.isArray(services) ? services : []);
    } catch (error) {
        console.error("Ошибка загрузки услуг:", error);
        servicesList.innerHTML = "";
        const node = document.createElement("div");
        node.className = "load-error";
        node.textContent = "Не удалось загрузить услуги из PostgreSQL.";
        servicesList.appendChild(node);
    }
}

function openServiceSearch(query) {
    serviceSearch.value = query;
    loadServices(query);
    window.scrollTo({top: 0, behavior: "smooth"});
}

function closeServiceModal() {
    serviceModal.hidden = true;
    body.classList.remove("modal-open");
}

function addDetailSection(title, value) {
    if (!value) return;
    const section = document.createElement("section");
    section.className = "service-detail-section";

    const heading = document.createElement("h3");
    heading.textContent = title;
    const text = document.createElement("p");
    text.textContent = value;

    section.append(heading, text);
    serviceModalContent.appendChild(section);
}

async function openService(serviceId) {
    if (!serviceId) return;

    serviceModal.hidden = false;
    body.classList.add("modal-open");
    serviceModalTitle.textContent = "Загрузка...";
    serviceModalContent.innerHTML = '<div class="loading">Получаю данные из PostgreSQL...</div>';

    try {
        const response = await fetch("/api/services/" + encodeURIComponent(serviceId));
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Не удалось загрузить услугу");

        serviceModalTitle.textContent = data.name || "Услуга";
        serviceModalContent.innerHTML = "";
        addDetailSection("Описание", data.description || "Описание в базе не указано.");
        addDetailSection("Получатели", data.recipients);
        addDetailSection("Документы", data.documents);
        addDetailSection("Оплата", data.payment);
        addDetailSection("Срок", data.time);
        addDetailSection("Результат", data.result);
        addDetailSection("Основания отказа", data.reject_reasons);
    } catch (error) {
        console.error("Ошибка карточки услуги:", error);
        serviceModalTitle.textContent = "Ошибка";
        serviceModalContent.innerHTML = "";
        const text = document.createElement("p");
        text.textContent = error.message;
        serviceModalContent.appendChild(text);
    }
}

serviceModalBackdrop.addEventListener("click", closeServiceModal);
serviceModalClose.addEventListener("click", closeServiceModal);
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !serviceModal.hidden) closeServiceModal();
});

resetFilters.addEventListener("click", () => {
    selectedCategory = "";
    selectedStatus = "";
    categoryFilter.value = "";
    statusFilter.value = "";
    serviceSearch.value = "";
    saveUiState();
    loadServices("");
});

categoryFilter.addEventListener("change", () => {
    selectedCategory = categoryFilter.value;
    saveUiState();
    loadServices(serviceSearch.value.trim());
});

statusFilter.addEventListener("change", () => {
    selectedStatus = statusFilter.value;
    saveUiState();
    loadServices(serviceSearch.value.trim());
});

serviceSearch.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadServices(serviceSearch.value.trim()), 250);
});

globalSearch.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        const value = globalSearch.value.trim();
        if (value) openServiceSearch(value);
    }
});

function addMessage(type, text, sources = []) {
    const item = document.createElement("div");
    item.className = "message " + type;

    const label = document.createElement("span");
    label.className = "message-label";
    label.textContent = type === "user" ? "Вы" : "ИИ-помощник";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent = text;

    item.append(label, bubble);

    if (type === "assistant" && Array.isArray(sources) && sources.length) {
        const sourceBox = document.createElement("div");
        sourceBox.className = "message-sources";

        const sourceLabel = document.createElement("span");
        sourceLabel.textContent = "Данные из БД:";
        sourceBox.appendChild(sourceLabel);

        sources.slice(0, 3).forEach((source) => {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = source.name || "Услуга";
            button.addEventListener("click", () => openService(source.id));
            sourceBox.appendChild(button);
        });

        item.appendChild(sourceBox);
    }

    chatMessages.appendChild(item);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addTyping() {
    const item = document.createElement("div");
    item.className = "message assistant";
    item.id = "typingMessage";
    item.innerHTML = '<span class="message-label">ИИ-помощник</span><div class="message-bubble typing">Формирую ответ...</div>';
    chatMessages.appendChild(item);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTyping() {
    document.getElementById("typingMessage")?.remove();
}


async function askAiForService(serviceId, serviceName) {
    if (!serviceId || sendAi.disabled) return;

    openAi();

    const question = `Объясни простыми словами услугу: ${serviceName || ""}`.trim();
    addMessage("user", question);
    sendAi.disabled = true;
    addTyping();

    try {
        const response = await fetch(
            "/api/chat/service/" + encodeURIComponent(serviceId),
            {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({message: question})
            }
        );

        const data = await response.json();
        removeTyping();

        if (!response.ok) {
            throw new Error(data.error || "Ошибка сервера");
        }

        addMessage("assistant", data.answer || "Ответ не получен.");
        saveChat();
    } catch (error) {
        console.error("Ошибка ИИ услуги:", error);
        removeTyping();
        addMessage("assistant", "Не удалось получить ответ: " + error.message);
        saveChat();
        saveChat();
    } finally {
        sendAi.disabled = false;
        aiInput.focus();
    }
}

async function sendMessage() {
    const text = aiInput.value.trim();
    if (!text || sendAi.disabled) return;

    addMessage("user", text);
    aiInput.value = "";
    sendAi.disabled = true;
    addTyping();

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({message: text}),
        });
        const data = await response.json();
        removeTyping();
        if (!response.ok) throw new Error(data.error || "Ошибка сервера");
        addMessage("assistant", data.answer || "Ответ не получен.", data.matched || []);
        saveChat();
    } catch (error) {
        console.error("Ошибка ИИ:", error);
        removeTyping();
        addMessage("assistant", "Не удалось получить ответ: " + error.message);
    } finally {
        sendAi.disabled = false;
        aiInput.focus();
    }
}

sendAi.addEventListener("click", sendMessage);
aiInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

document.querySelectorAll(".ai-suggestions button").forEach((button) => {
    button.addEventListener("click", async () => {
        aiInput.value = button.dataset.question || button.textContent.trim();
        await sendMessage();
    });
});

document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", (event) => {
        const view = item.dataset.view;
        if (view === "ai") return;

        event.preventDefault();
        document.querySelectorAll(".nav-item").forEach((nav) => nav.classList.remove("active"));
        item.classList.add("active");

        if (view === "services") {
            emptyView.hidden = true;
            servicesList.hidden = false;
            loadServices(serviceSearch.value.trim());
            return;
        }

        if (view === "home") {
            emptyView.hidden = true;
            servicesList.hidden = false;
            serviceSearch.value = "";
            restoreUiState();
restoreChat();
loadServices(serviceSearch.value.trim());
            return;
        }

        emptyView.hidden = false;
        servicesList.hidden = true;
    });
});

loadServices();
