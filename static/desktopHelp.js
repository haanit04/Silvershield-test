document.addEventListener("DOMContentLoaded", () => {
    const hints = {
        desktop: document.querySelector('[data-training-hint="desktop"]'),
        email: document.querySelector('[data-training-hint="email"]'),
        internet: document.querySelector('[data-training-hint="internet"]')
    };

    const showHint = (name) => {
        const hint = hints[name];
        if (hint) hint.hidden = false;
    };

    document.querySelectorAll(".training-hint__close").forEach((button) => {
        button.addEventListener("click", () => {
            const hint = button.closest(".training-hint");
            if (hint) hint.hidden = true;
        });
    });

    document.querySelector(".icon.help")?.addEventListener("click", () => {
        showHint("desktop");
    });

    document.querySelector(".icon.email")?.addEventListener("click", () => {
        showHint("email");
    });

    document.querySelector(".icon.internet")?.addEventListener("click", () => {
        showHint("internet");
    });
});
