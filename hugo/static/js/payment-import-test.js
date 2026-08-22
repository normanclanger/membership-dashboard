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


function assert(
    condition,
    message
) {

    if (!condition) {
        throw new Error(message);
    }

    log(`✓ ${message}`);
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
        `✓ Step ${number} passed`
    );

    return result.data;
}


async function runExpectedFailure(
    number,
    description,
    method,
    path,
    user,
    expectedStatus,
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

    assert(
        result.status === expectedStatus,
        `Expected HTTP ${expectedStatus}; received HTTP ${result.status}`
    );

    log(
        `✓ Expected failure received`
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
                "✓ Authenticated user found"
            );

            log(
                `Token available: ${
                    !!user.access_token
                }`
            );


            // -------------------------------------------------
            // 1. Create import
            // -------------------------------------------------

            const createdImport =
                await runStep(
                    "1",
                    "Create payment import",
                    "POST",
                    "/payment-imports",
                    user
                );

            const importId =
                createdImport.import.id;

            log(
                `Import ID: ${importId}`
            );


            // -------------------------------------------------
            // 2. Add statement lines
            // -------------------------------------------------

            const linesBody = {

                lines: [

                    // -----------------------------------------
                    // Line 1: reconciliation failure test
                    // -----------------------------------------

                    {
                        statement_reference:
                            `E2E-${importId}-001`,

                        payment_date:
                            "2026-08-19",

                        statement_amount:
                            10,

                        statement_type:
                            "CREDIT",

                        description:
                            "E2E reconciliation failure",

                        action:
                            "IMPORT"
                    },


                    // -----------------------------------------
                    // Line 2: exception -> pending -> committed
                    // -----------------------------------------

                    {
                        statement_reference:
                            `E2E-${importId}-002`,

                        payment_date:
                            "2026-08-19",

                        statement_amount:
                            20,

                        statement_type:
                            "CREDIT",

                        description:
                            "E2E exception resolution",

                        action:
                            "IMPORT"
                    },


                    // -----------------------------------------
                    // Line 3: externally resolved
                    // -----------------------------------------

                    {
                        statement_reference:
                            `E2E-${importId}-003`,

                        payment_date:
                            "2026-08-19",

                        statement_amount:
                            48,

                        statement_type:
                            "CREDIT",

                        description:
                            "E2E externally resolved allocation",

                        action:
                            "IMPORT"
                    },


                    // -----------------------------------------
                    // Ignored line
                    // -----------------------------------------

                    {
                        statement_reference:
                            `E2E-${importId}-004`,

                        payment_date:
                            "2026-08-19",

                        statement_amount:
                            5,

                        statement_type:
                            "CREDIT",

                        description:
                            "E2E ignored line",

                        action:
                            "IGNORE"
                    }
                ]
            };

            const addedLines =
                await runStep(
                    "2",
                    "Add statement lines",
                    "POST",
                    `/payment-imports/${importId}/lines`,
                    user,
                    linesBody
                );

            const line1 =
                addedLines.lines[0];

            const line2 =
                addedLines.lines[1];

            const line3 =
                addedLines.lines[2];

            const ignoredLine =
                addedLines.lines[3];

            const line1Id =
                line1.id;

            const line2Id =
                line2.id;

            const line3Id =
                line3.id;

            const ignoredLineId =
                ignoredLine.id;


            // =================================================
            // LINE 1
            // PENDING allocation which does NOT reconcile
            // =================================================

            // -------------------------------------------------
            // 3. Add £9 PENDING allocation to £10 line
            // -------------------------------------------------

            const line1Item =
                await runStep(
                    "3",
                    "Add £9 PENDING allocation to £10 line",
                    "POST",
                    `/payment-import-lines/${line1Id}/items`,
                    user,
                    {
                        member_id: 1,
                        subscription_amount: 9,
                        gift_amount: 0,
                        calendar_year: 2026
                    }
                );

            const line1ItemId =
                line1Item.item.id;


            // -------------------------------------------------
            // 4. Attempt to commit unreconciled line
            // -------------------------------------------------

            const failedCommit =
                await runExpectedFailure(
                    "4",
                    "Reject commit because PENDING allocation does not reconcile",
                    "POST",
                    `/payment-import-lines/${line1Id}/commit`,
                    user,
                    400
                );

            assert(
                failedCommit.error,
                "Unreconciled line was rejected"
            );


            // -------------------------------------------------
            // 5. Amend £9 -> £10
            // -------------------------------------------------

            const amendedLine1Item =
                await runStep(
                    "5",
                    "Amend PENDING allocation to £10",
                    "PATCH",
                    `/payment-import-items/${line1ItemId}`,
                    user,
                    {
                        subscription_amount: 10
                    }
                );

            assert(
                amendedLine1Item.item.status === "PENDING",
                "Allocation remains PENDING after amendment"
            );


            // -------------------------------------------------
            // 6. Commit reconciled line
            // -------------------------------------------------

            const committedLine1 =
                await runStep(
                    "6",
                    "Commit reconciled PENDING allocation",
                    "POST",
                    `/payment-import-lines/${line1Id}/commit`,
                    user
                );

            assert(
                committedLine1.line.status === "COMMITTED",
                "Line 1 became COMMITTED"
            );

            assert(
                committedLine1.payments_created.length === 1,
                "Exactly one payment was created for Line 1"
            );

            assert(
                committedLine1.payments_created[0].import_item_id
                    === line1ItemId,
                "Created payment belongs to Line 1 allocation"
            );


            // =================================================
            // LINE 2
            // PENDING + EXCEPTION
            // =================================================

            // -------------------------------------------------
            // 7. Add £10 PENDING
            // -------------------------------------------------

            const line2Pending =
                await runStep(
                    "7",
                    "Add £10 PENDING allocation",
                    "POST",
                    `/payment-import-lines/${line2Id}/items`,
                    user,
                    {
                        member_id: 1,
                        subscription_amount: 10,
                        gift_amount: 0,
                        calendar_year: 2026
                    }
                );

            const line2PendingId =
                line2Pending.item.id;


            // -------------------------------------------------
            // 8. Add £10 EXCEPTION
            // -------------------------------------------------

            const line2Exception =
                await runStep(
                    "8",
                    "Add £10 EXCEPTION allocation",
                    "POST",
                    `/payment-import-lines/${line2Id}/items`,
                    user,
                    {
                        member_id: null,
                        subscription_amount: 10,
                        gift_amount: 0,
                        calendar_year: 2026,
                        status: "EXCEPTION",
                        exception_reason:
                            "E2E test exception"
                    }
                );

            const line2ExceptionId =
                line2Exception.item.id;

            assert(
                line2Exception.item.status === "EXCEPTION",
                "Allocation is EXCEPTION"
            );


            // -------------------------------------------------
            // 9. Commit line with open exception
            // -------------------------------------------------

            const partialLine =
                await runStep(
                    "9",
                    "Commit PENDING allocation while exception remains open",
                    "POST",
                    `/payment-import-lines/${line2Id}/commit`,
                    user
                );

            assert(
                partialLine.line.status
                    === "PARTIALLY_COMMITTED",
                "Line 2 became PARTIALLY_COMMITTED"
            );

            assert(
                partialLine.payments_created.length === 1,
                "Exactly one payment was created for the PENDING allocation"
            );

            assert(
                partialLine.exception_item_ids.includes(
                    line2ExceptionId
                ),
                "Open exception remains identified"
            );

            // -------------------------------------------------
            // 9. Commit line with open exception
            // -------------------------------------------------

            const partialImport =
                await runStep(
                    "9.1",
                    "Check parent import after partial commit",
                    "GET",
                    `/payment-imports/${importId}`,
                    user
                );

           assert(
              partialImport.import.status === "IN_PROGRESS",
               "Parent import remains IN_PROGRESS while exceptions are open"
              );


            // -------------------------------------------------
            // 10. Change EXCEPTION -> PENDING
            // -------------------------------------------------

            const resolvedToPending =
                await runStep(
                    "10",
                    "Change EXCEPTION to PENDING",
                    "PATCH",
                    `/payment-import-items/${line2ExceptionId}`,
                    user,
                    {
                        status: "PENDING",
                        member_id: 1
                    }
                );

            assert(
                resolvedToPending.item.status === "PENDING",
                "Exception changed to PENDING"
            );


            // -------------------------------------------------
            // 11. Commit the newly PENDING allocation
            // -------------------------------------------------

            const completedLine2 =
                await runStep(
                    "11",
                    "Commit newly PENDING allocation",
                    "POST",
                    `/payment-import-lines/${line2Id}/commit`,
                    user
                );

            assert(
                completedLine2.line.status === "COMMITTED",
                "Line 2 became COMMITTED"
            );

            assert(
                completedLine2.payments_created.length === 1,
                "Exactly one payment was created for the newly PENDING allocation"
            );

            assert(
                completedLine2.payments_created[0].import_item_id
                    === line2ExceptionId,
                "New payment belongs to the formerly exceptional allocation"
            );


            // =================================================
            // LINE 3
            // PENDING + EXCEPTION + RESOLVED_EXTERNALLY
            // =================================================

            // The £48 statement will contain:
            //
            // PENDING               £28
            // EXCEPTION             £12
            // RESOLVED_EXTERNALLY    £8
            //                         ---
            //                       £48
            //
            // All three statuses therefore count towards
            // reconciliation.
            // -------------------------------------------------


            // -------------------------------------------------
            // 12. Add £28 PENDING
            // -------------------------------------------------

            const line3Pending =
                await runStep(
                    "12",
                    "Add £28 PENDING allocation",
                    "POST",
                    `/payment-import-lines/${line3Id}/items`,
                    user,
                    {
                        member_id: 1,
                        subscription_amount: 28,
                        gift_amount: 0,
                        calendar_year: 2026
                    }
                );

            const line3PendingId =
                line3Pending.item.id;


            // -------------------------------------------------
            // 13. Add £12 EXCEPTION
            // -------------------------------------------------

            const line3Exception =
                await runStep(
                    "13",
                    "Add £12 EXCEPTION allocation",
                    "POST",
                    `/payment-import-lines/${line3Id}/items`,
                    user,
                    {
                        member_id: null,
                        subscription_amount: 12,
                        gift_amount: 0,
                        calendar_year: 2026,
                        status: "EXCEPTION",
                        exception_reason:
                            "E2E external resolution test"
                    }
                );

            const line3ExceptionId =
                line3Exception.item.id;


            // -------------------------------------------------
            // 14. Add £8 RESOLVED_EXTERNALLY
            // -------------------------------------------------

            const line3External =
                await runStep(
                    "14",
                    "Add £8 RESOLVED_EXTERNALLY allocation",
                    "POST",
                    `/payment-import-lines/${line3Id}/items`,
                    user,
                    {
                        member_id: null,
                        subscription_amount: 8,
                        gift_amount: 0,
                        calendar_year: 2026,
                        status: "RESOLVED_EXTERNALLY",
                        exception_reason:
                            "Resolved outside payment system"
                    }
                );

            const line3ExternalId =
                line3External.item.id;

            assert(
                line3External.item.status
                    === "RESOLVED_EXTERNALLY",
                "Allocation is RESOLVED_EXTERNALLY"
            );


            // -------------------------------------------------
            // 15. Commit reconciled line with exception
            // -------------------------------------------------

            const partialLine3 =
                await runStep(
                    "15",
                    "Commit Line 3 with PENDING, EXCEPTION and RESOLVED_EXTERNALLY",
                    "POST",
                    `/payment-import-lines/${line3Id}/commit`,
                    user
                );

            assert(
                partialLine3.line.status
                    === "PARTIALLY_COMMITTED",
                "Line 3 became PARTIALLY_COMMITTED"
            );

            assert(
                partialLine3.payments_created.length === 1,
                "Only the PENDING allocation created a payment"
            );

            assert(
                partialLine3.payments_created[0].import_item_id
                    === line3PendingId,
                "Created payment belongs only to the PENDING allocation"
            );

            assert(
                partialLine3.exception_item_ids.includes(
                    line3ExceptionId
                ),
                "Line 3 exception remains open"
            );

            assert(
                partialLine3.externally_resolved_item_ids.includes(
                    line3ExternalId
                ),
                "RESOLVED_EXTERNALLY allocation remains identified"
            );


            // -------------------------------------------------
            // 16. Change EXCEPTION -> RESOLVED_EXTERNALLY
            // -------------------------------------------------

            const externallyResolved =
                await runStep(
                    "16",
                    "Resolve remaining exception externally",
                    "PATCH",
                    `/payment-import-items/${line3ExceptionId}`,
                    user,
                    {
                        status: "RESOLVED_EXTERNALLY",
                        exception_reason:
                            "Confirmed externally"
                    }
                );

            assert(
                externallyResolved.item.status
                    === "RESOLVED_EXTERNALLY",
                "Exception changed to RESOLVED_EXTERNALLY"
            );


            // -------------------------------------------------
            // 17. Commit Line 3 again
            // -------------------------------------------------

            const completedLine3 =
                await runStep(
                    "17",
                    "Complete Line 3 after external resolution",
                    "POST",
                    `/payment-import-lines/${line3Id}/commit`,
                    user
                );

            assert(
                completedLine3.line.status
                    === "COMMITTED",
                "Line 3 became COMMITTED"
            );

            assert(
                completedLine3.payments_created.length === 0,
                "No additional payment was created for RESOLVED_EXTERNALLY"
            );

            assert(
                completedLine3.externally_resolved_item_ids.includes(
                    line3ExceptionId
                ),
                "Resolved exception remains RESOLVED_EXTERNALLY"
            );


            // =================================================
            // IMPORT COMPLETION
            // =================================================

            // -------------------------------------------------
            // 18. Complete import
            // -------------------------------------------------

            const completed =
                await runStep(
                    "18",
                    "Complete payment import",
                    "POST",
                    `/payment-imports/${importId}/complete`,
                    user
                );

            assert(
                completed.import.status === "COMPLETE",
                "Import became COMPLETE"
            );


            // -------------------------------------------------
            // Final result
            // -------------------------------------------------

            log("");
            log(
                "=================================================="
            );

            log(
                "END-TO-END PAYMENT IMPORT TEST PASSED"
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
                `Line 1: ${line1Id} - committed after reconciliation`
            );

            log(
                `Line 2: ${line2Id} - exception -> pending -> committed`
            );

            log(
                `Line 3: ${line3Id} - externally resolved`
            );

            log(
                `Ignored line: ${ignoredLineId}`
            );

            log("");

            log(
                "Tested:"
            );

            log(
                "  ✓ Unreconciled PENDING allocation is rejected"
            );

            log(
                "  ✓ Reconciled PENDING allocation creates a payment"
            );

            log(
                "  ✓ PENDING allocation becomes COMMITTED"
            );

            log(
                "  ✓ EXCEPTION does not create a payment"
            );

            log(
                "  ✓ Open exception produces PARTIALLY_COMMITTED"
            );

            log(
                "  ✓ EXCEPTION can become PENDING"
            );

            log(
                "  ✓ PENDING exception can subsequently become COMMITTED"
            );

            log(
                "  ✓ RESOLVED_EXTERNALLY remains RESOLVED_EXTERNALLY"
            );

            log(
                "  ✓ RESOLVED_EXTERNALLY does not create a payment"
            );

            log(
                "  ✓ RESOLVED_EXTERNALLY counts towards reconciliation"
            );

            log(
                "  ✓ Fully resolved import can become COMPLETE"
            );

        } catch (error) {

            log("");
            log(
                "=================================================="
            );

            log(
                "END-TO-END PAYMENT IMPORT TEST FAILED"
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