/*************************
      Email Functions
**************************/
let lastGeneratedEmail = "";
let lastEmailExpectedLabel = "";
let emailLoadTime = null;
let emailFreePractice = false;
const desktopEmailLabels = globalThis.desktopLabels || {};

document.addEventListener("DOMContentLoaded", () => {
    const emailIcon = document.querySelector(".icon.email");
    const emailWindow = document.getElementById("emailWindow");
    const emailContent = document.getElementById("emailContent");

    const rfContainer = document.getElementById("emailButtons");
    const realBtn = document.getElementById("realBtn");
    const fakeBtn = document.getElementById("fakeBtn");

    /* Loading AI generated Email */
    async function loadEmail()
    {
        // Stop any playing audio when loading a new email
        if (window.stopTTS) try { window.stopTTS(); } catch (e) {}
        emailContent.textContent = desktopEmailLabels.generatingEmail || "Generating email...";
        rfContainer.style.display = "none";

        try
        {
            const response = await fetch("/generate-email", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    theme: "Email Scam Training",
                    platform: "desktop",
                    free_practice: emailFreePractice
                })
            });

            const data = await response.json();

            if (data.success && data.email)
            {
                emailContent.innerHTML = data.email;
                lastGeneratedEmail = data.email;
                lastEmailExpectedLabel = data.expected_label || "";
                emailLoadTime = Date.now();  // Record time email was displayed
                rfContainer.style.display = "flex";

                // Preload TTS immediately to reduce play delay
                try {
                    const tmp = document.createElement('div');
                    tmp.innerHTML = lastGeneratedEmail;
                    const plain = tmp.textContent || tmp.innerText || '';
                    if (window.preloadTTS) {
                        const lang = (window.getTTSLang && window.getTTSLang()) || 'en';
                        window.preloadTTS(plain, { lang, slow: false }).catch && window.preloadTTS(plain, { lang, slow: false });
                    }
                } catch (e) { console.warn('Preload TTS failed', e); }
            }
            else
            {
                emailContent.innerHTML = `<p style="color:#c00;text-align:center;padding:16px;">${desktopEmailLabels.couldNotGenerateEmail || "Could not generate email. Please close and try again."}</p>`;
            }

        }
        catch (err)
        {
            console.error("Email load error:", err);
            emailContent.textContent = desktopEmailLabels.serverError || "Server error.";
        }
    }

    /* Analyzing User Choice */
    async function sendUserAnswer(choice)
    {
        // stop audio when user makes a choice
        if (window.stopTTS) try { window.stopTTS(); } catch (e) {}

        if(!lastGeneratedEmail)
        {
            console.warn("No generated email stored for analysis.");
            return showNotification(false, desktopEmailLabels.noEmailLoadedToAnalyze || "No email loaded to analyze.", "email");
        }

        // Calculate time spent on email (in seconds)
        const timeSpent = emailLoadTime ? Math.round((Date.now() - emailLoadTime) / 1000) : 0;

        try
        {
            const response = await fetch("/api/analyze", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    user_choice: choice,
                    message: lastGeneratedEmail,
                    expected_label: lastEmailExpectedLabel,
                    time_spent_seconds: timeSpent,
                    free_practice: emailFreePractice
                })
            });

            const result = await response.json();

            if (!result.success)
            {
                return showNotification(false, desktopEmailLabels.errorAnalyzingResponse || "Error analyzing response.", "email");
            }

            const correct = result.feedback.correct;
            const feedback = result.feedback.feedback;
            const difficulty = result.difficulty_now;

            showNotification(
                correct,
                `${feedback} (${emailFreePractice ? "Free Practice — not saved" : `${desktopEmailLabels.difficultyLabel || "Difficulty"}: ${difficulty}`})`,
                "email"
            );

            if (result.free_practice_available) {
                emailFreePractice = window.confirm(
                    "You completed Level 10. Continue with unlimited Free Practice? These answers will not be saved."
                );
            }

            loadEmail();
        }
        catch (err)
        {
            console.error("Email analysis error:", err);
            showNotification(false, desktopEmailLabels.serverErrorAnalyzingResponse || "Server error analyzing response.", "email");
        }
    }

    /* Event Listeners */
    if (emailIcon && emailWindow)
    {
        emailIcon.addEventListener("click", () => {
            // stop any playing audio and open the window
            if (window.stopTTS) try { window.stopTTS(); } catch (e) {}
            emailWindow.style.display = "block";
            loadEmail();
        });
    }

    /* Read Aloud button */
    const readAloudBtn = document.getElementById('readAloudBtn');
    if (readAloudBtn && !readAloudBtn.dataset.bound) {
        readAloudBtn.dataset.bound = true;
        readAloudBtn.addEventListener('click', async () => {
            if (!lastGeneratedEmail) {
                return showNotification(false, desktopEmailLabels.noEmailLoadedToRead || 'No email loaded to read.', 'email');
            }

            // Convert HTML to plain text for TTS
            const tmp = document.createElement('div');
            tmp.innerHTML = lastGeneratedEmail;
            const plain = tmp.textContent || tmp.innerText || '';

            try {
                // If a preloaded audio matches, play it for near-instant playback
                if (window.playPreloaded) {
                    const played = window.playPreloaded(plain);
                    if (played) return;
                }

                if (window.speak) {
                    const lang = (window.getTTSLang && window.getTTSLang()) || 'en';
                    await window.speak(plain, { lang, slow: false });
                } else {
                    console.warn('TTS helper not available.');
                }
            } catch (err) {
                console.error('TTS playback error:', err);
            }
        });
    }

    /* Real and Fake button */
    if (realBtn && !realBtn.dataset.bound) {
        realBtn.dataset.bound = true;
        realBtn.addEventListener("click", () => {
            if (window.stopTTS) try { window.stopTTS(); } catch (e) {}
            sendUserAnswer("real");
        });
    }

    if (fakeBtn && !fakeBtn.dataset.bound) {
        fakeBtn.dataset.bound = true;
        fakeBtn.addEventListener("click", () => {
            if (window.stopTTS) try { window.stopTTS(); } catch (e) {}
            sendUserAnswer("fake");
        });
    }

    const emailVoiceBtn = document.getElementById("emailVoiceBtn");
    if (emailVoiceBtn && !emailVoiceBtn.dataset.bound && window.startVoiceAnswer) {
        emailVoiceBtn.dataset.bound = true;
        emailVoiceBtn.addEventListener("click", () => {
            if (window.stopTTS) try { window.stopTTS(); } catch (e) {}
            window.startVoiceAnswer(
                emailVoiceBtn,
                () => sendUserAnswer("real"),
                () => sendUserAnswer("fake")
            );
        });
    }

    /* Close Popup */
    document.querySelectorAll(".popup-close").forEach(btn =>
        btn.addEventListener("click", () => {
            // stop audio when popup is closed
            if (window.stopTTS) try { window.stopTTS(); } catch (e) {}
            btn.closest(".popup").style.display = "none"
        })
    );
});
