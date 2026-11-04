/*************************
    Internet Functions
**************************/

let currentWebsiteHTML = "";
let currentWebsiteType = "";
let currentInternetDifficulty = "";
let websiteLoadTime = null;
let currentInternetSpeechText = "";
let currentInternetQuery = "security alerts";
let cachedDesktopResults = [];
let internetFreePractice = false;
const desktopInternetLabels = globalThis.desktopLabels || {};

const internetContent = document.getElementById("internetContent");
const internetButtons = document.getElementById("internetButtons");
const internetRealBtn = document.getElementById("internetRealBtn");
const internetFakeBtn = document.getElementById("internetFakeBtn");
const internetReadAloudBtn = document.getElementById("internetReadAloudBtn");
const addressBar = document.getElementById("addressBar");
const internetSearchBtn = document.getElementById("internetSearchBtn");
const internetBackBtn = document.getElementById("internetBackBtn");
const internetSearchMeta = document.getElementById("internetSearchMeta");

function stopCurrentTTS() {
    if (typeof globalThis.stopTTS === "function") {
        globalThis.stopTTS();
    }
}

function htmlToPlainText(html) {
    const tmp = document.createElement("div");
    tmp.innerHTML = html || "";
    return (tmp.textContent || tmp.innerText || "").replace(/\s+/g, " ").trim();
}

function getDesktopSearchQuery() {
    const defaultQuery = desktopInternetLabels.defaultSearchQuery || "security alerts";
    const typedValue = (addressBar?.value || currentInternetQuery || defaultQuery).trim();
    return typedValue || defaultQuery;
}

function setDesktopInternetState({ view = "results", inputValue = currentInternetQuery, metaText = "" } = {}) {
    if (addressBar) {
        addressBar.value = inputValue;
    }

    if (internetBackBtn) {
        internetBackBtn.style.display = view === "site" ? "inline-flex" : "none";
    }

    if (internetButtons) {
        internetButtons.style.display = view === "site" ? "flex" : "none";
    }

    if (internetSearchMeta) {
        internetSearchMeta.textContent = metaText;
    }
}

function renderDesktopSearchResults(results, query) {
    if (!internetContent) return;

    currentWebsiteHTML = "";
    currentWebsiteType = "";
    cachedDesktopResults = results || [];
    currentInternetQuery = query || currentInternetQuery;

    setDesktopInternetState({
        view: "results",
        inputValue: currentInternetQuery,
        metaText: `${desktopInternetLabels.showingResultsFor || "Showing simulated Google-style results for"} “${currentInternetQuery}”. ${desktopInternetLabels.openAndInspect || "Open a result and inspect the site before deciding."}`
    });

    internetContent.innerHTML = "";

    const stats = document.createElement("div");
    stats.className = "google-results-stats";
    stats.textContent = `${desktopInternetLabels.aboutResults || "About"} ${(results.length || 1) * 184230} results (0.41 ${desktopInternetLabels.secondsSuffix || "seconds"})`;
    internetContent.appendChild(stats);

    (results || []).forEach(site => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = `search-result-card${site.is_sponsored ? " sponsored" : ""}`;

        const topRow = document.createElement("div");
        topRow.className = "search-result-top";

        const favicon = document.createElement("span");
        favicon.className = "search-result-favicon";
        favicon.textContent = site.is_sponsored ? (desktopInternetLabels.adLabel || "Ad") : "🌐";

        const meta = document.createElement("div");
        meta.className = "search-result-meta";

        const link = document.createElement("div");
        link.className = "search-result-link";
        link.textContent = site.url || "https://example.com";

        meta.appendChild(link);

        if (site.is_sponsored) {
            const sponsored = document.createElement("div");
            sponsored.className = "sponsored-label";
            sponsored.textContent = desktopInternetLabels.sponsored || "Sponsored";
            meta.appendChild(sponsored);
        }

        topRow.appendChild(favicon);
        topRow.appendChild(meta);

        const title = document.createElement("div");
        title.className = "search-result-title";
        title.textContent = site.title || "Search Result";

        const description = document.createElement("div");
        description.className = "search-result-description";
        description.textContent = site.description || "No description provided.";

        card.appendChild(topRow);
        card.appendChild(title);
        card.appendChild(description);

        card.addEventListener("click", () => openDesktopWebsite(site));
        internetContent.appendChild(card);
    });

    currentInternetSpeechText = (results || [])
        .map(site => `${site.title}. ${site.description}.`)
        .join(" ");

    if (typeof globalThis.preloadTTS === "function" && currentInternetSpeechText) {
        const lang = (globalThis.getTTSLang && globalThis.getTTSLang()) || "en";
        globalThis.preloadTTS(currentInternetSpeechText, { lang, slow: false }).catch(() => {});
    }
}

/* ========================================
   Load Search Results (List Mode)
======================================== */
async function generateDesktopFakeSites(query = getDesktopSearchQuery()) {
    if (!internetContent) return;

    stopCurrentTTS();
    currentInternetQuery = query;
    setDesktopInternetState({
        view: "results",
        inputValue: currentInternetQuery,
        metaText: `${desktopInternetLabels.searchingGoogleFor || "Searching Google for"} “${currentInternetQuery}”...`
    });
    internetContent.innerHTML = `<p>${desktopInternetLabels.loadingSearchResults || "Loading search results..."}</p>`;

    try {
        const response = await fetch("/api/generate_sites", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: "list", query: currentInternetQuery, free_practice: internetFreePractice })
        });

        const data = await response.json();

        if (!data.success || !data.results) {
            internetContent.innerHTML = `<p>${desktopInternetLabels.errorLoadingSearchResults || "Error loading search results."}</p>`;
            return;
        }

        renderDesktopSearchResults(data.results, data.query || currentInternetQuery);
    } catch (err) {
        console.error(err);
        internetContent.innerHTML = `<p>${desktopInternetLabels.errorLoadingSearchResults || "Error loading search results."}</p>`;
    }
}

/* ========================================
   Open a Website (Open Mode)
======================================== */
async function openDesktopWebsite(site) {
    const title = site?.title || (desktopInternetLabels.website || "Website");
    const url = site?.url || "https://example.com";
    const type = site?.site_type || "legit";

    internetContent.innerHTML = `<p>${desktopInternetLabels.loadingWebsite || "Loading website..."}</p>`;
    stopCurrentTTS();

    try {
        const response = await fetch("/api/generate_sites", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                mode: "open",
                query: currentInternetQuery,
                title,
                url,
                site_type: type
                ,free_practice: internetFreePractice
            })
        });

        const data = await response.json();

        if (!data.success) {
            internetContent.innerHTML = `<p>${desktopInternetLabels.errorLoadingWebsite || "Error loading website."}</p>`;
            return;
        }

        currentWebsiteHTML = data.html;
        currentWebsiteType = type;
        currentInternetDifficulty = data.difficulty;
        currentInternetSpeechText = `${title}. ${url}. ${htmlToPlainText(data.html)}`;

        setDesktopInternetState({
            view: "site",
            inputValue: url,
            metaText: desktopInternetLabels.inspectThenDecide || "Explore the site content, then decide whether the website is real or a scam."
        });

        internetContent.innerHTML = `
            <div class="fake-site">
              <div class="fake-site-header">
                <h2>${title}</h2>
                <p class="fake-url">${url}</p>
              </div>
              <div class="fake-body">${data.html}</div>
            </div>
        `;

        websiteLoadTime = Date.now();

        if (typeof globalThis.preloadTTS === "function" && currentInternetSpeechText) {
            const lang = (globalThis.getTTSLang && globalThis.getTTSLang()) || "en";
            globalThis.preloadTTS(currentInternetSpeechText, { lang, slow: false }).catch(() => {});
        }
    } catch (err) {
        console.error(err);
        internetContent.innerHTML = `<p>${desktopInternetLabels.errorLoadingWebsite || "Error loading website."}</p>`;
    }
}

/* ========================================
   Analyze Website Response
======================================== */
async function analyzeDesktopWebsite(choice) {
    stopCurrentTTS();

    if (!currentWebsiteHTML || !currentWebsiteType) {
        showNotification(false, desktopInternetLabels.openResultFirst || "Open a search result first, then inspect the site.", "internet");
        return;
    }

    const timeSpent = websiteLoadTime ? Math.round((Date.now() - websiteLoadTime) / 1000) : 0;

    try {
        const response = await fetch("/api/analyze_website", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_choice: choice,
                ai_context: currentWebsiteHTML,
                site_type: currentWebsiteType,
                time_spent_seconds: timeSpent,
                free_practice: internetFreePractice
            })
        });

        const data = await response.json();

        if (!data.success) {
            showNotification(false, desktopInternetLabels.errorAnalyzingWebsite || "Error analyzing website.", "internet");
            return;
        }

        const fb = data.feedback;
        const levelText = internetFreePractice ? "Free Practice — not saved" : `${desktopInternetLabels.difficultyLabel || "Difficulty"}: ${data.difficulty_now}`;
        const message = `${fb.explanation} (${levelText})`;
        showNotification(fb.correct, message, "internet");

        if (data.free_practice_available) {
            internetFreePractice = window.confirm(
                "You completed Level 10. Continue with unlimited Free Practice? These answers will not be saved."
            );
        }

        if (cachedDesktopResults && cachedDesktopResults.length) {
            renderDesktopSearchResults(cachedDesktopResults, currentInternetQuery);
        } else {
            generateDesktopFakeSites(currentInternetQuery);
        }
    } catch (err) {
        console.error(err);
        showNotification(false, desktopInternetLabels.serverErrorAnalyzingWebsite || "Server error analyzing website.", "internet");
    }
}

/* ========================================
   Button Event Listeners
======================================== */
if (internetRealBtn) {
    internetRealBtn.addEventListener("click", () => analyzeDesktopWebsite("real"));
}

if (internetFakeBtn) {
    internetFakeBtn.addEventListener("click", () => analyzeDesktopWebsite("fake"));
}

const internetVoiceBtn = document.getElementById("internetVoiceBtn");
if (internetVoiceBtn && window.startVoiceAnswer) {
    internetVoiceBtn.addEventListener("click", () => {
        stopCurrentTTS();
        window.startVoiceAnswer(
            internetVoiceBtn,
            () => analyzeDesktopWebsite("real"),
            () => analyzeDesktopWebsite("fake")
        );
    });
}

if (internetReadAloudBtn) {
    internetReadAloudBtn.addEventListener("click", async () => {
        if (!currentInternetSpeechText) {
            return;
        }

        try {
            if (typeof globalThis.playPreloaded === "function") {
                const played = await globalThis.playPreloaded(currentInternetSpeechText);
                if (played) return;
            }

            if (typeof globalThis.speak === "function") {
                const lang = (globalThis.getTTSLang && globalThis.getTTSLang()) || "en";
                await globalThis.speak(currentInternetSpeechText, { lang, slow: false });
            }
        } catch (err) {
            console.error("Internet TTS playback error:", err);
        }
    });
}

if (internetSearchBtn) {
    internetSearchBtn.addEventListener("click", () => generateDesktopFakeSites());
}

if (addressBar) {
    addressBar.addEventListener("keydown", event => {
        if (event.key === "Enter") {
            event.preventDefault();
            generateDesktopFakeSites();
        }
    });
}

if (internetBackBtn) {
    internetBackBtn.addEventListener("click", () => {
        renderDesktopSearchResults(cachedDesktopResults, currentInternetQuery);
    });
}

/* ========================================
   Internet Icon Opens the Module
======================================== */
document.addEventListener("DOMContentLoaded", () => {
    const internetIcon = document.querySelector(".icon.internet");
    const internetWindow = document.getElementById("internetWindow");

    if (internetIcon && internetWindow) {
        internetIcon.addEventListener("click", () => {
            internetWindow.style.display = "block";
            generateDesktopFakeSites(getDesktopSearchQuery());
        });
    }
});
