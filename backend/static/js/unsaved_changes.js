/**
 * WildEye Unsaved Changes Protection
 * Automatically detects when form inputs are modified and prompts the user
 * before navigating away (via browser Back/Forward, link clicks, or closing tab).
 */
(function() {
    let isFormDirty = false;
    let isFormSubmitting = false;

    // Helper to check if an element should be tracked
    function shouldTrackElement(el) {
        if (!el || !el.form) return false;
        const form = el.form;

        // Exclude forms explicitly marked with data-unsaved-protection="false"
        if (form.getAttribute('data-unsaved-protection') === 'false') return false;

        // Exclude hidden inputs, search fields, or elements explicitly marked to ignore
        if (el.type === 'hidden' || el.type === 'search' || el.classList.contains('no-unsaved-track')) return false;

        return true;
    }

    // Listen for input and change events across the document
    document.addEventListener('input', function(e) {
        if (shouldTrackElement(e.target)) {
            isFormDirty = true;
        }
    }, true);

    document.addEventListener('change', function(e) {
        if (shouldTrackElement(e.target)) {
            isFormDirty = true;
        }
    }, true);

    // Reset dirty flag when any form is submitted via standard submit event
    document.addEventListener('submit', function(e) {
        isFormSubmitting = true;
    }, true);

    // Override HTMLFormElement.prototype.submit so programmatic form.submit() calls also disable warning
    const originalSubmit = HTMLFormElement.prototype.submit;
    HTMLFormElement.prototype.submit = function() {
        isFormSubmitting = true;
        return originalSubmit.apply(this, arguments);
    };

    // Warn user before unload if form has unsaved changes and is not being submitted
    window.addEventListener('beforeunload', function(e) {
        if (isFormDirty && !isFormSubmitting) {
            e.preventDefault();
            e.returnValue = ''; // Standard requirement for modern browsers
            return '';
        }
    });

    // Global utility to reset dirty state manually (e.g. after AJAX saves)
    window.resetUnsavedChanges = function() {
        isFormDirty = false;
        isFormSubmitting = false;
    };
})();
