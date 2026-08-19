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

            /*
             * Determine the user's Cognito groups.
             */
            const groups =
                user.profile?.["cognito:groups"] || [];

            const userGroups =
                Array.isArray(groups)
                    ? groups
                    : [groups];

            /*
             * Determine whether the user can edit members.
             *
             * This is only for controlling the UI.
             * The API continues to enforce permissions.
             */
            window.canEditMembers =
                userGroups.some(group =>
                    [
                        "MembershipAdmin",
                        "ApplicationAdmin"
                    ].includes(group)
                );


            const signedInUser =
                document.querySelector(
                    "#signed-in-user"
                );

            if (signedInUser) {

                const email =
                    user.profile?.email ||
                    "Unknown user";

                const DISPLAY_GROUPS = [
                    "MembershipAdmin",
                    "ApplicationAdmin",
                    "PaymentAdmin",
                    "MembershipViewer"
                ];

                const displayedGroups =
                    userGroups.filter(group =>
                        DISPLAY_GROUPS.includes(group)
                    );

                const role =
                    displayedGroups.length > 0
                        ? displayedGroups.join(", ")
                        : "Read-only";

                console.log("All Cognito groups:", userGroups);
                console.log("Displayed groups:", displayedGroups);

                signedInUser.textContent =
                    `Signed in as ${email}  (${role})`;
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
