// DM chat client.  Connects to Socket.IO, joins the deterministic room for
// the other user, loads history, and posts/subscribes to messages.

(function () {
    "use strict";

    const body = document.body;
    const otherId = parseInt(body.dataset.otherId || "0", 10);
    if (!otherId) {
        return;
    }

    const win = document.getElementById("chat-window");
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-input");
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

    function formatTime(iso) {
        if (!iso) return "";
        const d = new Date(iso);
        if (isNaN(d.getTime())) return "";
        return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    async function loadHistory() {
        try {
            const res = await fetch(
                "/api/dm/" + otherId + "/history?limit=50",
                { credentials: "same-origin" }
            );
            if (!res.ok) return;
            const data = await res.json();
            (data.messages || []).forEach(renderMessage);
            scrollToBottom(true);
        } catch (e) {
            console.error("history load failed", e);
        }
    }

    // Connect to Socket.IO.
    const socket = io({ withCredentials: true });

    socket.on("connect", function () {
        // Server emits dm:typing_broadcast to ``user:<other_id>`` (server side
        // join_room).  We can't reach that room from the client, so the
        // server instead emits on the dm: room itself.  We join our own
        // personal room for parity with the group-room typing flow.
        socket.emit("dm:join", { other_id: otherId });
        loadHistory();
    });

    socket.on("dm:message", function (msg) {
        renderMessage(msg);
        scrollToBottom(false);
    });

    socket.on("dm:typing_broadcast", function (data) {
        if (!typingEl) return;
        if (data && data.from_id && data.from_id !== myId && data.typing) {
            typingEl.textContent = (data.from_username || "User") + " is typing…";
        } else if (data && data.from_id === myId) {
            // our own typing echo — ignore
        } else {
            typingEl.textContent = "";
        }
    });

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        const bodyText = input.value.trim();
        if (!bodyText) return;
        socket.emit("dm:send", { other_id: otherId, body: bodyText });
        input.value = "";
        // Typing: false
        socket.emit("dm:typing", { other_id: otherId, typing: false });
    });

    // Throttled typing indicator.
    let lastTypingEmit = 0;
    let typingDebounce = null;
    input.addEventListener("input", function () {
        const now = Date.now();
        if (now - lastTypingEmit > 2000) {
            socket.emit("dm:typing", { other_id: otherId, typing: true });
            lastTypingEmit = now;
        }
        clearTimeout(typingDebounce);
        typingDebounce = setTimeout(function () {
            socket.emit("dm:typing", { other_id: otherId, typing: false });
        }, 1500);
    });
})();
