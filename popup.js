const indexBtn = document.getElementById("indexBtn");
const askBtn = document.getElementById("askBtn");
const summaryBtn = document.getElementById("summaryBtn");
const clearBtn = document.getElementById("clearBtn");
const questionInput = document.getElementById("question");
const statusDiv = document.getElementById("status");
const videoStatusDiv = document.getElementById("videoStatus");
const chatBox = document.getElementById("chatBox");

function extractVideoId(url) {
  try {
    const parsed = new URL(url);

    if (parsed.hostname === "youtu.be") {
      return parsed.pathname.slice(1);
    }

    if (parsed.pathname === "/watch") {
      return parsed.searchParams.get("v");
    }

    if (parsed.pathname.startsWith("/shorts/")) {
      return parsed.pathname.split("/shorts/")[1].split("/")[0];
    }

    return parsed.searchParams.get("v");
  } catch {
    return null;
  }
}

function timestampToSeconds(ts) {
  const parts = ts.split(":").map(Number);

  if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  }
  if (parts.length === 2) {
    return parts[0] * 60 + parts[1];
  }
  return 0;
}

async function getCurrentTabInfo() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab || !tab.url) {
    throw new Error("No active tab found.");
  }

  const videoId = extractVideoId(tab.url);
  if (!videoId) {
    throw new Error("Open a YouTube video page first.");
  }

  let cleanTitle = tab.title || "Untitled Video";
  cleanTitle = cleanTitle.replace(" - YouTube", "").trim();

  return {
    videoId,
    title: cleanTitle
  };
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || data.error || "Request failed.");
  }

  return data;
}

function addMessage(text, sender) {
  const div = document.createElement("div");
  div.className = sender === "user" ? "user-message" : "bot-message";

  const formatted = text.replace(/\[(\d{1,2}:\d{2}(:\d{2})?)\]/g, (match, ts) => {
    const seconds = timestampToSeconds(ts);
    return `<span class="timestamp" data-time="${seconds}">[${ts}]</span>`;
  });

  div.innerHTML = formatted;

  div.querySelectorAll(".timestamp").forEach(el => {
    el.addEventListener("click", async () => {
      const seconds = el.getAttribute("data-time");
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      const url = new URL(tab.url);
      url.searchParams.set("t", seconds + "s");

      chrome.tabs.update(tab.id, { url: url.toString() });
    });
  });

  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function setStatus(message) {
  statusDiv.textContent = message;
}

indexBtn.addEventListener("click", async () => {
  setStatus("");
  try {
    const { videoId, title } = await getCurrentTabInfo();
    videoStatusDiv.textContent = `⏳ Loading: ${title}`;

    const data = await postJson("http://localhost:8000/index_video", {
      video_id: videoId
    });

    videoStatusDiv.textContent = `✅ ${title}`;
    setStatus(data.message || "Video loaded successfully.");
  } catch (err) {
    videoStatusDiv.textContent = err.message;
  }
});

askBtn.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  if (!question) {
    setStatus("Type a question first.");
    return;
  }

  addMessage(question, "user");
  questionInput.value = "";
  setStatus("⏳ Generating answer...");

  try {
    const { videoId } = await getCurrentTabInfo();

    const data = await postJson("http://localhost:8000/ask", {
      video_id: videoId,
      question: question
    });

    addMessage(data.answer || "No answer returned.", "bot");
    setStatus("✅ Done.");
  } catch (err) {
    addMessage(err.message, "bot");
    setStatus("❌ Error.");
  }
});

summaryBtn.addEventListener("click", async () => {
  setStatus("⏳ Generating summary...");

  try {
    const { videoId } = await getCurrentTabInfo();
    addMessage("Give me a quick summary of this video.", "user");

    const data = await postJson("http://localhost:8000/ask", {
      video_id: videoId,
      question: "Can you summarize this video clearly with key points and mention relevant timestamps if possible?"
    });

    addMessage(data.answer || "No summary returned.", "bot");
    setStatus("✅ Done.");
  } catch (err) {
    addMessage(err.message, "bot");
    setStatus("❌ Error.");
  }
});

clearBtn.addEventListener("click", () => {
  chatBox.innerHTML = `
    <div class="bot-message">
      🚀 Chat with any YouTube video

      1. Click "Load Current Video"
      2. Ask any question
      3. Get answers from the transcript
    </div>
  `;
  setStatus("");
});