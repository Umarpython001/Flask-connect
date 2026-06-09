// Site-wide JS.  Currently just a small auto-dismiss helper for flash alerts.

(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        // Auto-dismiss Bootstrap alerts after 4s.
        const alerts = document.querySelectorAll(".alert.fade.show");
        alerts.forEach(function (el) {
            setTimeout(function () {
                if (window.bootstrap && window.bootstrap.Alert) {
                    const instance = window.bootstrap.Alert.getOrCreateInstance(el);
                    instance.close();
                } else {
                    el.classList.remove("show");
                    el.style.display = "none";
                }
            }, 4000);
        });
    });
})();
