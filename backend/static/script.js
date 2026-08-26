document.addEventListener('DOMContentLoaded', function() {
    // Get references to key DOM elements
    const loadingScreen = document.getElementById('loading-screen');
    const content = document.getElementById('content');
    const messageOverlay = document.getElementById('message-overlay');
    const alertOkButtons = document.querySelectorAll('.alert-ok-button'); // Selects all 'OK' buttons within messages

    // --- Message Handling Logic ---
    // Determine if there are any Django messages present on the page
    const hasMessages = alertOkButtons.length > 0;

    if (hasMessages) {
        // If messages are present, immediately hide the loading screen
        loadingScreen.style.display = 'none';

        // Show the message overlay by setting its display property to 'flex' (for centering)
        // and setting its opacity to 1 (CSS transition handles the fade-in)
        messageOverlay.style.display = 'flex';
        messageOverlay.style.opacity = '1';

        // Add an event listener to each 'OK' button to dismiss its respective message
        alertOkButtons.forEach(button => {
            button.addEventListener('click', () => {
                // Find the closest parent 'alert' div to the clicked 'OK' button
                const alertDiv = button.closest('.alert');
                if (alertDiv) {
                    // Start the fade-out effect for the individual alert
                    alertDiv.style.opacity = '0';
                    alertDiv.style.transition = 'opacity 0.3s ease-out'; // Ensure transition is applied

                    // After the fade-out animation completes, remove the alert from the DOM
                    setTimeout(() => {
                        if (alertDiv && alertDiv.parentNode) {
                            alertDiv.remove();
                        }

                        // After removing an alert, check if there are any messages still left
                        const remainingAlerts = document.querySelectorAll('.alert-ok-button').length;
                        if (remainingAlerts === 0 && messageOverlay) {
                            // If no messages remain, fade out the entire message overlay
                            messageOverlay.style.opacity = '0';
                            messageOverlay.style.transition = 'opacity 0.5s ease-out';

                            // After the overlay fades out, hide it completely and display the main content
                            setTimeout(() => {
                                if (messageOverlay) messageOverlay.style.display = 'none';
                                if (content) content.style.display = 'block'; // Show the main content of the page
                            }, 500); // This delay matches the messageOverlay's fade-out transition
                        }
                    }, 300); // This delay matches the individual alert's fade-out transition
                }
            });
        });
    } else {
        // If no messages are present, proceed with the standard loading screen animation
        setTimeout(() => {
            if (loadingScreen) loadingScreen.style.display = 'none'; // Hide loading screen
            if (content) content.style.display = 'block'; // Show main content
        }, 3000); // Your specified loading time (e.g., 3 seconds)
    }

    // --- References to other form elements and modals ---
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    // Important: The form doesn't have an ID, so we select it via its parent and tag name.
    const loginForm = document.querySelector('#login-container form');
    const loginButton = document.getElementById('login-button');
    const logo = document.getElementById('logo');
    const togglePassword = document.getElementById('togglePassword');
    const passwordField = document.getElementById('password');
    const forgotPasswordLink = document.getElementById('forgot-password');
    const modal = document.getElementById('forgot-password-modal');
    // Check if the modal exists before trying to query its close button
    const closeModalButton = modal ? modal.querySelector('.close-modal') : null;

    // --- Input Field Label Animation Logic ---
    const inputs = document.querySelectorAll('.input-group input');
    inputs.forEach(input => {
        // Initial check for autofilled values to ensure labels are positioned correctly on load
        if (input.value.trim() !== '') {
            input.classList.add('has-value');
            input.nextElementSibling.classList.add('active');
        }

        // Event listener for when an input field gains focus
        input.addEventListener('focus', (e) => {
            e.target.nextElementSibling.classList.add('active'); // Move label up
            e.target.closest('.input-group').classList.add('focused'); // Add focus style to the group
        });

        // Event listener for when an input field loses focus
        input.addEventListener('blur', (e) => {
            // If the input is empty, move label back down; otherwise, keep it up
            if (e.target.value.trim() === '') {
                e.target.nextElementSibling.classList.remove('active');
                e.target.classList.remove('has-value');
            } else {
                e.target.classList.add('has-value'); // Ensure has-value class remains if there's content
            }
            e.target.closest('.input-group').classList.remove('focused'); // Remove focus style from the group
        });

        // Event listener for 'change' to handle cases like autofill or pasting, ensuring label position
        input.addEventListener('change', (e) => {
            if (e.target.value.trim() !== '') {
                e.target.classList.add('has-value');
                e.target.nextElementSibling.classList.add('active');
            } else {
                e.target.classList.remove('has-value');
                // Only remove label 'active' class if not currently focused
                if (!e.target.matches(':focus')) {
                    e.target.nextElementSibling.classList.remove('active');
                }
            }
        });
    });

    // A small delay to re-check input fields for values, especially helpful for browser autofill that might trigger later
    setTimeout(() => {
        inputs.forEach(input => {
            if (input.value.trim() !== '') {
                input.classList.add('has-value');
                input.nextElementSibling.classList.add('active');
            }
        });
    }, 100);


    // --- Password Visibility Toggle Logic ---
    if (togglePassword && passwordField) {
        togglePassword.addEventListener('click', () => {
            // Toggle the 'type' attribute between 'password' and 'text'
            const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordField.setAttribute('type', type);

            // Toggle Font Awesome eye icons based on password visibility
            const icon = togglePassword.querySelector('i');
            if (type === 'password') {
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            } else {
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            }
        });
    }

    // --- Login Button Loading State Logic ---
    if (loginForm && loginButton) {
        loginForm.addEventListener('submit', (e) => {
            // Check if the form is valid according to HTML5 validation rules
            if (loginForm.checkValidity()) {
                // Add 'loading' class to button and disable it
                // Note: For actual Django submissions, the page will reload,
                // so this loading state might be very brief unless you handle
                // submission via AJAX.
                loginButton.classList.add('loading');
                loginButton.disabled = true;

                // Do NOT preventDefault() if you want the form to submit to Django
                // and for the page to reload with messages handled by the backend.
                // e.preventDefault(); // <--- This line is commented out for Django submission
            } else {
                // If form is not valid, trigger native HTML5 validation UI
                loginForm.reportValidity();
                console.log("Form is not valid.");
            }
        });
    }


    // --- Logo Animation Trigger ---
    // Starts the pulse animation on the logo after an initial reveal delay
    setTimeout(() => {
         if (logo) {
             logo.classList.add('pulse-active'); // Add class to start CSS pulse animation
             console.log('Logo pulse started');
         }
    }, 1700); // Delay in milliseconds (e.g., 1.2s reveal + 0.5s buffer)


    // --- Forgot Password Modal Logic ---
    if (forgotPasswordLink && modal && closeModalButton) {
        // Open modal when 'Forgot Password?' link is clicked
        forgotPasswordLink.addEventListener('click', (e) => {
            e.preventDefault(); // Prevent default link behavior
            modal.classList.add('show'); // Add 'show' class to display modal via CSS
        });

        // Close modal when the close button is clicked
        closeModalButton.addEventListener('click', () => {
            modal.classList.remove('show'); // Remove 'show' class to hide modal
        });

        // Close modal if the user clicks outside the modal content area
        window.addEventListener('click', (e) => {
            if (e.target === modal) { // Check if the click occurred directly on the modal background
                modal.classList.remove('show');
            }
        });
    }

    // --- Canvas Particle System Placeholder (if you plan to implement it) ---
    const particlesContainer = document.getElementById('particles-container');
    if (particlesContainer /* && youDecideToImplementCanvas */) {
        // This is a placeholder. A full canvas-based particle system would involve:
        // 1. Creating a <canvas> element dynamically or using an existing one.
        // 2. Getting its 2D rendering context (canvas.getContext('2d')).
        // 3. Defining a Particle object with properties (x, y, velocity, color, size, etc.).
        // 4. Creating an array of Particle instances.
        // 5. Implementing an animation loop using `requestAnimationFrame` that:
        //    - Clears the canvas.
        //    - Updates each particle's position and properties.
        //    - Draws each particle on the canvas.
        //    - Handles boundary conditions (e.g., particles leaving the screen).
        console.warn('Advanced particle system requires Canvas implementation. Current CSS is approximation.');
    }

}); // End DOMContentLoaded