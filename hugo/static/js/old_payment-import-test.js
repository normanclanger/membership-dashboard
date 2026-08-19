import { requireLogin } from "/js/auth.js";

const button =
    document.querySelector(
        "#run-payment-import-test"
    );

const output =
    document.querySelector(
        "#payment-import-test-output"
    );

console.log(
    "Payment import test page loaded"
);

console.log(
    "Button:",
    button
);

console.log(
    "Output:",
    output
);

button.addEventListener(
    "click",
    async () => {

        output.textContent =
            "Button clicked...\n";

        try {

            const user =
                await requireLogin();

            if (!user) {

                output.textContent +=
                    "Authentication required.\n";

                return;
            }

            output.textContent +=
                "Authenticated user found.\n";

            output.textContent +=
                `Token available: ${
                    !!user.access_token
                }\n`;

            output.textContent +=
                `User groups: ${
                    JSON.stringify(
                        user.profile?.[
                            "cognito:groups"
                        ] || []
                    )
                }\n`;

        } catch (error) {

            output.textContent +=
                `ERROR: ${error.message}\n`;

            console.error(error);
        }
    }
)

