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


            const apiBase =
                "https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com";


            console.log(
                "Import ID:",
                JSON.stringify(importId)
            );

            console.log(
                "Payment import API URL:",
                `${apiBase}/api/payment-imports/${importId}`
            );


            const response =
                await fetch(
                    `${apiBase}/api/payment-imports/${importId}`,
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
                        ${
                            paymentImport.created_at
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
                     *
                     * RESOLVED_EXTERNALLY items do not
                     * count towards reconciliation.
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

                                const hasOpenException =
                                    items.some(
                                        item =>
                                            item.status === "EXCEPTION"
                                    );


                                if (
                                   outstandingAmount < -0.005
                                   ) {

                                       statusText =
                                           "⚠ Over-allocated";

                                       statusClass =
                                           "text-danger";

                                   } else if (
                                       hasOpenException
                                   ) {

                                       statusText =
                                           "⚠ Open exception";

                                       statusClass =
                                           "text-warning";

                                   } else if (
                                       outstandingAmount > 0.005
                                   ) {

                                       statusText =
                                           "⚠ Allocation required";

                                       statusClass =
                                           "text-warning";

                                   } else {

                                       statusText =
                                           "✓ Ready";

                                       statusClass =
                                           "text-success";
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

                                                <th>
                                                    Actions
                                                </th>

                                            </tr>

                                        </thead>


                                        <tbody>

                                            ${items.map(
                                                item => {

                                                    const
                                                        memberDisplay =
                                                        item.member_id
                                                            ? `Member #${item.member_id}`
                                                            : "No member";


                                                    const
                                                        statusDisplay =
                                                        item.status ||
                                                        "-";


                                                    return `

                                                        <tr>

                                                            <td>
                                                                ${memberDisplay}
                                                            </td>

                                                            <td>
                                                                £${parseFloat(
                                                                    item.subscription_amount ||
                                                                    0
                                                                ).toFixed(2)}
                                                            </td>

                                                            <td>
                                                                £${parseFloat(
                                                                    item.gift_amount ||
                                                                    0
                                                                ).toFixed(2)}
                                                            </td>

                                                            <td>
                                                                ${item.calendar_year || "-"}
                                                            </td>

                                                            <td>
                                                                ${statusDisplay}
                                                            </td>

                                                            <td>
                                                                ${item.exception_reason || ""}
                                                            </td>


                                                            <td>

                                                                ${
                                                                    item.status !== "COMMITTED"

                                                                        ? `

                                                                            <button
                                                                                type="button"
                                                                                class="btn btn-outline-primary btn-sm"
                                                                                data-action="amend-allocation"
                                                                                data-item-id="${item.id}"
                                                                                data-line-id="${line.id}"
                                                                            >
                                                                                Amend
                                                                            </button>

                                                                            <button
                                                                                type="button"
                                                                                class="btn btn-outline-danger btn-sm"
                                                                                data-action="delete-allocation"
                                                                                data-item-id="${item.id}"
                                                                                data-line-id="${line.id}"
                                                                            >
                                                                                Delete
                                                                            </button>

                                                                        `

                                                                        : `
                                                                            <span class="text-muted">
                                                                                Committed
                                                                            </span>
                                                                        `
                                                                }

                                                            </td> 


                                                        </tr>

                                                    `;

                                                }
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
                                £${parseFloat(
                                    line.statement_amount || 0
                                ).toFixed(2)}
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
             * Allocation controls
             */

            linesBody.addEventListener(
                "click",
                async event => {

                    /*
                     * Add allocation
                     */

                    const addButton =
                        event.target.closest(
                            '[data-action="add-allocation"]'
                        );


                    if (addButton) {

                        const lineId =
                            addButton.dataset.lineId;


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

                                        <div
                                            class="form-text"
                                        >
                                            A member is required for Pending
                                            allocations. It is not required
                                            for Exception or Resolved externally.
                                        </div>

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


                                    <div class="row g-3 mt-1">

                                        <div class="col-md-4">

                                            <label
                                                class="form-label"
                                                for="allocation-status-${lineId}"
                                            >
                                                Status
                                            </label>

                                            <select
                                                class="form-select"
                                                id="allocation-status-${lineId}"
                                            >

                                                <option
                                                    value="PENDING"
                                                    selected
                                                >
                                                    Pending
                                                </option>

                                                <option
                                                    value="EXCEPTION"
                                                >
                                                    Exception
                                                </option>

                                                <option
                                                    value="RESOLVED_EXTERNALLY"
                                                >
                                                    Resolved externally
                                                </option>

                                            </select>

                                        </div>

                                    </div>


                                    <div
                                        id="allocation-exception-container-${lineId}"
                                        class="mt-3"
                                        hidden
                                    >

                                        <label
                                            class="form-label"
                                            for="allocation-exception-${lineId}"
                                        >
                                            Exception details
                                        </label>

                                        <textarea
                                            class="form-control"
                                            id="allocation-exception-${lineId}"
                                            rows="3"
                                            placeholder="Enter details explaining the exception or external resolution..."
                                        ></textarea>

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


                        addButton
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


                                /*
                                 * Member search requires
                                 * MembershipViewer.
                                 *
                                 * Exception and Resolved
                                 * externally can still be
                                 * saved without a member.
                                 */

                                if (
                                    !userHasGroup(
                                        "MembershipViewer"
                                    )
                                ) {

                                    memberResults.innerHTML = `

                                        <div
                                            class="
                                                list-group-item
                                                text-warning
                                            "
                                        >
                                            Member lookup is unavailable.
                                            Your account has PaymentAdmin
                                            access but does not have
                                            MembershipViewer access.
                                        </div>

                                    `;

                                    memberResults.hidden =
                                        false;

                                    return;
                                }


                                searchTimeout =
                                    setTimeout(
                                        async () => {

                                            try {

                                                const response =
                                                    await fetch(
                                                        `${apiBase}/api/members?search=${encodeURIComponent(search)}`,
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


                                paymentHistory.hidden =
                                    false;


                                paymentHistory.innerHTML = `
                                    <div class="text-muted">
                                        Loading payment history...
                                    </div>
                                `;


                                try {

                                    const response =
                                        await fetch(
                                            `${apiBase}/api/members/${memberId}/payment-history`,
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

                                    if (
                                        payments.length === 0
                                    ) {

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

                                                                    const
                                                                        subscription =
                                                                        parseFloat(
                                                                            payment.subscription_amount ||
                                                                            0
                                                                        );

                                                                    const
                                                                        gift =
                                                                        parseFloat(
                                                                            payment.gift_amount ||
                                                                            0
                                                                        );

                                                                    const
                                                                        total =
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


                        /*
                         * Allocation status controls
                         */

                        const statusSelect =
                            document.querySelector(
                                `#allocation-status-${lineId}`
                            );


                        const exceptionContainer =
                            document.querySelector(
                                `#allocation-exception-container-${lineId}`
                            );


                        const exceptionInput =
                            document.querySelector(
                                `#allocation-exception-${lineId}`
                            );


                        function updateExceptionField() {

                            const requiresDetails =
                                statusSelect.value ===
                                    "EXCEPTION" ||
                                statusSelect.value ===
                                    "RESOLVED_EXTERNALLY";


                            exceptionContainer.hidden =
                                !requiresDetails;


                            if (!requiresDetails) {

                                exceptionInput.value =
                                    "";
                            }
                        }


                        statusSelect.addEventListener(
                            "change",
                            updateExceptionField
                        );


                        updateExceptionField();

                        return;
                    }


                    /*
                     * Save allocation
                     */

                    const saveButton =
                        event.target.closest(
                            '[data-action="save-allocation"]'
                        );


                    if (saveButton) {

                        const lineId =
                            saveButton.dataset.lineId;


                        const formRow =
                            linesBody.querySelector(
                                `[data-allocation-form="${lineId}"]`
                            );


                        if (!formRow) {
                            return;
                        }


                        const memberId =
                            document.querySelector(
                                `#allocation-member-id-${lineId}`
                            ).value;


                        const subscriptionAmount =
                            parseFloat(
                                document.querySelector(
                                    `#allocation-subscription-${lineId}`
                                ).value || 0
                            );


                        const giftAmount =
                            parseFloat(
                                document.querySelector(
                                    `#allocation-gift-${lineId}`
                                ).value || 0
                            );


                        const calendarYear =
                            parseInt(
                                document.querySelector(
                                    `#allocation-year-${lineId}`
                                ).value,
                                10
                            );


                        const status =
                            document.querySelector(
                                `#allocation-status-${lineId}`
                            ).value;


                        const exceptionReason =
                            document.querySelector(
                                `#allocation-exception-${lineId}`
                            ).value.trim();


                        /*
                         * Validation
                         */

                        if (
                            status === "PENDING" &&
                            !memberId
                        ) {

                            error.textContent =
                                "Please select a member for a Pending allocation.";

                            error.hidden =
                                false;

                            return;
                        }


                        if (
                            !Number.isFinite(
                                subscriptionAmount
                            ) ||
                            subscriptionAmount < 0
                        ) {

                            error.textContent =
                                "Please enter a valid subscription amount.";

                            error.hidden =
                                false;

                            return;
                        }


                        if (
                            !Number.isFinite(
                                giftAmount
                            ) ||
                            giftAmount < 0
                        ) {

                            error.textContent =
                                "Please enter a valid gift amount.";

                            error.hidden =
                                false;

                            return;
                        }


                        if (
                            subscriptionAmount +
                            giftAmount <=
                            0
                        ) {

                            error.textContent =
                                "The allocation must contain a subscription or gift amount.";

                            error.hidden =
                                false;

                            return;
                        }


                        if (
                            !Number.isInteger(
                                calendarYear
                            )
                        ) {

                            error.textContent =
                                "Please enter a valid calendar year.";

                            error.hidden =
                                false;

                            return;
                        }


                        /*
                         * Exception/resolved externally
                         * requires explanatory text.
                         */

                        if (
                            (
                                status === "EXCEPTION" ||
                                status ===
                                    "RESOLVED_EXTERNALLY"
                            ) &&
                            !exceptionReason
                        ) {

                            error.textContent =
                                "Please enter details explaining this allocation status.";

                            error.hidden =
                                false;

                            return;
                        }


                        /*
                         * Clear any previous error.
                         */

                        error.textContent =
                            "";

                        error.hidden =
                            true;


                        /*
                         * Prevent double submission.
                         */

                        saveButton.disabled =
                            true;

                        saveButton.textContent =
                            "Saving...";


                        try {

                            /*
                             * Create the allocation directly
                             * with the selected status.
                             *
                             * For PENDING:
                             *     member_id is supplied.
                             *
                             * For EXCEPTION and
                             * RESOLVED_EXTERNALLY:
                             *     member_id is null.
                             */

                            const createResponse =
                                await fetch(
                                    `${apiBase}/api/payment-import-lines/${lineId}/items`,
                                    {
                                        method: "POST",

                                        headers: {
                                            Authorization:
                                                `Bearer ${user.access_token}`,

                                            "Content-Type":
                                                "application/json"
                                        },

                                        body: JSON.stringify({
                                            member_id:
                                                memberId
                                                    ? Number(memberId)
                                                    : null,

                                            subscription_amount:
                                                subscriptionAmount,

                                            gift_amount:
                                                giftAmount,

                                            calendar_year:
                                                calendarYear,

                                            status:
                                                status,

                                            exception_reason:
                                                exceptionReason ||
                                                null
                                        })
                                    }
                                );


                            if (!createResponse.ok) {

                                let message =
                                    `HTTP ${createResponse.status}`;

                                try {

                                    const responseData =
                                        await createResponse.json();

                                    if (
                                        responseData.error
                                    ) {

                                        message =
                                            responseData.error;
                                    }

                                } catch (_) {
                                    // Keep HTTP error message.
                                }

                                throw new Error(
                                    message
                                );
                            }


                            /*
                             * Allocation has been created.
                             */

                            const created =
                                await createResponse.json();


                            console.log(
                                "Allocation created:",
                                created
                            );


                            /*
                             * Reload the import so that
                             * the new allocation and totals
                             * are displayed from the server.
                             */

                            window.location.reload();


                        } catch (err) {

                            console.error(
                                "Save allocation failed:",
                                err
                            );


                            error.textContent =
                                `Unable to save allocation: ${err.message}`;

                            error.hidden =
                                false;


                            saveButton.disabled =
                                false;

                            saveButton.textContent =
                                "Save allocation";
                        }


                        return;
                    }


                    /*
                     * Cancel allocation
                     */

                    const cancelButton =
                        event.target.closest(
                            '[data-action="cancel-allocation"]'
                        );


                    if (cancelButton) {

                        const lineId =
                            cancelButton.dataset.lineId;


                        const formRow =
                            linesBody.querySelector(
                                `[data-allocation-form="${lineId}"]`
                            );


                        if (formRow) {

                            formRow.remove();
                        }


                        error.textContent =
                            "";

                        error.hidden =
                            true;
                    }

                }
            );


        } catch (err) {

            console.error(
                err
            );


            error.textContent =
                "Unable to load payment import.";

            error.hidden =
                false;
        }

    }
);