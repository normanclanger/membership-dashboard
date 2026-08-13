import {
    requireLogin,
    signOutRedirect
} from "/js/auth.js";


document.addEventListener(
    "DOMContentLoaded",
    async () => {

        const protectedPage =
            document.body.dataset.protected === "true";

        if (!protectedPage) {
            return;
        }

        try {

            const user =
                await requireLogin();

            if (!user) {
                return;
            }

            window.currentUser =
                user;

            const signedInUser =
                document.querySelector(
                    "#signed-in-user"
                );

            if (signedInUser) {

                const email =
                    user.profile?.email ||
                    "Unknown user";

                signedInUser.textContent =
                    `Signed in as ${email}`;
            }

            const logoutButton =
                document.querySelector(
                    "#logout-button"
                );

            if (logoutButton) {

                logoutButton.addEventListener(
                    "click",
                    signOutRedirect
                );
            }

            document.dispatchEvent(
                new Event(
                    "authentication-ready"
                )
            );

        } catch (error) {

            console.error(
                "Authentication failed:",
                error
            );

        }
    }
);