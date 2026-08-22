function userHasGroup(groupName) {

    const groups =
        window.currentUser?.profile?.[
            "cognito:groups"
        ] || [];

    const userGroups =
        Array.isArray(groups)
            ? groups
            : [groups];

    return userGroups.includes(groupName);
}


document.addEventListener(
    "authentication-ready",
    async () => {

        const params =
            new URLSearchParams(
                window.location.search
            );

        const importId =
            params.get("id");

        const error =
            document.querySelector(
                "#payment-import-error"
            );


        if (!importId) {

            error.textContent =
                "No payment import ID was supplied.";

            error.hidden = false;

            return;
        }


        try {

            const user =
                window.currentUser;

            if (
                !user ||
                !user.access_token
            ) {

                throw new Error(
                    "No authenticated user"
                );
            }


            console.log(
                "Import ID:",
                JSON.stringify(importId)
            );

            console.log(
                "Payment import API URL:",
                `https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com/api/payment-imports/${importId}`
            );


            const response =
                await fetch(
                    `https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com/api/payment-imports/${importId}`,
                    {
                        headers: {
                            Authorization:
                                `Bearer ${user.access_token}`
                        }
                    }
                );


            if (!response.ok) {

                throw new Error(
                    `HTTP ${response.status}`
                );
            }


            const data =
                await response.json();


            const paymentImport =
                data.import;

            const lines =
                data.lines || [];


            /*
             * Import details
             */

            document.querySelector(
                "#payment-import-detail"
            ).innerHTML = `

                <tr>
                    <th>Import</th>
                    <td>#${paymentImport.id}</td>
                </tr>

                <tr>
                    <th>Created</th>
                    <td>
                        ${paymentImport.created_at
                            ? new Date(
                                paymentImport.created_at
                              ).toLocaleDateString(
                                "en-GB"
                              )
                            : "-"
                        }
                    </td>
                </tr>

                <tr>
                    <th>Created by</th>
                    <td>
                        ${paymentImport.created_by || "-"}
                    </td>
                </tr>

                <tr>
                    <th>Status</th>
                    <td>
                        ${paymentImport.status || "-"}
                    </td>
                </tr>

            `;


            /*
             * Statement lines
             */

            const linesBody =
                document.querySelector(
                    "#payment-import-lines-body"
                );


            if (lines.length === 0) {

                linesBody.innerHTML = `
                    <tr>
                        <td colspan="6">
                            No statement lines found.
                        </td>
                    </tr>
                `;

                return;
            }


            linesBody.innerHTML =
                lines.map(line => {

                    const items =
                        line.items || [];


                    /*
                     * Allocation totals
                     */

                    const statementAmount =
                        parseFloat(
                            line.statement_amount || 0
                        );


                    const allocatedAmount =
                        items.reduce(
                            (total, item) =>
                                total +
                                parseFloat(
                                    item.subscription_amount || 0
                                ) +
                                parseFloat(
                                    item.gift_amount || 0
                                ),
                            0
                        );


                    const outstandingAmount =
                        statementAmount -
                        allocatedAmount;


                    /*
                     * Allocation summary
                     */

                    const allocationSummary =
                        line.action === "IMPORT"

                            ? (() => {

                                let statusText;
                                let statusClass;


                                if (
                                    Math.abs(
                                        outstandingAmount
                                    ) < 0.005
                                ) {

                                    statusText =
                                        "✓ Ready";

                                    statusClass =
                                        "text-success";

                                } else if (
                                    outstandingAmount > 0
                                ) {

                                    statusText =
                                        "⚠ Allocation required";

                                    statusClass =
                                        "text-warning";

                                } else {

                                    statusText =
                                        "⚠ Over-allocated";

                                    statusClass =
                                        "text-danger";
                                }


                                const allocationButton =
                                    outstandingAmount > 0.005

                                        ? `
                                            <button
                                                type="button"
                                                class="btn btn-primary btn-sm"
                                                data-action="add-allocation"
                                                data-line-id="${line.id}"
                                            >
                                                Add allocation
                                            </button>
                                          `

                                        : "";


                                return `

                                    <div
                                        class="
                                            payment-line-summary
                                            d-flex
                                            gap-4
                                            align-items-center
                                            py-2
                                            px-2
                                        "
                                    >

                                        <span>
                                            Allocated:
                                            <strong>
                                                £${allocatedAmount.toFixed(2)}
                                            </strong>
                                        </span>

                                        <span>
                                            Outstanding:
                                            <strong>
                                                £${outstandingAmount.toFixed(2)}
                                            </strong>
                                        </span>

                                        <span
                                            class="${statusClass}"
                                        >
                                            <strong>
                                                ${statusText}
                                            </strong>
                                        </span>

                                        ${allocationButton}

                                    </div>

                                `;

                            })()

                            : `
                                <div
                                    class="
                                        payment-line-summary
                                        py-2
                                        px-2
                                        text-muted
                                    "
                                >
                                    Ignored — no allocation required
                                </div>
                            `;


                    /*
                     * Existing allocations
                     */

                    let allocationContent;


                    if (items.length === 0) {

                        allocationContent = `
                            <div class="text-muted py-2">
                                No allocations
                            </div>
                        `;

                    } else {

                        allocationContent = `

                            <details
                                class="payment-allocation-details"
                            >

                                <summary
                                    class="fw-semibold"
                                >
                                    Allocations (${items.length})
                                </summary>

                                <div
                                    class="
                                        table-responsive
                                        mt-2
                                        ms-3
                                    "
                                >

                                    <table
                                        class="
                                            table
                                            table-sm
                                            table-bordered
                                            mb-2
                                        "
                                    >

                                        <thead>

                                            <tr>

                                                <th>
                                                    Member
                                                </th>

                                                <th>
                                                    Subscription
                                                </th>

                                                <th>
                                                    Gift
                                                </th>

                                                <th>
                                                    Year
                                                </th>

                                                <th>
                                                    Status
                                                </th>

                                                <th>
                                                    Exception
                                                </th>

                                            </tr>

                                        </thead>


                                        <tbody>

                                            ${items.map(
                                                item => `

                                                    <tr>

                                                        <td>
                                                            Member #${item.member_id}
                                                        </td>

                                                        <td>
                                                            £${item.subscription_amount || "0.00"}
                                                        </td>

                                                        <td>
                                                            £${item.gift_amount || "0.00"}
                                                        </td>

                                                        <td>
                                                            ${item.calendar_year || "-"}
                                                        </td>

                                                        <td>
                                                            ${item.status || "-"}
                                                        </td>

                                                        <td>
                                                            ${item.exception_reason || ""}
                                                        </td>

                                                    </tr>

                                                `
                                            ).join("")}

                                        </tbody>

                                    </table>

                                </div>

                            </details>

                        `;
                    }


                    /*
                     * Statement line
                     */

                    return `

                        <tr>

                            <td>
                                ${line.statement_reference || "-"}
                            </td>

                            <td>
                                ${line.payment_date || "-"}
                            </td>

                            <td>
                                £${line.statement_amount || "0.00"}
                            </td>

                            <td>
                                ${line.statement_type || "-"}
                            </td>

                            <td>
                                ${line.description || "-"}
                            </td>

                            <td>
                                ${line.action || "-"}
                            </td>

                        </tr>


                        <tr>

                            <td
                                colspan="6"
                                class="payment-allocation-cell"
                            >

                                ${allocationSummary}

                                ${allocationContent}

                            </td>

                        </tr>

                    `;

                }).join("");


            /*
             * Add allocation button
             */

            linesBody.addEventListener(
                "click",
                event => {

                    const button =
                        event.target.closest(
                            '[data-action="add-allocation"]'
                        );


                    if (!button) {
                        return;
                    }


                    /*
                     * MembershipViewer check
                     */

                    if (
                        !userHasGroup(
                            "MembershipViewer"
                        )
                    ) {

                        error.textContent =
                            "Member lookup is unavailable. " +
                            "Your account has PaymentAdmin access " +
                            "but does not have MembershipViewer access. " +
                            "Please contact an administrator.";

                        error.hidden = false;

                        return;
                    }


                    const lineId =
                        button.dataset.lineId;


                    /*
                     * Don't create two forms
                     */

                    const existingForm =
                        linesBody.querySelector(
                            `[data-allocation-form="${lineId}"]`
                        );


                    if (existingForm) {
                        return;
                    }


                    /*
                     * Create allocation form
                     */

                    const formRow =
                        document.createElement("tr");


                    formRow.dataset.allocationForm =
                        lineId;


                    formRow.innerHTML = `

                        <td
                            colspan="6"
                            class="bg-light"
                        >

                            <div class="p-3">

                                <h5>
                                    Add allocation
                                </h5>


                                <div class="mb-3">

                                    <label
                                        class="form-label"
                                        for="allocation-member-${lineId}"
                                    >
                                        Member
                                    </label>


                                    <input
                                        type="text"
                                        class="form-control"
                                        id="allocation-member-${lineId}"
                                        placeholder="Search by membership number, first name or surname..."
                                        autocomplete="off"
                                    >


                                    <div
                                        id="allocation-member-results-${lineId}"
                                        class="list-group mt-2"
                                        hidden
                                    >
                                    </div>


                                    <input
                                        type="hidden"
                                        id="allocation-member-id-${lineId}"
                                    >

                                </div>


                                <div
                                    id="allocation-payment-history-${lineId}"
                                    class="mt-3"
                                    hidden
                                >
                                </div>


                                <div class="row g-3">

                                    <div class="col-md-4">

                                        <label
                                            class="form-label"
                                            for="allocation-subscription-${lineId}"
                                        >
                                            Subscription
                                        </label>

                                        <input
                                            type="number"
                                            class="form-control"
                                            id="allocation-subscription-${lineId}"
                                            value="0.00"
                                            min="0"
                                            step="0.01"
                                        >

                                    </div>


                                    <div class="col-md-4">

                                        <label
                                            class="form-label"
                                            for="allocation-gift-${lineId}"
                                        >
                                            Gift
                                        </label>

                                        <input
                                            type="number"
                                            class="form-control"
                                            id="allocation-gift-${lineId}"
                                            value="0.00"
                                            min="0"
                                            step="0.01"
                                        >

                                    </div>


                                    <div class="col-md-4">

                                        <label
                                            class="form-label"
                                            for="allocation-year-${lineId}"
                                        >
                                            Calendar year
                                        </label>

                                        <input
                                            type="number"
                                            class="form-control"
                                            id="allocation-year-${lineId}"
                                            value="${new Date().getFullYear()}"
                                        >

                                    </div>

                                </div>


                                <div class="mt-3">

                                    <button
                                        type="button"
                                        class="btn btn-primary btn-sm"
                                        data-action="save-allocation"
                                        data-line-id="${lineId}"
                                    >
                                        Save allocation
                                    </button>


                                    <button
                                        type="button"
                                        class="btn btn-secondary btn-sm"
                                        data-action="cancel-allocation"
                                        data-line-id="${lineId}"
                                    >
                                        Cancel
                                    </button>

                                </div>

                            </div>

                        </td>

                    `;


                    button
                        .closest("tr")
                        .after(formRow);


                    /*
                     * Member search controls
                     */

                    const memberInput =
                        document.querySelector(
                            `#allocation-member-${lineId}`
                        );


                    const memberResults =
                        document.querySelector(
                            `#allocation-member-results-${lineId}`
                        );


                    const memberIdInput =
                        document.querySelector(
                            `#allocation-member-id-${lineId}`
                        );


                    let searchTimeout;


                    /*
                     * Member search
                     */

                    memberInput.addEventListener(
                        "input",
                        () => {

                            clearTimeout(
                                searchTimeout
                            );


                            const search =
                                memberInput.value.trim();


                            memberIdInput.value =
                                "";


                            if (
                                search.length < 2
                            ) {

                                memberResults.innerHTML =
                                    "";

                                memberResults.hidden =
                                    true;

                                return;
                            }


                            searchTimeout =
                                setTimeout(
                                    async () => {

                                        try {

                                            const response =
                                                await fetch(
                                                    "https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com" +
                                                    `/api/members?search=${encodeURIComponent(search)}`,
                                                    {
                                                        headers: {
                                                            Authorization:
                                                                `Bearer ${user.access_token}`
                                                        }
                                                    }
                                                );


                                            if (!response.ok) {

                                                throw new Error(
                                                    `HTTP ${response.status}`
                                                );
                                            }


                                            const data =
                                                await response.json();


                                            const members =
                                                data.members || [];


                                            if (
                                                members.length === 0
                                            ) {

                                                memberResults.innerHTML = `

                                                    <div
                                                        class="
                                                            list-group-item
                                                            text-muted
                                                        "
                                                    >
                                                        No members found
                                                    </div>

                                                `;

                                                memberResults.hidden =
                                                    false;

                                                return;
                                            }


                                            memberResults.innerHTML =
                                                members.map(
                                                    member => `

                                                        <button
                                                            type="button"
                                                            class="
                                                                list-group-item
                                                                list-group-item-action
                                                            "
                                                            data-member-id="${member.id}"
                                                            data-member-name="${member.first_name} ${member.surname}"
                                                            data-membership-number="${member.membership_number}"
                                                        >

                                                            <strong>
                                                                ${member.membership_number}
                                                            </strong>

                                                            —
                                                            ${member.first_name}
                                                            ${member.surname}

                                                            ${
                                                                  member.tower?.name
                                                                      ? ` — ${member.tower.name}`
                                                                      : ""
                                                              }

                                                        </button>

                                                    `
                                                ).join("");


                                            memberResults.hidden =
                                                false;


                                        } catch (err) {

                                            console.error(
                                                "Member search failed:",
                                                err
                                            );


                                            memberResults.innerHTML = `

                                                <div
                                                    class="
                                                        list-group-item
                                                        text-danger
                                                    "
                                                >
                                                    Unable to search for members
                                                </div>

                                            `;


                                            memberResults.hidden =
                                                false;
                                        }

                                    },
                                    300
                                );

                        }
                    );


                    /*
                     * Member selection
                     */



                   memberResults.addEventListener(
                       "click",
                       async event => {

                           const selected =
                               event.target.closest(
                                   "[data-member-id]"
                               );

                           if (!selected) {
                               return;
                           }

                           const memberId =
                               selected.dataset.memberId;

                           const memberName =
                               selected.dataset.memberName;

                           const membershipNumber =
                               selected.dataset.membershipNumber;

                           /*
                            * Set selected member
                            */

                           memberIdInput.value =
                               memberId;

                           memberInput.value =
                               `${membershipNumber} — ${memberName}`;

                           memberResults.innerHTML =
                               "";

                           memberResults.hidden =
                               true;


                           /*
                            * Load payment history
                            */

                           const paymentHistory =
                               document.querySelector(
                                   `#allocation-payment-history-${lineId}`
                               );

                           paymentHistory.hidden = false;

                           paymentHistory.innerHTML = `
                               <div class="text-muted">
                                   Loading payment history...
                               </div>
                           `;


                           try {

                               const response =
                                   await fetch(
                                       "https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com" +
                                       `/api/members/${memberId}/payment-history`,
                                       {
                                           headers: {
                                               Authorization:
                                                   `Bearer ${user.access_token}`
                                           }
                                       }
                                   );


                               if (!response.ok) {

                                   throw new Error(
                                       `HTTP ${response.status}`
                                   );
                               }


                               const data =
                                   await response.json();

                               const payments =
                                   data.payments || [];


                               /*
                                * No payment history
                                */

                               if (payments.length === 0) {

                                   paymentHistory.innerHTML = `

                                       <div
                                           class="alert alert-info mb-0"
                                       >
                                           <strong>
                                               No previous payments found
                                           </strong>
                                           <br>
                                           This appears to be the member's
                                           first recorded payment.
                                       </div>

                                   `;

                                   return;
                               }


                               /*
                                * Display payment history
                                */

                               paymentHistory.innerHTML = `

                                   <div class="card">

                                       <div class="card-header">

                                           <strong>
                                               Payment history
                                           </strong>

                                           —
                                           ${membershipNumber}
                                           ${memberName}

                                       </div>


                                       <div class="card-body p-0">

                                           <div class="table-responsive">

                                               <table
                                                   class="
                                                       table
                                                       table-sm
                                                       table-bordered
                                                       mb-0
                                                   "
                                               >

                                                   <thead>

                                                       <tr>

                                                           <th>
                                                               Payment date
                                                           </th>

                                                           <th>
                                                               Calendar year
                                                           </th>

                                                           <th>
                                                               Subscription
                                                           </th>

                                                           <th>
                                                               Gift
                                                           </th>

                                                           <th>
                                                               Total
                                                           </th>

                                                           <th>
                                                               Reference
                                                           </th>

                                                       </tr>

                                                   </thead>


                                                   <tbody>

                                                       ${payments.map(
                                                           payment => {

                                                               const subscription =
                                                                   parseFloat(
                                                                       payment.subscription_amount || 0
                                                                   );

                                                               const gift =
                                                                   parseFloat(
                                                                       payment.gift_amount || 0
                                                                   );

                                                               const total =
                                                                   subscription +
                                                                   gift;

                                                               return `

                                                                   <tr>

                                                                       <td>
                                                                           ${
                                                                               payment.payment_date
                                                                                   ? new Date(
                                                                                       payment.payment_date +
                                                                                       "T00:00:00"
                                                                                     ).toLocaleDateString(
                                                                                       "en-GB"
                                                                                     )
                                                                                   : "-"
                                                                           }
                                                                       </td>

                                                                       <td>
                                                                           <strong>
                                                                               ${
                                                                                   payment.calendar_year ||
                                                                                   "-"
                                                                               }
                                                                           </strong>
                                                                       </td>

                                                                       <td>
                                                                           £${subscription.toFixed(2)}
                                                                       </td>

                                                                       <td>
                                                                           £${gift.toFixed(2)}
                                                                       </td>

                                                                       <td>
                                                                           <strong>
                                                                               £${total.toFixed(2)}
                                                                           </strong>
                                                                       </td>

                                                                       <td>
                                                                           ${
                                                                               payment.statement_reference ||
                                                                               "-"
                                                                           }
                                                                       </td>

                                                                   </tr>

                                                               `;
                                                           }
                                                       ).join("")}

                                                   </tbody>

                                               </table>

                                           </div>

                                       </div>

                                   </div>

                               `;


                               console.log(
                                   "Payment history loaded:",
                                   memberId,
                                   payments
                               );


                           } catch (err) {

                               console.error(
                                   "Payment history failed:",
                                   err
                               );

                               paymentHistory.innerHTML = `

                                   <div
                                       class="alert alert-danger mb-0"
                                   >
                                       Unable to load payment history.
                                   </div>

                               `;
                           }

                       }
                   );

                }
            );


        } catch (err) {

            console.error(err);


            error.textContent =
                "Unable to load payment import.";


            error.hidden =
                false;
        }

    }
);