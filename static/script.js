/*************************
      Mobile Scenario Engine - Email, Web, SMS, Call apps
**************************/
let currentMessage = "";
let currentType = "";
let currentDifficulty = "";
let currentExpectedLabel = "";
let currentFreePractice = false;
let freePracticeType = "";
let scenarioLoadTime = null;
let currentWebQuery = "";
let currentWebResults = null;
const mobileLabels = globalThis.mobileLabels || {};

function applyMobileTranslations() {
    const backLabel = mobileLabels.back || "Back";
    const readAloudLabel = mobileLabels.readAloud || "Read Aloud";
    const realLabel = mobileLabels.real || "REAL";
    const fakeLabel = mobileLabels.fake || "FAKE";
    const speakLabel = mobileLabels.speak || "Speak";
    const muteLabel = mobileLabels.mute || "Mute";
    const endLabel = mobileLabels.end || "End";
    const speakerLabel = mobileLabels.speaker || "Speaker";
    const reportScamCallLabel = mobileLabels.reportScamCall || fakeLabel;
    const looksSafeLabel = mobileLabels.looksSafe || realLabel;
    const gmailLabel = mobileLabels.gmail || "Gmail";
    const chromeLabel = mobileLabels.chrome || "Chrome";

    const gmailWordmark = document.querySelector(".gmail-mobile-wordmark");
    if (gmailWordmark) gmailWordmark.textContent = gmailLabel;

    const browserTitle = document.querySelector(".web-browser-title");
    if (browserTitle) browserTitle.textContent = chromeLabel;

    const mailSearchPill = document.querySelector(".gmail-mobile-search-pill");
    if (mailSearchPill) mailSearchPill.textContent = mobileLabels.searchInMail || "Search in mail";

    const mailboxLabel = document.querySelector(".gmail-mobile-mailbox");
    if (mailboxLabel) mailboxLabel.textContent = mobileLabels.primaryInbox || "Primary Inbox";

    const unreadLabel = document.querySelector(".gmail-mobile-unread");
    if (unreadLabel) unreadLabel.textContent = mobileLabels.oneNew || "1 new";

    const emailLoading = document.getElementById("emailBody");
    if (emailLoading && /loading email/i.test(emailLoading.textContent || "")) {
        emailLoading.textContent = mobileLabels.loadingEmail || "Loading email...";
    }

    const fakeSearchInput = document.getElementById("fakeSearchInput");
    if (fakeSearchInput) {
        fakeSearchInput.placeholder = mobileLabels.searchOrTypeAddress || "Search or type web address";
    }

    const mobileSearchBtn = document.getElementById("mobileSearchBtn");
    if (mobileSearchBtn) mobileSearchBtn.textContent = mobileLabels.go || "Go";

    const chips = document.querySelectorAll(".chrome-mobile-chip");
    if (chips[0]) chips[0].textContent = mobileLabels.all || "All";
    if (chips[1]) chips[1].textContent = mobileLabels.news || "News";
    if (chips[2]) chips[2].textContent = mobileLabels.images || "Images";

    const backToResultsBtn = document.getElementById("webBackToResults");
    if (backToResultsBtn) backToResultsBtn.textContent = mobileLabels.results || "Results";

    const webStatusText = document.getElementById("webStatusText");
    if (webStatusText && /search a topic/i.test(webStatusText.textContent || "")) {
        webStatusText.textContent = mobileLabels.searchAndInspect || "Search a topic, open a result, and inspect the site before choosing REAL or FAKE.";
    }

    const chromeFooter = document.querySelector(".chrome-mobile-footer");
    if (chromeFooter) chromeFooter.textContent = `${mobileLabels.googleFooter || "Google"} © 2025`;

    document.querySelectorAll(".back-btn, .back-button").forEach(btn => {
        btn.textContent = `← ${backLabel}`;
    });

    const readBtn = document.getElementById("readAloudMobile");
    if (readBtn) {
        readBtn.textContent = document.querySelector(".call-app") ? speakerLabel : readAloudLabel;
    }

    const safeBtn = document.getElementById("markSafe");
    if (safeBtn) {
        safeBtn.textContent = document.querySelector(".call-app") ? looksSafeLabel : realLabel;
    }

    const scamBtn = document.getElementById("markScam");
    if (scamBtn) {
        scamBtn.textContent = document.querySelector(".call-app") ? reportScamCallLabel : fakeLabel;
    }

    const voiceBtn = document.getElementById("voiceAnswerBtn");
    if (voiceBtn) voiceBtn.textContent = speakLabel;

    const callButtons = document.querySelectorAll(".call-controls .call-btn");
    if (callButtons[0]) callButtons[0].textContent = muteLabel;
    if (callButtons[1]) callButtons[1].textContent = endLabel;
}

function buildWebSpeechText(sc) {
    if (!sc) return "";

    const adText = (sc.ads || [])
        .map(ad => `${ad.title || "Sponsored result"}. ${ad.snippet || ""}`)
        .join(" ");

    const resultText = (sc.results || [])
        .map(result => `${result.title || "Result"}. ${result.snippet || ""}`)
        .join(" ");

    return `${adText} ${resultText}`.replace(/\s+/g, " ").trim();
}

function htmlToPlainText(html) {
    const temp = document.createElement("div");
    temp.innerHTML = html || "";
    return (temp.textContent || temp.innerText || "").replace(/\s+/g, " ").trim();
}

const ScenarioEngine = {
    endpoints: {
        email: "/generate-email",
        sms: "/generate-sms",
        call: "/generate-call",
        web: "/generate-web"
    },

    async load(type) {
        // Free practice belongs to the module the user just completed, not every app.
        if (currentFreePractice && freePracticeType && freePracticeType !== type) {
            currentFreePractice = false;
            freePracticeType = "";
        }
        currentType = type;
        currentExpectedLabel = "";

        const scenarioBody = document.getElementById("scenarioBody");
        const appsGrid = document.querySelector(".apps");
        if (!scenarioBody || !appsGrid) return;

        scenarioBody.innerHTML = "<p class='loading'>Loading scenario...</p>";
        if (mobileLabels.loadingScenario) {
            scenarioBody.innerHTML = `<p class='loading'>${mobileLabels.loadingScenario}</p>`;
        }
        appsGrid.style.display = "none";

        // Load snippet HTML template
        const htmlResp = await fetch(`/static/snippets/${type}.html`);
        scenarioBody.innerHTML = await htmlResp.text();
        applyMobileTranslations();

        if (type === "web") {
            this.setupWebSearchUI();
            await this.loadWebSearch((document.getElementById("fakeSearchInput")?.value || "bank account security tips").trim());
            return;
        }

        // Pick appropriate endpoint
        const endpoint = this.endpoints[type];
        if (!endpoint) return;

        // Fetch scenario from backend
        const res = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                theme: "SilverShield training",
                platform: type === "email" ? "mobile" : undefined,
                free_practice: currentFreePractice
            })
        });

        const data = await res.json();
        if (!data.success) {
            scenarioBody.innerHTML = `<p>${mobileLabels.errorLoadingScenario || "Error loading scenario."}</p>`;
            console.error("Scenario error:", data.error);
            return;
        }

        currentDifficulty = data.difficulty;

        const diffLabel = document.getElementById("difficultyLabel");
        if (diffLabel) {
            diffLabel.innerText = currentFreePractice
                ? "Free Practice — Level 10 (not saved)"
                : `${mobileLabels.level || "Level"}: ${currentDifficulty}`;
        }

        // Record time scenario was displayed
        scenarioLoadTime = Date.now();

        // Map returned data to scenario object for UI
        let sc = null;
        if (type === "email") sc = { email_html: data.email };
        else if (type === "sms") sc = data.sms;
        else if (type === "call") sc = data.call;
        else if (type === "web") sc = data.web;

        // Capture server-provided ground truth label for grading.
        if (type === "email" || type === "sms" || type === "call" || type === "web") {
            const raw = (data.expected_label || sc?.expected_label || sc?.label || "").toLowerCase();
            if (raw === "scam" || raw === "fake") {
                currentExpectedLabel = "scam";
            } else if (raw === "not_scam" || raw === "real") {
                currentExpectedLabel = "not_scam";
            } else {
                currentExpectedLabel = "";
            }
        }

        this.fill(type, sc);

        // After filling UI, if email was loaded, attempt to preload TTS
        if (currentMessage && (type === 'email' || type === 'sms' || type === 'call' || type === 'web')) {
            try {
                const tmp = document.createElement('div');
                tmp.innerHTML = currentMessage;
                const plain = (tmp.textContent || tmp.innerText || '').replace(/\s+/g,' ').trim();
                if (window.preloadTTS) {
                    const lang = (window.getTTSLang && window.getTTSLang()) || 'en';
                    // fire-and-forget preload (internal dedupe prevents duplicates)
                    try { window.preloadTTS(plain, { lang, slow: false }); } catch(e) { /* ignore */ }
                }
            } catch (e) { console.warn('Preload TTS failed', e); }
        }

        // Hook up scam/safe buttons
        const scamBtn = document.getElementById("markScam");
        const safeBtn = document.getElementById("markSafe");
        const readAloudMobile = document.getElementById('readAloudMobile');

        if (scamBtn) scamBtn.onclick = () => { if (window.stopTTS) try { window.stopTTS(); } catch(e){}; analyzeChoice("scam"); };
        if (safeBtn) safeBtn.onclick = () => { if (window.stopTTS) try { window.stopTTS(); } catch(e){}; analyzeChoice("not_scam"); };

        const voiceBtn = document.getElementById("voiceAnswerBtn");
        if (voiceBtn && window.startVoiceAnswer) {
            voiceBtn.onclick = () => {
                if (window.stopTTS) try { window.stopTTS(); } catch(e) {}
                window.startVoiceAnswer(
                    voiceBtn,
                    () => analyzeChoice("not_scam"),
                    () => analyzeChoice("scam")
                );
            };
        }

        if (readAloudMobile) {
            readAloudMobile.onclick = async () => {
                try {
                    const tmp = document.createElement('div'); tmp.innerHTML = currentMessage;
                    const plain = (tmp.textContent || tmp.innerText || '').replace(/\s+/g,' ').trim();
                    if (window.playPreloaded) {
                        const played = await window.playPreloaded(plain);
                        if (played) return;
                    }
                    if (window.speak) {
                        const lang = (window.getTTSLang && window.getTTSLang()) || 'en';
                        await window.speak(plain, { lang, slow: false });
                    }
                } catch (e) { console.warn('Mobile TTS play failed', e); }
            };
        }
    },

    setupWebSearchUI() {
        const webActions = document.getElementById("webActions");
        const searchInput = document.getElementById("fakeSearchInput");
        const searchBtn = document.getElementById("mobileSearchBtn");
        const resultsBtn = document.getElementById("webBackToResults");
        const statusText = document.getElementById("webStatusText");

        if (webActions) webActions.style.display = "none";
        if (resultsBtn) resultsBtn.style.display = "none";
        if (statusText) {
            statusText.textContent = mobileLabels.searchAndInspect || "Search a topic, open a result, and inspect the page before deciding if it is real or a scam.";
        }

        if (searchBtn && !searchBtn.dataset.bound) {
            searchBtn.dataset.bound = "true";
            searchBtn.onclick = () => this.loadWebSearch(searchInput?.value || "bank account security tips");
        }

        if (searchInput && !searchInput.dataset.bound) {
            searchInput.dataset.bound = "true";
            searchInput.addEventListener("keydown", event => {
                if (event.key === "Enter") {
                    event.preventDefault();
                    this.loadWebSearch(searchInput.value || "bank account security tips");
                }
            });
        }

        if (resultsBtn && !resultsBtn.dataset.bound) {
            resultsBtn.dataset.bound = "true";
            resultsBtn.onclick = () => {
                if (currentWebResults) {
                    this.renderMobileWebResults(currentWebResults);
                }
            };
        }
    },

    async loadWebSearch(query) {
        const normalizedQuery = (query || "bank account security tips").trim() || "bank account security tips";
        const container = document.getElementById("web-content");
        const statusText = document.getElementById("webStatusText");
        const webActions = document.getElementById("webActions");
        const resultsBtn = document.getElementById("webBackToResults");
        const searchInput = document.getElementById("fakeSearchInput");

        currentType = "web";
        currentWebQuery = normalizedQuery;
        currentExpectedLabel = "";
        currentMessage = "";
        scenarioLoadTime = Date.now();

        if (searchInput) searchInput.value = normalizedQuery;
        if (webActions) webActions.style.display = "none";
        if (resultsBtn) resultsBtn.style.display = "none";
        if (statusText) statusText.textContent = `${mobileLabels.searchingFor || "Searching for"} “${normalizedQuery}”...`;
        if (container) container.innerHTML = `<p class='loading'>${mobileLabels.loadingSearchResults || "Loading search results..."}</p>`;

        try {
            const response = await fetch("/generate-web", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode: "search", query: normalizedQuery, free_practice: currentFreePractice })
            });

            const data = await response.json();
            if (!data.success || !data.web) {
                throw new Error(data.error || mobileLabels.searchResultsFailed || "Search results failed to load.");
            }

            currentDifficulty = data.difficulty;
            currentWebResults = data.web;
            currentMessage = buildWebSpeechText(data.web);
            this.renderMobileWebResults(data.web);

            if (window.preloadTTS && currentMessage) {
                const lang = (window.getTTSLang && window.getTTSLang()) || "en";
                try { window.preloadTTS(currentMessage, { lang, slow: false }); } catch (e) { /* ignore */ }
            }
        } catch (err) {
            console.error("loadWebSearch error:", err);
            if (container) container.innerHTML = `<p>${mobileLabels.errorLoadingSearchResults || "Error loading search results."}</p>`;
            if (statusText) statusText.textContent = mobileLabels.tryDifferentSearch || "Try a different search or reload the scenario.";
        }
    },

    async openWebResult(site) {
        const container = document.getElementById("web-content");
        const statusText = document.getElementById("webStatusText");
        const webActions = document.getElementById("webActions");
        const resultsBtn = document.getElementById("webBackToResults");
        const searchInput = document.getElementById("fakeSearchInput");

        if (!site || !container) return;

        container.innerHTML = `<p class='loading'>${mobileLabels.loadingWebsite || "Loading website..."}</p>`;
        if (statusText) statusText.textContent = mobileLabels.loadingSelectedWebsite || "Loading the selected website...";

        try {
            const response = await fetch("/generate-web", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    mode: "open",
                    query: currentWebQuery,
                    title: site.title,
                    url: site.url,
                    site_type: site.site_type,
                    free_practice: currentFreePractice
                })
            });

            const data = await response.json();
            if (!data.success) {
                throw new Error(data.error || "Unable to open site.");
            }

            currentExpectedLabel = site.site_type === "phishing" ? "scam" : "not_scam";
            currentMessage = `${site.title}. ${site.url}. ${htmlToPlainText(data.html)}`;
            scenarioLoadTime = Date.now();

            if (searchInput) searchInput.value = site.url;
            if (resultsBtn) resultsBtn.style.display = "inline-flex";
            if (webActions) webActions.style.display = "grid";
            if (statusText) {
                statusText.textContent = mobileLabels.inspectAndChoose || "Inspect the website carefully, then choose REAL or FAKE.";
            }

            container.innerHTML = `
                <div class="mobile-site-page">
                    <div class="mobile-site-header">
                        <div class="search-result-title">${site.title}</div>
                        <div class="search-result-link">${site.url}</div>
                    </div>
                    <div class="web-content-body">${data.html}</div>
                </div>
            `;

            if (window.preloadTTS && currentMessage) {
                const lang = (window.getTTSLang && window.getTTSLang()) || "en";
                try { window.preloadTTS(currentMessage, { lang, slow: false }); } catch (e) { /* ignore */ }
            }
        } catch (err) {
            console.error("openWebResult error:", err);
            container.innerHTML = `<p>${mobileLabels.errorLoadingWebsite || "Error loading website."}</p>`;
            if (statusText) statusText.textContent = mobileLabels.unableToOpenResult || "Unable to open that result. Please try another one.";
        }
    },

    renderMobileWebResults(sc) {
        const container = document.getElementById("web-content");
        const statusText = document.getElementById("webStatusText");
        const webActions = document.getElementById("webActions");
        const resultsBtn = document.getElementById("webBackToResults");
        const pagination = document.getElementById("pagination");
        const searchInput = document.getElementById("fakeSearchInput");

        if (!container || !sc) return;

        currentExpectedLabel = "";
        currentMessage = buildWebSpeechText(sc);
        if (webActions) webActions.style.display = "none";
        if (resultsBtn) resultsBtn.style.display = "none";
        if (pagination) pagination.innerHTML = "";
        if (searchInput) searchInput.value = currentWebQuery;
        if (statusText) {
            statusText.textContent = `${mobileLabels.showingResultsFor || "Showing results for"} “${currentWebQuery}”. ${mobileLabels.openAndInspectBeforeAnswer || "Open a site and inspect it before answering."}`;
        }

        container.innerHTML = "";

        const stats = document.createElement("div");
        stats.className = "search-results-stats";
        stats.textContent = `${mobileLabels.about || "About"} ${((sc.results || []).length + (sc.ads || []).length) * 142000} results (0.38 ${mobileLabels.seconds || "seconds"})`;
        container.appendChild(stats);

        const renderCard = (item, sponsored = false) => {
            const card = document.createElement("button");
            card.type = "button";
            card.className = `search-result ${sponsored ? "sponsored" : ""}`;
            card.innerHTML = `
                ${sponsored ? '<div class="sponsored-label">Sponsored</div>' : ''}
                <div class="search-result-title">${item.title || mobileLabels.searchResult || "Search Result"}</div>
                <div class="search-result-link">${item.url}</div>
                <div class="search-result-snippet">${item.snippet || mobileLabels.noDescriptionProvided || "No description provided."}</div>
            `;
            if (sponsored) {
                card.querySelector('.sponsored-label').textContent = mobileLabels.sponsored || 'Sponsored';
            }
            card.onclick = () => this.openWebResult(item);
            container.appendChild(card);
        };

        (sc.ads || []).forEach(ad => renderCard(ad, true));
        (sc.results || []).forEach(result => renderCard(result, false));

        if (pagination) {
            pagination.innerHTML = `<button id="nextPageBtn">${sc.pagination?.next_page_label || `${mobileLabels.nextPage || "Next"} >`}</button>`;
            const nextPageBtn = document.getElementById("nextPageBtn");
            if (nextPageBtn) {
                nextPageBtn.onclick = () => this.loadWebSearch(currentWebQuery);
            }
        }
    },

    fill(type, sc) {
        if (!sc) return;

        // EMAIL
        if (type === "email") {
            const emailBody = document.getElementById("emailBody");
           // const emailSubject = document.getElementById("emailSubject");
            //const fromName = document.getElementById("from-name");
            //const fromEmail = document.getElementById("from-email");


            const htmlEmail = sc.email_html;
            currentMessage = htmlEmail;

            emailBody.innerHTML = htmlEmail;

          //  const fromMatch = htmlEmail.match(/<b>From:<\/b>\s*(.*?)<br>/i);
            //const dateMatch = htmlEmail.match(/<b>Date:<\/b>\s*(.*?)<br>/i);

            //const senderString = fromMatch ? fromMatch[1] : "Unknown";

            // parsed metadata
            //emailSubject.innerText = subjectMatch ? subjectMatch[1] : "No Subject";
            //metaFrom.innerText = senderString;
            //metaDate.innerText = dateMatch ? dateMatch[1] : "";

            //avatar - 1st letter of sender's name
            //const initial = senderString.charAt(0).toUpperCase();
            //senderAvatar.innerText = initial;

            //fromEmail.innerText = fromMatch ? fromMatch[1] : "unknown@sender.com";
            //fromName.innerText = "Sender";
            return;
        }

        // SMS
        if (type === "sms") {
            document.getElementById("smsBody").innerText = sc.text;
            document.getElementById("smsNumber").innerText = sc.number;
            document.getElementById("smsTime").innerText = sc.time || "Today 12:04 PM";

            const smsContactName = document.getElementById("smsContactName");
            const smsAvatar = document.getElementById("smsAvatar");
            const senderLabel = sc.sender_name || mobileLabels.bankAlerts || "Bank Alerts";

            if (smsContactName) smsContactName.innerText = senderLabel;
            if (smsAvatar) smsAvatar.innerText = senderLabel.charAt(0).toUpperCase();

            currentMessage = sc.text;
            return;
        }

        // CALL
        if (type === "call") {
            document.getElementById("call-number").innerText = sc.number;
            document.getElementById("call-caller").innerText = sc.caller_name || mobileLabels.unknownCaller || "Unknown Caller";
            document.getElementById("call-transcript").innerText = sc.transcript;
            currentMessage = sc.transcript;
            return;
        }

        // WEB
        if (type === "web") {
            this.renderMobileWebResults(sc);
            return;
        }
    }
};

// Make openApp globally available
window.openApp = type => ScenarioEngine.load(type);

// back button module ui app
function backToApps(){
    const scenarioBody = document.getElementById("scenarioBody");
    const appsGrid = document.querySelector(".apps");

    if(scenarioBody) scenarioBody.innerHTML = "";
    if(appsGrid) appsGrid.style.display = "block"; //restore grid

    // Stop any playing TTS when user navigates back
    if (window.stopTTS) try { window.stopTTS(); } catch (e) {}

    console.log("Back button clicked --> Returning to app menu.")
}

// stop any TTS when leaving the scenario
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && window.stopTTS) {
        try { window.stopTTS(); } catch (e) {}
    }
});

async function analyzeChoice(choice) {
    try {
        if (currentType === "web" && !currentExpectedLabel) {
            alert(mobileLabels.openSearchResultFirst || "Open a search result and inspect the site before answering.");
            return;
        }

        // Calculate time spent on scenario (in seconds)
        const timeSpent = scenarioLoadTime ? Math.round((Date.now() - scenarioLoadTime) / 1000) : 0;

        const response = await fetch("/api/analyze_any", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                type: currentType,
                platform: "mobile",
                user_choice: choice,
                expected_label: currentExpectedLabel || undefined,
                message: currentMessage,
                time_spent_seconds: timeSpent,
                free_practice: currentFreePractice
            })
        });

        const data = await response.json();

        if (!data.success) {
            alert(mobileLabels.errorAnalyzingResponse || "Error analyzing response.");
            return;
        }

        alert(
            data.feedback.feedback +
            `\n\n(${currentFreePractice ? "Free Practice — not saved" : `${mobileLabels.currentDifficulty || "Current difficulty"}: ${data.difficulty_now}`})`
        );

        if (data.free_practice_available) {
            currentFreePractice = window.confirm(
                "You completed Level 10. Continue with unlimited Free Practice? These answers will not be saved."
            );
            freePracticeType = currentFreePractice ? currentType : "";
        }

        // Reload next scenario automatically
        ScenarioEngine.load(currentType);

    } catch (err) {
        console.error("analyzeChoice() error:", err);
        alert(mobileLabels.serverErrorAnalyzingChoice || "Server error analyzing choice.");
    }
}

/*************************
   BUTTON HANDLERS
   (for mobile + desktop)
**************************/

document.addEventListener("click", () => {
    const realBtn = document.getElementById("markSafe"); //mobile real
    const fakeBtn = document.getElementById("markScam"); //mobile fake
    const desktopReal = document.getElementById("realBtn");
    const desktopFake = document.getElementById("fakeBtn");
    // Bind handlers once and ensure TTS is stopped before submitting
    if (realBtn && !realBtn.dataset.bound) {
        realBtn.dataset.bound = true;
        realBtn.onclick = () => {
            if (window.stopTTS) try { window.stopTTS(); } catch (e) {}
            analyzeChoice("not_scam");
        };
    }

    if (fakeBtn && !fakeBtn.dataset.bound) {
        fakeBtn.dataset.bound = true;
        fakeBtn.onclick = () => {
            if (window.stopTTS) try { window.stopTTS(); } catch (e) {}
            analyzeChoice("scam");
        };
    }

    if (desktopReal && !desktopReal.dataset.bound) {
        desktopReal.dataset.bound = true;
        desktopReal.onclick = () => {
            if (window.stopTTS) try { window.stopTTS(); } catch (e) {}
            analyzeChoice("not_scam");
        };
    }

    if (desktopFake && !desktopFake.dataset.bound) {
        desktopFake.dataset.bound = true;
        desktopFake.onclick = () => {
            if (window.stopTTS) try { window.stopTTS(); } catch (e) {}
            analyzeChoice("scam");
        };
    }
});

window.analyzeChoice = analyzeChoice;

window.backToApps = backToApps;
