import { requireLogin } from "/js/auth.js";


const API_BASE =
    "https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com/api";


function showError(message) {

    const error =
        document.querySelector(
            "#payment-import-summary-error"
        );

    error.textContent = message;
    error.hidden = false;
}


function getImportId() {

    const params =
        new URLSearchParams(
            window.location.search
        );

    return params.get("id");
}


async function loadSummary(user, importId) {

    const response =
        await fetch(
            `${API_BASE}/payment-imports/${importId}/summary`,
            {
                headers: {
                    Authorization:
                        `Bearer ${user.access_token}`
                }
            }
        );


    if (!response.ok) {

        let message =
            `API returned ${response.status}`;

        try {

            const data =
                await response.json();

            if (data.error) {
                message = data.error;
            }

        } catch {
            // Keep the HTTP status message.
        }

        throw new Error(message);
    }


    return response.json();
}


document.addEventListener(
    "DOMContentLoaded",
    async () => {

        try {

            const user =
                await requireLogin();

            if (!user) {
                return;
            }


            const importId =
                getImportId();


            if (!importId) {

                showError(
                    "No payment import was specified."
                );

                return;
            }


            const data =
                await loadSummary(
                    user,
                    importId
                );


            const summary =
                document.querySelector(
                    "#payment-import-summary"
                );


            summary.value =
                (data.lines || [])
                    .map(line => line.text)
                    .join("\n");

            const copyButton =
                document.querySelector(
                    "#copy-payment-import-summary"
                );


            copyButton.addEventListener(
                "click",
                async () => {

                    await navigator.clipboard.writeText(
                        summary.value
                    );

                    copyButton.textContent =
                        "Copied";

                    setTimeout(
                        () => {
                            copyButton.textContent =
                                "Copy";
                        },
                        1500
                    );
                }
            );


            const backButton =
                document.querySelector(
                    "#back-payment-import-summary"
                );


            backButton.addEventListener(
                "click",
                () => {
                    window.history.back();
                }
            );


        } catch (error) {

            console.error(error);

            showError(
                error.message ||
                "Unable to generate payment import summary."
            );
        }
    }
);