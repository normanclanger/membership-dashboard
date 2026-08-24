/*
 * ============================================================
 * Payment Import Detail
 * ============================================================
 *
 * Displays a payment import and its statement lines.
 *
 * Allocation statuses:
 *
 * PENDING
 *     Included in reconciliation.
 *     Will eventually be committed to payments.
 *
 * EXCEPTION
 *     Included in reconciliation.
 *     Remains unresolved and prevents the line being Ready.
 *
 * RESOLVED_EXTERNALLY
 *     Included in reconciliation.
 *     Will NOT be written to payments when committed.
 *
 * COMMITTED
 *     Already written to payments.
 *     Cannot be amended or deleted.
 *
 * ============================================================
 */


/*
 * ============================================================
 * Cognito group helper
 * ============================================================
 */

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

/*
 * ============================================================
 * Error display helper, with scroll
 * ============================================================
 */

function showPaymentImportError(error, message) {

    error.textContent =
        message;

    error.hidden =
        false;

    error.scrollIntoView({
        behavior: "smooth",
        block: "center"
    });
}


/*
 * ============================================================
 * Authentication
 * ============================================================
 */

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


        /*
         * --------------------------------------------------------
         * Validate import ID
         * --------------------------------------------------------
         */

        if (!importId) {

            showPaymentImportError(
                error,
                "No payment import ID was supplied."
            );

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


            /*
             * ----------------------------------------------------
             * Load payment import
             * ----------------------------------------------------
             */

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

            console.log(
                "PAYMENT IMPORT DATA:",
                data
            );


            const paymentImport =
                data.import;

            const lines =
                data.lines || [];


            /*
             * ====================================================
             * Import details
             * ====================================================
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

                    <div
                      class="
                          d-flex
                          align-items-center
                          gap-3
                      "
                  >

                      <span>
                          ${paymentImport.status || "-"}
                      </span>

                      ${
                          (
                              (
                                  paymentImport.status === "IN_PROGRESS" ||
                                  paymentImport.status === "PARTIALLY_COMMITTED"
                              ) &&
                              lines.every(
                                  line =>
								      line.action === "IGNORE" ||
                                      line.status === "COMMITTED"
									  
                              )
                          )

                              ? `
                                  <button
                                      type="button"
                                      class="btn btn-success btn-sm"
                                      id="complete-payment-import"
                                  >
                                      Complete import
                                  </button>
                                `

                              : ""
                      }

                  </div>

                    </td>
                </tr>

            `;


            /*
             * ====================================================
             * Statement lines
             * ====================================================
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
                     * ------------------------------------------------
                     * Reconciliation totals
                     * ------------------------------------------------
                     *
                     * IMPORTANT:
                     *
                     * Every allocation counts towards reconciliation.
                     *
                     * This deliberately includes:
                     *
                     * PENDING
                     * EXCEPTION
                     * RESOLVED_EXTERNALLY
                     *
                     * RESOLVED_EXTERNALLY is only excluded later,
                     * when the import is committed to payments.
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
                     * ------------------------------------------------
                     * Check for open exceptions
                     * ------------------------------------------------
                     */

                    const hasOpenException =
                        items.some(
                            item =>
                                item.status === "EXCEPTION"
                        );


                    /*
                     * =================================================
                     * Allocation summary
                     * =================================================
                     */

                    const allocationSummary =
                        line.action === "IMPORT"

                            ? (() => {

                                let statusText;
                                let statusClass;


                                /*
                                 * Status precedence:
                                 *
                                 * 1. Over-allocated
                                 * 2. Open exception
                                 * 3. Allocation required
                                 * 4. Ready
                                 */

                                 if (line.status === "COMMITTED") {

                                     statusText =
                                         "✓ Committed";

                                     statusClass =
                                         "text-success";

                                 } else if (
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


                                /*
                                 * Add allocation button
                                 *
                                 * Only needed when there is
                                 * money still to allocate.
                                 */

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

                                const commitButton =
                                    outstandingAmount <= 0.005 && 
                                       line.status !== "COMMITTED"

                                        ? `
                                            <button
                                                type="button"
                                                class="btn btn-success btn-sm"
                                                data-action="commit-line"
                                                data-line-id="${line.id}"
                                            >
                                                Commit
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
                                            class="${statusClass}  payment-line-status"
                                        >
                                            <strong>
                                                ${statusText}
                                            </strong>
                                        </span>

                                        ${allocationButton}
                                        ${commitButton}


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
                     * =================================================
                     * Existing allocations
                     * =================================================
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
                                            allocation-table
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

                                                    const memberDisplay =
                                                        item.member
                                                            ? `
                                                                <strong>
                                                                    ${item.member.membership_number}
                                                                </strong>
                                                                — ${item.member.first_name}
                                                                ${item.member.surname}
                                                                ${
                                                                    item.member.tower_name
                                                                        ? ` — ${item.member.tower_name}`
                                                                        : ""
                                                                }
                                                              `
                                                            : "No member";


                                                    const statusDisplay =
                                                        item.status ||
                                                        "-";


                                                    /*
                                                     * ------------------------------------------------
                                                     * Actions
                                                     * ------------------------------------------------
                                                     *
                                                     * Anything not yet committed can be
                                                     * amended or deleted.
                                                     */

                                                    const actions =
                                                        item.status !== "COMMITTED" &&
                                                        line.status !== "COMMITTED"

                                                            ? `

                                                                <button
                                                                    type="button"
                                                                    class="btn btn-outline-primary btn-sm me-1"
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
                                                              `;


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
                                                                ${actions}
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
                     * =================================================
                     * Statement line
                     * =================================================
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
                                ${line.status || "PENDING"}
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
			 * ====================================================
			 * Complete payment import
			 * ====================================================
			 */

			const completeButton =
				document.querySelector(
					"#complete-payment-import"
				);

			if (completeButton) {

				completeButton.addEventListener(
					"click",
					async () => {

						const confirmed =
							window.confirm(
								"Are you sure you want to complete this payment import?"
							);

						if (!confirmed) {
							return;
						}

						completeButton.disabled =
							true;

						completeButton.textContent =
							"Completing...";

						error.textContent =
							"";

						error.hidden =
							true;

						try {

							const response =
								await fetch(
									`${apiBase}/api/payment-imports/${importId}/complete`,
									{
										method: "POST",

										headers: {
											Authorization:
												`Bearer ${user.access_token}`
										}
									}
								);


							if (!response.ok) {

								let message =
									`HTTP ${response.status}`;

								try {

									const responseData =
										await response.json();

									if (responseData.error) {
										message =
											responseData.error;
									}

								} catch (_) {
									// Keep HTTP error message.
								}

								throw new Error(message);
							}


							await response.json();

							window.location.reload();


						} catch (err) {

							console.error(
								"Complete payment import failed:",
								err
							);

							error.textContent =
								`Unable to complete payment import: ${err.message}`;

							error.hidden =
								false;

							error.scrollIntoView({
								behavior: "smooth",
								block: "center"
							});

							completeButton.disabled =
								false;

							completeButton.textContent =
								"Complete import";
						}

					}
				);
			}




            /*
             * ====================================================
             * Scroll expanded allocation tables into view
             * ====================================================
             */

            linesBody.addEventListener(
                "toggle",
                event => {

                    const details =
                        event.target.closest(
                            ".payment-allocation-details"
                        );

                    if (!details || !details.open) {
                        return;
                    }

                    details.scrollIntoView({
                        behavior: "smooth",
                        block: "start"
                    });
                },
                true
            );





            /*
             * ====================================================
             * Allocation controls
             * ====================================================
             */

            linesBody.addEventListener(
                "click",
                async event => {


                  /*
                   * =================================================
                   * COMMIT STATEMENT LINE
                   * =================================================
                   */

                  const commitButton =
                      event.target.closest(
                          '[data-action="commit-line"]'
                      );


                  if (commitButton) {

                      const lineId =
                          commitButton.dataset.lineId;


                      const confirmed =
                          window.confirm(
                              "Are you sure you want to commit this statement line?"
                          );


                      if (!confirmed) {
                          return;
                      }


                      /*
                       * Prevent double submission.
                       */

                      commitButton.disabled =
                          true;

                      commitButton.textContent =
                          "Committing...";


                      /*
                       * Clear previous error.
                       */

                      error.textContent =
                          "";

                      error.hidden =
                          true;


                      try {

                          const commitResponse =
                              await fetch(
                                  `${apiBase}/api/payment-import-lines/${lineId}/commit`,
                                  {
                                      method: "POST",

                                      headers: {
                                          Authorization:
                                              `Bearer ${user.access_token}`
                                      }
                                  }
                              );


                          if (!commitResponse.ok) {

                              let message =
                                  `HTTP ${commitResponse.status}`;


                              try {

                                  const responseData =
                                      await commitResponse.json();


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


                          const committed =
                              await commitResponse.json();


                          console.log(
                              "Statement line committed:",
                              committed
                          );


                          /*
                           * Reload so the line status,
                           * allocation statuses and import
                           * totals are recalculated.
                           */

                          window.location.reload();


                      } catch (err) {

                          console.error(
                              "Commit statement line failed:",
                              err
                          );


                         showPaymentImportError(
                             error,
                             `Unable to commit statement line: ${err.message}`
                         );


                          error.scrollIntoView({
                              behavior: "smooth",
                              block: "center"
                          });


                          commitButton.disabled =
                              false;

                          commitButton.textContent =
                              "Commit";
                      }


                      return;
                  }




                    /*
                     * =================================================
                     * ADD ALLOCATION
                     * =================================================
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
                         * ------------------------------------------------
                         * Create allocation form
                         * ------------------------------------------------
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
                                                type="text"
                                                class="form-control"
                                                id="allocation-subscription-${lineId}"
                                                value="0.00"
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
                                                type="text"
                                                class="form-control"
                                                id="allocation-gift-${lineId}"
                                                value="0.00"
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

                        formRow.scrollIntoView({
                            behavior: "smooth",
                            block: "start"
                        });

                        /*
                         * ------------------------------------------------
                         * Initialise member search and form controls
                         * ------------------------------------------------
                         */

                        initialiseAllocationForm(
                            lineId,
                            apiBase,
                            user,
                            error
                        );

                        return;
                    }


                    /*
                     * =================================================
                     * AMEND ALLOCATION
                     * =================================================
                     */

                    const amendButton =
                        event.target.closest(
                            '[data-action="amend-allocation"]'
                        );


                    if (amendButton) {

                        const itemId =
                            amendButton.dataset.itemId;

                        const lineId =
                            amendButton.dataset.lineId;


                        /*
                         * Find the allocation being amended
                         */

                        const line =
                            lines.find(
                                currentLine =>
                                    String(currentLine.id) ===
                                    String(lineId)
                            );


                        if (!line) {



                          showPaymentImportError(
                             error,
                             "Unable to find the statement line."
                             );

                            return;
                        }


                        const item =
                            (line.items || []).find(
                                currentItem =>
                                    String(currentItem.id) ===
                                    String(itemId)
                            );


                        if (!item) {

                            showPaymentImportError(
                                error,
                                "Unable to find the allocation."
                            );

                            return;
                        }


                        /*
                         * Don't amend committed allocations.
                         */

                        if (
                            item.status === "COMMITTED"
                        ) {

                            showPaymentImportError(
                                error,
                                "Committed allocations cannot be amended."
                            );

                            return;
                        }


                        /*
                         * Don't create two forms.
                         */

                        const existingForm =
                            linesBody.querySelector(
                                `[data-allocation-form="${lineId}"]`
                            );


                        if (existingForm) {
                            return;
                        }


                        /*
                         * ------------------------------------------------
                         * Create amend form
                         * ------------------------------------------------
                         */

                        const formRow =
                            document.createElement("tr");


                        formRow.dataset.allocationForm =
                            lineId;


                        const subscriptionValue =
                            parseFloat(
                                item.subscription_amount || 0
                            ).toFixed(2);


                        const giftValue =
                            parseFloat(
                                item.gift_amount || 0
                            ).toFixed(2);


                        const yearValue =
                            item.calendar_year ||
                            new Date().getFullYear();


                        const statusValue =
                            item.status ||
                            "PENDING";


                        const exceptionValue =
                            item.exception_reason ||
                            "";


                        formRow.innerHTML = `

                            <td
                                colspan="6"
                                class="bg-light"
                            >

                                <div class="p-3">

                                    <h5>
                                        Amend allocation
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
                                            value="${
                                                item.member_id || ""
                                            }"
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
                                                value="${subscriptionValue}"
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
                                                value="${giftValue}"
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
                                                value="${yearValue}"
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
                                                    ${
                                                        statusValue ===
                                                        "PENDING"
                                                            ? "selected"
                                                            : ""
                                                    }
                                                >
                                                    Pending
                                                </option>

                                                <option
                                                    value="EXCEPTION"
                                                    ${
                                                        statusValue ===
                                                        "EXCEPTION"
                                                            ? "selected"
                                                            : ""
                                                    }
                                                >
                                                    Exception
                                                </option>

                                                <option
                                                    value="RESOLVED_EXTERNALLY"
                                                    ${
                                                        statusValue ===
                                                        "RESOLVED_EXTERNALLY"
                                                            ? "selected"
                                                            : ""
                                                    }
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
                                        >${exceptionValue}</textarea>

                                    </div>


                                    <div class="mt-3">

                                        <button
                                            type="button"
                                            class="btn btn-primary btn-sm"
                                            data-action="update-allocation"
                                            data-line-id="${lineId}"
                                            data-item-id="${itemId}"
                                        >
                                            Save changes
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


                        /*
                         * Put form immediately after the
                         * statement line.
                         */

                        const statementRow =
                            amendButton.closest(
                                "details"
                            )?.closest(
                                "td"
                            )?.closest(
                                "tr"
                            );


                        if (statementRow) {

                            statementRow.after(
                                formRow
                            );

                        } else {

                            amendButton
                                .closest("tr")
                                .after(formRow);
                        }

                        formRow.scrollIntoView({
                            behavior: "smooth",
                            block: "start"
                        });


                        /*
                         * Initialise form controls.
                         */

                        initialiseAllocationForm(
                            lineId,
                            apiBase,
                            user,
                            error
                        );


                        /*
                         * ------------------------------------------------
                         * Display existing member
                         * ------------------------------------------------
                         */

                        if (
                            item.member_id
                        ) {

                            const memberInput =
                                document.querySelector(
                                    `#allocation-member-${lineId}`
                                );


                            /*
                             * We only have the member ID in the
                             * allocation data. Load the member so
                             * that the same search/history UI can
                             * be populated.
                             */

                            try {

                                const memberResponse =
                                    await fetch(
                                        `${apiBase}/api/members/${item.member_id}`,
                                        {
                                            headers: {
                                                Authorization:
                                                    `Bearer ${user.access_token}`
                                            }
                                        }
                                    );


                                if (
                                    memberResponse.ok
                                ) {

                                    const memberData =
                                        await memberResponse.json();


                                    const member =
                                        memberData.member ||
                                        memberData;


                                    if (member) {

                                        const membershipNumber =
                                            member.membership_number ||
                                            "";


                                        const memberName =
                                            `${member.first_name || ""} ${member.surname || ""}`
                                                .trim();


                                        memberInput.value =
                                            membershipNumber
                                                ? `${membershipNumber} — ${memberName}`
                                                : memberName;


                                        /*
                                         * Load payment history for
                                         * the existing member.
                                         */

                                        await loadPaymentHistory(
                                            item.member_id,
                                            membershipNumber,
                                            memberName,
                                            lineId,
                                            apiBase,
                                            user
                                        );
                                    }

                                }

                            } catch (err) {

                                console.error(
                                    "Unable to load existing member:",
                                    err
                                );

                                memberInput.value =
                                    `Member #${item.member_id}`;
                            }
                        }


                        /*
                         * Update exception field visibility.
                         */

                        const statusSelect =
                            document.querySelector(
                                `#allocation-status-${lineId}`
                            );


                        if (statusSelect) {

                            statusSelect.dispatchEvent(
                                new Event("change")
                            );
                        }


                        return;
                    }


                    /*
                     * =================================================
                     * SAVE NEW ALLOCATION
                     * =================================================
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


                        /*
                         * Read form values.
                         */

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
                         * ------------------------------------------------
                         * Validation
                         * ------------------------------------------------
                         */

                        if (
                            status === "PENDING" &&
                            !memberId
                        ) {


                            showPaymentImportError(
                                error,
                                "Please select a member for a Pending allocation."
                            );

                            return;
                        }


                        if (
                            (
                                status === "EXCEPTION" ||
                                status === "RESOLVED_EXTERNALLY"
                            ) &&
                            memberId
                        ) {


                            showPaymentImportError(
                                error,
                                "A member must not be selected for an Exception or Resolved externally allocation."
                            );

                            return;
                        }


                        if (
                            !Number.isFinite(
                                subscriptionAmount
                            ) ||
                            subscriptionAmount < 0
                        ) {


                            showPaymentImportError(
                                error,
                                "Please enter a valid subscription amount."
                            );
                            return;
                        }


                        if (
                            !Number.isFinite(
                                giftAmount
                            ) ||
                            giftAmount < 0
                        ) {

                            showPaymentImportError(
                                error,
                                "Please enter a valid gift amount."
                            );

                            return;
                        }


                        if (
                            subscriptionAmount +
                            giftAmount <=
                            0
                        ) {


                            showPaymentImportError(
                                error,
                                "The allocation must contain a subscription or gift amount."
                            );
                            return;
                        }


                        if (
                            !Number.isInteger(
                                calendarYear
                            )
                        ) {


                            showPaymentImportError(
                                error,
                                "Please enter a valid calendar year."
                            );
                            return;
                        }


                        if (
                            (
                                status === "EXCEPTION" ||
                                status ===
                                    "RESOLVED_EXTERNALLY"
                            ) &&
                            !exceptionReason
                        ) {


                            showPaymentImportError(
                                error,
                                "Please enter details explaining this allocation status."
                            );
                            return;
                        }


                        /*
                         * Clear previous error.
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
                             * Create the allocation.
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


                            const created =
                                await createResponse.json();


                            console.log(
                                "Allocation created:",
                                created
                            );


                            /*
                             * Reload so reconciliation
                             * totals and status are recalculated.
                             */

                            window.location.reload();


                        } catch (err) {

                            console.error(
                                "Save allocation failed:",
                                err
                            );



                            showPaymentImportError(
                                error,
                                `Unable to save allocation: ${err.message}`
                            );

                            error.scrollIntoView({
                                behavior: "smooth",
                                block: "center"
                            });


                            saveButton.disabled =
                                false;

                            saveButton.textContent =
                                "Save allocation";
                        }


                        return;
                    }


                    /*
                     * =================================================
                     * DELETE ALLOCATION
                     * =================================================
                     */

                    const deleteButton =
                        event.target.closest(
                            '[data-action="delete-allocation"]'
                        );


                    if (deleteButton) {

                        const itemId =
                            deleteButton.dataset.itemId;


                        /*
                         * Confirm deletion.
                         */

                        const confirmed =
                            window.confirm(
                                "Are you sure you want to delete this allocation?"
                            );


                        if (!confirmed) {
                            return;
                        }


                        /*
                         * Prevent double-clicks.
                         */

                        deleteButton.disabled =
                            true;

                        deleteButton.textContent =
                            "Deleting...";


                        try {

                            const deleteResponse =
                                await fetch(
                                    `${apiBase}/api/payment-import-items/${itemId}`,
                                    {
                                        method: "DELETE",

                                        headers: {
                                            Authorization:
                                                `Bearer ${user.access_token}`
                                        }
                                    }
                                );


                            if (!deleteResponse.ok) {

                                let message =
                                    `HTTP ${deleteResponse.status}`;


                                try {

                                    const responseData =
                                        await deleteResponse.json();


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


                            console.log(
                                "Allocation deleted:",
                                itemId
                            );


                            /*
                             * Reload so reconciliation totals
                             * are recalculated from the server.
                             */

                            window.location.reload();


                        } catch (err) {

                            console.error(
                                "Delete allocation failed:",
                                err
                            );


                            showPaymentImportError(
                                error,
                                `Unable to delete allocation: ${err.message}`
                            );


                            deleteButton.disabled =
                                false;

                            deleteButton.textContent =
                                "Delete";
                        }


                        return;
                    }


                    /*
                     * =================================================
                     * SAVE AMENDED ALLOCATION
                     * =================================================
                     */

                    const updateButton =
                        event.target.closest(
                            '[data-action="update-allocation"]'
                        );


                    if (updateButton) {

                        const lineId =
                            updateButton.dataset.lineId;


                        const itemId =
                            updateButton.dataset.itemId;


                        const formRow =
                            linesBody.querySelector(
                                `[data-allocation-form="${lineId}"]`
                            );


                        if (!formRow) {
                            return;
                        }


                        /*
                         * Read form values.
                         */

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
                         * ------------------------------------------------
                         * Validation
                         * ------------------------------------------------
                         */

                        if (
                            status === "PENDING" &&
                            !memberId
                        ) {


                            showPaymentImportError(
                                error,
                                "Please select a member for a Pending allocation."
                            );

                            return;
                        }


                        if (
                            (
                                status === "EXCEPTION" ||
                                status === "RESOLVED_EXTERNALLY"
                            ) &&
                            memberId
                        ) {

                            showPaymentImportError(
                                error,
                                "A member must not be selected for an Exception or Resolved externally allocation."
                            );

                            return;
                        }


                        if (
                            !Number.isFinite(
                                subscriptionAmount
                            ) ||
                            subscriptionAmount < 0
                        ) {


                            showPaymentImportError(
                                error,
                                "Please enter a valid subscription amount."
                            );

                            return;
                        }


                        if (
                            !Number.isFinite(
                                giftAmount
                            ) ||
                            giftAmount < 0
                        ) {


                            showPaymentImportError(
                                error,
                                "Please enter a valid gift amount."
                            );

                            return;
                        }


                        if (
                            subscriptionAmount +
                            giftAmount <=
                            0
                        ) {


                            showPaymentImportError(
                                error,
                                "The allocation must contain a subscription or gift amount."
                            );

                            return;
                        }


                        if (
                            !Number.isInteger(
                                calendarYear
                            )
                        ) {


                            showPaymentImportError(
                                error,
                                "Please enter a valid calendar year."
                            );

                            return;
                        }


                        if (
                            (
                                status === "EXCEPTION" ||
                                status ===
                                    "RESOLVED_EXTERNALLY"
                            ) &&
                            !exceptionReason
                        ) {


                            showPaymentImportError(
                                error,
                                "Please enter details explaining this allocation status."
                            );
                            return;
                        }


                        /*
                         * Clear previous error.
                         */

                        error.textContent =
                            "";

                        error.hidden =
                            true;


                        /*
                         * Prevent double submission.
                         */

                        updateButton.disabled =
                            true;

                        updateButton.textContent =
                            "Saving...";


                        try {

                            /*
                             * Update the allocation.
                             */

                            const updateResponse =
                                await fetch(
                                    `${apiBase}/api/payment-import-items/${itemId}`,
                                    {
                                        method: "PATCH",

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


                            if (!updateResponse.ok) {

                                let message =
                                    `HTTP ${updateResponse.status}`;


                                try {

                                    const responseData =
                                        await updateResponse.json();


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


                            const updated =
                                await updateResponse.json();


                            console.log(
                                "Allocation updated:",
                                updated
                            );


                            /*
                             * Reload so that reconciliation
                             * totals and status are recalculated.
                             */

                            window.location.reload();


                        } catch (err) {

                            console.error(
                                "Update allocation failed:",
                                err
                            );



                            showPaymentImportError(
                                error,
                                `Unable to update allocation: ${err.message}`
                            );
							
                            error.scrollIntoView({
                              behavior: "smooth",
                              block: "center"
                            });


                            updateButton.disabled =
                                false;

                            updateButton.textContent =
                                "Save changes";
                        }


                        return;
                    }


                    /*
                     * =================================================
                     * CANCEL ALLOCATION FORM
                     * =================================================
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


            showPaymentImportError(
                error,
                "Unable to load payment import."
            );
        }

    }
);


/*
 * ============================================================
 * Allocation form initialisation
 * ============================================================
 *
 * Used by both:
 *
 *     Add allocation
 *     Amend allocation
 *
 * This keeps the member lookup, payment history and
 * status handling identical in both forms.
 *
 * ============================================================
 */

function initialiseAllocationForm(
    lineId,
    apiBase,
    user,
    error
) {

    /*
     * ------------------------------------------------------------
     * Form controls
     * ------------------------------------------------------------
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


    /*
     * ------------------------------------------------------------
     * Member search
     * ------------------------------------------------------------
     */

    let searchTimeout;


    memberInput.addEventListener(
        "input",
        () => {

            clearTimeout(
                searchTimeout
            );


            const search =
                memberInput.value.trim();


            /*
             * Typing into the member box means the
             * previous member selection is no longer valid.
             */

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
             * Member search requires MembershipViewer.
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
     * ------------------------------------------------------------
     * Member selection
     * ------------------------------------------------------------
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
             * Set selected member.
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
             * Load payment history.
             */

            await loadPaymentHistory(
                memberId,
                membershipNumber,
                memberName,
                lineId,
                apiBase,
                user
            );

        }
    );


    /*
     * ------------------------------------------------------------
     * Status controls
     * ------------------------------------------------------------
     */

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


        /*
         * A member is only valid for PENDING.
         *
         * We don't automatically clear the member here,
         * because changing the status and changing the
         * member are separate user actions.
         *
         * The save validation handles this safely.
         */
    }


    statusSelect.addEventListener(
        "change",
        updateExceptionField
    );


    updateExceptionField();
}


/*
 * ============================================================
 * Payment history
 * ============================================================
 */

async function loadPaymentHistory(
    memberId,
    membershipNumber,
    memberName,
    lineId,
    apiBase,
    user
) {

    const paymentHistory =
        document.querySelector(
            `#allocation-payment-history-${lineId}`
        );


    if (!paymentHistory) {
        return;
    }


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
         * --------------------------------------------------------
         * No payment history
         * --------------------------------------------------------
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
         * --------------------------------------------------------
         * Display payment history
         * --------------------------------------------------------
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
                                                payment.subscription_amount ||
                                                0
                                            );


                                        const gift =
                                            parseFloat(
                                                payment.gift_amount ||
                                                0
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