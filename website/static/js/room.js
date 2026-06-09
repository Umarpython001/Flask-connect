// Group room chat client.  Mirror of dm.js with room-shaped events.

(function () {
    "use strict";

    const body = document.body;
    const roomId = parseInt(body.dataset.roomId || "0", 10);
    if (!roomId) {
        return;
    }

    const win = document.getElementById("chat-window");
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-input");
    const membersList = document.getElementById("members-list");
    const typingEl = document.getElementById("typing-indicator");
    if (!win || !form || !input) {
        return;
    }
    const myId = parseInt(body.dataset.myId || "0", 10);

    function scrollToBottom(force) {
        const nearBottom =
            win.scrollHeight - win.scrollTop - win.clientHeight < 120;
        if (force || nearBottom) {
            win.scrollTop = win.scrollHeight;
        }
    }

    function formatTime(iso) {
        if (!iso) return "";
        const d = new Date(iso);
        if (isNaN(d.getTime())) return "";
        return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    function renderMessage(msg) {
        const mine = msg.sender_id === myId;
        const div = document.createElement("div");
        div.className = "chat-bubble " + (mine ? "mine" : "theirs");
        const body = document.createElement("div");
        body.className = "body";
        body.textContent = msg.body;
        div.appendChild(body);
        if (!mine) {
            const author = document.createElement("div");
            author.className = "meta";
            author.textContent = msg.sender_username || "";
            div.appendChild(author);
        }
        const ts = document.createElement("div");
        ts.className = "meta";
        ts.textContent = formatTime(msg.created_at);
        div.appendChild(ts);
        win.appendChild(div);
    }

    function renderMembers(members) {
        if (!membersList) return;
        membersList.innerHTML = "";
        members.forEach(function (m) {
            const li = document.createElement("li");
            li.className = "list-group-item d-flex align-items-center gap-2";
            const img = document.createElement("img");
            img.className = "avatar avatar-sm";
            img.src = "/static/" + (m.profile_pic || "uploads/images/default_avatar.svg");
            img.alt = "";
            const span = document.createElement("span");
            span.textContent = m.username;
            if (m.id === myId) {
                const you = document.createElement("small");
                you.className = "text-muted ms-auto";
                you.textContent = " (you)";
                span.appendChild(you);
            }
            li.appendChild(img);
            li.appendChild(span);
            membersList.appendChild(li);
        });
    }

    async function loadHistory() {
        try {
            const res = await fetch(
                "/api/room/" + roomId + "/history?limit=50",
                { credentials: "same-origin" }
            );
            if (!res.ok) return;
            const data = await res.json();
            (data.messages || []).forEach(renderMessage);
            scrollToBottom(true);
        } catch (e) {
            console.error("room history load failed", e);
        }
    }

    const socket = io({ withCredentials: true });

    socket.on("connect", function () {
        socket.emit("room:join", { room_id: roomId });
        loadHistory();
    });

    socket.on("room:message", function (msg) {
        renderMessage(msg);
        scrollToBottom(false);
    });

    socket.on("room:joined", function (data) {
        if (data && Array.isArray(data.members)) {
            renderMembers(data.members);
        }
    });

    socket.on("room:user_joined", function (data) {
        if (!data || !data.user) return;
        // Re-fetch the member list to be authoritative.
        // Cheap and avoids drift between client/server state.
        fetch("/api/room/" + roomId + "/members-list", { credentials: "same-origin" })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (j) { if (j && j.members) renderMembers(j.members); })
            .catch(function () {});
    });

    socket.on("room:user_left", function (data) {
        if (!data) return;
        fetch("/api/room/" + roomId + "/members-list", { credentials: "same-origin" })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (j) { if (j && j.members) renderMembers(j.members); })
            .catch(function () {});
    });

    socket.on("room:typing_broadcast", function (data) {
        if (!typingEl) return;
        if (data && data.typing && data.from_id && data.from_id !== myId) {
            typingEl.textContent = (data.from_username || "Someone") + " is typing…";
        } else {
            typingEl.textContent = "";
        }
    });

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        const bodyText = input.value.trim();
        if (!bodyText) return;
        socket.emit("room:send", { room_id: roomId, body: bodyText });
        input.value = "";
        socket.emit("room:typing", { room_id: roomId, typing: false });
    });

    let lastTypingEmit = 0;
    let typingDebounce = null;
    input.addEventListener("input", function () {
        const now = Date.now();
        if (now - lastTypingEmit > 2000) {
            socket.emit("room:typing", { room_id: roomId, typing: true });
            lastTypingEmit = now;
        }
        clearTimeout(typingDebounce);
        typingDebounce = setTimeout(function () {
            socket.emit("room:typing", { room_id: roomId, typing: false });
        }, 1500);
    });
})();
