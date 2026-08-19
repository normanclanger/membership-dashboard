import { requireLogin } from "/js/auth.js";

const API_BASE =
    "https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com/api";

const button =
    document.querySelector(
        "#run-payment-import-test"
    );

const output =
    document.querySelector(
        "#payment-import-test-output"
    );

function log(message = "") {
    output.textContent +=
        message + "\n";

    output.scrollTop =
        output.scrollHeight;
}


function logJson(data) {
    log(
        JSON.stringify(
            data,
            null,
            2
        )
    );
}


async function apiCall(
    method,
    path,
    user,
    body = null
) {

    const options = {
        method,
        headers: {
            Authorization:
                `Bearer ${user.access_token}`
        }
    };

    if (body !== null) {

        options.headers[
            "Content-Type"
        ] = "application/json";

        options.body =
            JSON.stringify(body);
    }

    const response =
        await fetch(
            `${API_BASE}${path}`,
            options
        );

    const text =
        await response.text();

    let data;

    try {
        data = JSON.parse(text);
    } catch {
        data = text;
    }

    return {
        status: response.status,
        ok: response.ok,
        data
    };
}



async function runStep(
    number,
    description,
    method,
    path,
    user,
    body = null
) {

    log("");
    log(
        `========== ${number}. ${description} ==========`
    );

    log(
        `${method} ${path}`
    );

    if (body !== null) {

        log(
            JSON.stringify(
                body,
                null,
                2
            )
        );
    }

    const result =
        await apiCall(
            method,
            path,
            user,
            body
        );

    log(
        `HTTP ${result.status}`
    );

    logJson(result.data);

    if (!result.ok) {

        throw new Error(
            `Step ${number} failed: HTTP ${result.status}`
        );
    }

    log(
        `? Step ${number} passed`
    );

    return result.data;
}


button.addEventListener(
    "click",
    async () => {

        button.disabled = true;

        output.textContent = "";

        try {

            // -------------------------------------------------
            // Authentication
            // -------------------------------------------------

            log(
                "Waiting for authentication..."
            );

            const user =
                await requireLogin();

            if (!user) {

                throw new Error(
                    "Authentication required"
                );
            }

            log(
                "? Authenticated user found"
            );

            log(
                `Token available: ${
                    !!user.access_token
                }`
            );

            // -------------------------------------------------
            // 5.1 Create import
            // -------------------------------------------------

            const createdImport =
                await runStep(
                    "5.1",
                    "Create payment import",
                    "POST",
                    "/payment-imports",
                    user
                );

            const importId =
                createdImport.import.id;

            log(
                `Created import ID: ${importId}`
            );

            // -------------------------------------------------
            // 5.2 Add statement lines
            // -------------------------------------------------

            const linesBody = {
                lines: [

                    {
                        statement_reference:
                            `E2E-${importId}-001`,

                        payment_date:
                            "2026-08-19",

                        statement_amount:
                            48,

                        statement_type:
                            "CREDIT",

                        description:
                            "E2E test payment",

                        action:
                            "IMPORT"
                    },

                    {
                        statement_reference:
                            `E2E-${importId}-002`,

                        payment_date:
                            "2026-08-19",

                        statement_amount:
                            5,

                        statement_type:
                            "CREDIT",

                        description:
                            "E2E test ignored line",

                        action:
                            "IGNORE"
                    }
                ]
            };

            const addedLines =
                await runStep(
                    "5.2",
                    "Add statement lines",
                    "POST",
                    `/payment-imports/${importId}/lines`,
                    user,
                    linesBody
                );

            const paymentLine =
                addedLines.lines[0];

            const ignoredLine =
                addedLines.lines[1];

            const lineId =
                paymentLine.id;

            const ignoredLineId =
                ignoredLine.id;

            log(
                `Payment line ID: ${lineId}`
            );

            log(
                `Ignored line ID: ${ignoredLineId}`
            );

            // -------------------------------------------------
            // 5.3 Retrieve import
            // -------------------------------------------------

            await runStep(
                "5.3",
                "Retrieve payment import",
                "GET",
                `/payment-imports/${importId}`,
                user
            );

            // -------------------------------------------------
            // 5.4 Change statement-line action
            // -------------------------------------------------

            await runStep(
                "5.4",
                "Change statement-line action",
                "PATCH",
                `/payment-import-lines/${lineId}`,
                user,
                {
                    action: "IMPORT"
                }
            );

            // -------------------------------------------------
            // 5.5 Add allocation
            // -------------------------------------------------

            const firstItem =
                await runStep(
                    "5.5",
                    "Add allocation",
                    "POST",
                    `/payment-import-lines/${lineId}/items`,
                    user,
                    {
                        member_id: 1,
                        subscription_amount: 48,
                        gift_amount: 0,
                        calendar_year: 2026
                    }
                );

            let itemId =
                firstItem.item.id;

            log(
                `Allocation ID: ${itemId}`
            );

            // -------------------------------------------------
            // 5.6 Amend allocation
            // -------------------------------------------------

            await runStep(
                "5.6",
                "Amend allocation",
                "PATCH",
                `/payment-import-items/${itemId}`,
                user,
                {
                    subscription_amount: 47,
                    gift_amount: 1,
                    calendar_year: 2026
                }
            );

            // -------------------------------------------------
            // 5.7 Delete allocation
            // -------------------------------------------------

            await runStep(
                "5.7",
                "Delete allocation",
                "DELETE",
                `/payment-import-items/${itemId}`,
                user
            );

            // -------------------------------------------------
            // Re-create allocation
            // -------------------------------------------------

            const finalItem =
                await runStep(
                    "5.7b",
                    "Re-create allocation for commit test",
                    "POST",
                    `/payment-import-lines/${lineId}/items`,
                    user,
                    {
                        member_id: 1,
                        subscription_amount: 48,
                        gift_amount: 0,
                        calendar_year: 2026
                    }
                );

            itemId =
                finalItem.item.id;

            await runStep(
                "7.8",
                "Mark allocation READY",
                "PATCH",
                `/payment-import-items/${itemId}`,
                user,
                {
                    status: "READY"
                }
            );

            // -------------------------------------------------
            // 8. Commit line
            // -------------------------------------------------

            await runStep(
                "8",
                "Commit statement line",
                "POST",
                `/payment-import-lines/${lineId}/commit`,
                user
            );

            // -------------------------------------------------
            // 9. Complete import
            // -------------------------------------------------

            const completed =
                await runStep(
                    "9",
                    "Complete payment import",
                    "POST",
                    `/payment-imports/${importId}/complete`,
                    user
                );

            // -------------------------------------------------
            // Final result
            // -------------------------------------------------

            log("");
            log(
                "=================================================="
            );

            log(
                "END-TO-END TEST PASSED"
            );

            log(
                "=================================================="
            );

            log("");

            log(
                `Import ID: ${importId}`
            );

            log(
                `Import status: ${
                    completed.import.status
                }`
            );

            log(
                `Committed line: ${lineId}`
            );

            log(
                `Ignored line: ${ignoredLineId}`
            );

            log(
                `Final allocation: ${itemId}`
            );

        } catch (error) {

            log("");
            log(
                "=================================================="
            );

            log(
                "END-TO-END TEST FAILED"
            );

            log(
                "=================================================="
            );

            log("");

            log(
                error.message
            );

            console.error(error);

        } finally {

            button.disabled =
                false;
        }
    }
);
