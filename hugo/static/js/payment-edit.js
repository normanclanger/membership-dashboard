import {
    requireLogin
} from "/js/auth.js";


const API_BASE =
    `${window.API_BASE_URL}`;


let currentPayment = null;


// --------------------------------------------------
// Helpers
// --------------------------------------------------

function showMessage(
    elementId,
    message,
    type = "info"
) {
    const element =
        document.getElementById(
            elementId
        );

    element.textContent =
        message;

    element.className =
        `alert alert-${type}`;

    element.hidden = false;
}


function formatCurrency(
    value
) {
    return new Intl.NumberFormat(
        "en-GB",
        {
            style: "currency",
            currency: "GBP"
        }
    ).format(
        Number(value)
    );
}


function updateNewTotal() {
    const subscription =
        Number(
            document.getElementById(
                "subscription-amount"
            ).value
        ) || 0;

    const gift =
        Number(
            document.getElementById(
                "gift-amount"
            ).value
        ) || 0;

    const total =
        subscription + gift;

    document.getElementById(
        "edit-new-total"
    ).textContent =
        formatCurrency(
            total
        );
}


function showApiResponse(
    data
) {
    const section =
        document.getElementById(
            "api-response-section"
        );

    const output =
        document.getElementById(
            "api-response"
        );

    output.textContent =
        JSON.stringify(
            data,
            null,
            2
        );

    section.hidden = false;
}


// --------------------------------------------------
// Display payment
// --------------------------------------------------

function displayPayment(
    payment
) {
    currentPayment =
        payment;

    const total =
        Number(
            payment.subscription_amount
        ) +
        Number(
            payment.gift_amount
        );

    // Current payment

    document.getElementById(
        "current-id"
    ).textContent =
        payment.id;

    document.getElementById(
        "current-member"
    ).textContent =
        `${payment.membership_number} - ${payment.first_name} ${payment.surname}`;

    document.getElementById(
        "current-date"
    ).textContent =
        payment.payment_date;

    document.getElementById(
        "current-reference"
    ).textContent =
        payment.statement_reference;

    document.getElementById(
        "current-subscription"
    ).textContent =
        formatCurrency(
            payment.subscription_amount
        );

    document.getElementById(
        "current-gift"
    ).textContent =
        formatCurrency(
            payment.gift_amount
        );

    document.getElementById(
        "current-total"
    ).textContent =
        formatCurrency(
            total
        );

    document.getElementById(
        "current-year"
    ).textContent =
        payment.calendar_year;

    document.getElementById(
        "current-import-item"
    ).textContent =
        payment.import_item_id ??
        "—";


    // Edit form

    document.getElementById(
        "payment-date"
    ).value =
        payment.payment_date;

    document.getElementById(
        "statement-reference"
    ).value =
        payment.statement_reference;

    document.getElementById(
        "member-id"
    ).value =
        payment.member_id;

    document.getElementById(
        "subscription-amount"
    ).value =
        Number(
            payment.subscription_amount
        ).toFixed(2);

    document.getElementById(
        "gift-amount"
    ).value =
        Number(
            payment.gift_amount
        ).toFixed(2);

    document.getElementById(
        "calendar-year"
    ).value =
        payment.calendar_year;


    // Totals

    document.getElementById(
        "edit-original-total"
    ).textContent =
        formatCurrency(
            total
        );

    updateNewTotal();


    document.getElementById(
        "payment-section"
    ).hidden =
        false;
		
		
	document.getElementById(
        "member-id"
    ).value =
        payment.member_id;

    document.getElementById(
        "selected-member"
    ).textContent =
        `${payment.first_name} ` +
        `${payment.surname} ` +
        `(${payment.membership_number})`;

    document.getElementById(
        "selected-member"
    ).hidden =
        false;	
}


// --------------------------------------------------
// GET payment
// --------------------------------------------------

async function loadPayment(
    paymentId
) {
    try {
        showMessage(
            "load-message",
            "Loading payment...",
            "info"
        );

        const user =
            await requireLogin();

        if (!user) {
            return;
        }

        const response =
            await fetch(
                `${API_BASE}/api/payments/${paymentId}`,
                {
                    headers: {
                        Authorization:
                            `Bearer ${user.access_token}`
                    }
                }
            );

        const data =
            await response.json();

        if (!response.ok) {
            throw new Error(
                data.error ||
                "Unable to load payment."
            );
        }

        displayPayment(
            data.payment
        );

        showMessage(
            "load-message",
            "Payment loaded.",
            "success"
        );

    } catch (err) {

        console.error(
            "Payment load error:",
            err
        );

        showMessage(
            "load-message",
            err.message ||
            "Unable to load payment.",
            "danger"
        );

        document.getElementById(
            "payment-section"
        ).hidden =
            true;
    }
}


// --------------------------------------------------
// PATCH payment
// --------------------------------------------------

async function savePayment() {

    if (!currentPayment) {
        showMessage(
            "save-message",
            "Load a payment before saving.",
            "danger"
        );

        return;
    }


    try {

        showMessage(
            "save-message",
            "Saving changes...",
            "info"
        );


        const user =
            await requireLogin();

        if (!user) {
            return;
        }


        const paymentId =
            currentPayment.id;


        const payload = {
            payment_date:
                document.getElementById(
                    "payment-date"
                ).value,

            statement_reference:
                document.getElementById(
                    "statement-reference"
                ).value.trim(),

            member_id:
                Number(
                    document.getElementById(
                        "member-id"
                    ).value
                ),

            subscription_amount:
                document.getElementById(
                    "subscription-amount"
                ).value,

            gift_amount:
                document.getElementById(
                    "gift-amount"
                ).value,

            calendar_year:
                Number(
                    document.getElementById(
                        "calendar-year"
                    ).value
                )
        };


        const response =
            await fetch(
                `${API_BASE}/api/payments/${paymentId}`,
                {
                    method: "PATCH",

                    headers: {
                        Authorization:
                            `Bearer ${user.access_token}`,

                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(
                            payload
                        )
                }
            );


        const data =
            await response.json();



        if (!response.ok) {
            throw new Error(
                data.error ||
                "Unable to save payment."
            );
        }


        // Reload the payment using GET so that
        // the member name and other joined data
        // are populated correctly.

        await loadPayment(
            paymentId
        );


        showMessage(
            "save-message",
            "Payment saved successfully.",
            "success"
        );


    } catch (err) {

        console.error(
            "Payment save error:",
            err
        );

        showMessage(
            "save-message",
            err.message ||
            "Unable to save payment.",
            "danger"
        );
    }
}



// --------------------------------------------------
// Split payment
// --------------------------------------------------

let splitRowCounter = 0;


function createSplitRow(
    payment = currentPayment || {}
) {

    splitRowCounter++;

    const rowId =
        splitRowCounter;


    const row =
        document.createElement(
            "div"
        );

    row.className =
        "card mb-3";

    row.dataset.rowId =
        rowId;


    row.innerHTML = `

        <div class="card-body">

            <div class="d-flex justify-content-between align-items-center mb-3">

                <h5 class="mb-0">
                    Split payment ${rowId}
                </h5>

                <button
                    type="button"
                    class="btn btn-sm btn-outline-danger remove-split-row"
                >
                    Remove
                </button>

            </div>


            <div class="row">

                <div class="col-md-3 mb-3">

                    <label
                        class="form-label"
                    >
                        Payment date
                    </label>

                    <input
                        type="date"
                        class="form-control split-date"
                        value="${payment.payment_date || ""}"
                        required
                    >

                </div>


                <div class="col-md-5 mb-3">

                    <label
                        class="form-label"
                    >
                        Statement reference
                    </label>

                    <input
                        type="text"
                        class="form-control split-reference"
                        value="${payment.statement_reference || ""}"
                        required
                    >

                </div>


                <div class="col-md-4 mb-3">

                    <label
                        class="form-label"
                    >
                        Calendar year
                    </label>

                    <input
                        type="number"
                        class="form-control split-year"
                        value="${payment.calendar_year || ""}"
                        required
                    >

                </div>

            </div>


            <div class="row">

                <div class="col-md-8 mb-3">

                    <label
                        class="form-label"
                    >
                        Member
                    </label>

                    <input
                        type="text"
                        class="form-control split-member-search"
                        placeholder="Search by name or membership number"
                        autocomplete="off"
                    >

                    <div
                        class="split-member-search-results mt-2"
                    ></div>

                    <div
                        class="alert alert-secondary mt-2 split-selected-member"
                        hidden
                    ></div>

                    <input
                        type="hidden"
                        class="split-member-id"
                        value="${payment.member_id || ""}"
                    >

                </div>


                <div class="col-md-2 mb-3">

                    <label
                        class="form-label"
                    >
                        Subscription
                    </label>

                    <input
                        type="number"
                        class="form-control split-subscription"
                        min="0"
                        step="0.01"
                        value="${payment.subscription_amount ?? 0}"
                        required
                    >

                </div>


                <div class="col-md-2 mb-3">

                    <label
                        class="form-label"
                    >
                        Gift
                    </label>

                    <input
                        type="number"
                        class="form-control split-gift"
                        min="0"
                        step="0.01"
                        value="${payment.gift_amount ?? 0}"
                        required
                    >

                </div>

            </div>


            <div class="text-end">

                <strong>
                    Row total:
                </strong>

                <span
                    class="split-row-total"
                >
                    £0.00
                </span>

            </div>

        </div>
    `;


    const container =
        document.getElementById(
            "split-rows"
        );


    container.appendChild(
        row
    );


    const subscriptionInput =
        row.querySelector(
            ".split-subscription"
        );

    const giftInput =
        row.querySelector(
            ".split-gift"
        );


    subscriptionInput.addEventListener(
        "input",
        updateSplitTotals
    );

    giftInput.addEventListener(
        "input",
        updateSplitTotals
    );


    row.querySelector(
        ".remove-split-row"
    ).addEventListener(
        "click",
        () => {

            row.remove();

            updateSplitTotals();
            updateSplitRowHeadings();
        }
    );


    const searchInput =
        row.querySelector(
            ".split-member-search"
        );


    searchInput.addEventListener(
        "input",
        () => searchSplitMembers(
            row
        )
    );


    updateSplitTotals();

    updateSplitRowHeadings();
}


async function searchSplitMembers(
    row
) {

    const searchInput =
        row.querySelector(
            ".split-member-search"
        );

    const resultsContainer =
        row.querySelector(
            ".split-member-search-results"
        );


    const search =
        searchInput.value.trim();


    resultsContainer.innerHTML =
        "";


    if (!search) {
        return;
    }


    try {

        const user =
            await requireLogin();

        if (!user) {
            return;
        }


        const response =
            await fetch(
                `${API_BASE}/api/members?search=${encodeURIComponent(search)}`,
                {
                    method: "GET",

                    headers: {
                        Authorization:
                            `Bearer ${user.access_token}`
                    }
                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            throw new Error(
                result.error ||
                "Unable to search for members."
            );
        }


        const members =
            Array.isArray(result)
                ? result
                : result.members || [];


        if (members.length === 0) {

            const empty =
                document.createElement(
                    "p"
                );

            empty.textContent =
                "No members found.";

            resultsContainer.appendChild(
                empty
            );

            return;
        }


        members.forEach(
            member => {

                const resultRow =
                    document.createElement(
                        "div"
                    );

                resultRow.className =
                    "d-flex align-items-center gap-2 mb-2";


                const text =
                    document.createElement(
                        "span"
                    );

                text.className =
                    "flex-grow-1";

                text.textContent =
                    `${member.first_name} ` +
                    `${member.surname} ` +
                    `(${member.membership_number})`;


                const selectButton =
                    document.createElement(
                        "button"
                    );

                selectButton.type =
                    "button";

                selectButton.className =
                    "btn btn-sm btn-primary";

                selectButton.textContent =
                    "Select";


                selectButton.addEventListener(
                    "click",
                    () => {

                        selectSplitMember(
                            row,
                            member
                        );
                    }
                );


                resultRow.appendChild(
                    text
                );

                resultRow.appendChild(
                    selectButton
                );

                resultsContainer.appendChild(
                    resultRow
                );
            }
        );

    } catch (error) {

        console.error(
            "Split member search error:",
            error
        );

        resultsContainer.textContent =
            error.message ||
            "Unable to search for members.";
    }
}


function selectSplitMember(
    row,
    member
) {

    row.querySelector(
        ".split-member-id"
    ).value =
        member.id;


    const selectedMember =
        row.querySelector(
            ".split-selected-member"
        );


    selectedMember.textContent =
        `${member.first_name} ` +
        `${member.surname} ` +
        `(${member.membership_number})`;


    selectedMember.hidden =
        false;


    row.querySelector(
        ".split-member-search-results"
    ).innerHTML =
        "";


    row.querySelector(
        ".split-member-search"
    ).value =
        "";
}


function updateSplitTotals() {

    const rows =
        document.querySelectorAll(
            "#split-rows > .card"
        );


    let grandTotal =
        0;


    rows.forEach(
        row => {

            const subscription =
                Number(
                    row.querySelector(
                        ".split-subscription"
                    ).value
                ) || 0;


            const gift =
                Number(
                    row.querySelector(
                        ".split-gift"
                    ).value
                ) || 0;


            const total =
                subscription + gift;


            row.querySelector(
                ".split-row-total"
            ).textContent =
                formatCurrency(
                    total
                );


            grandTotal +=
                total;
        }
    );


    document.getElementById(
        "split-new-total"
    ).textContent =
        formatCurrency(
            grandTotal
        );


    const originalTotal =
        Number(
            currentPayment.subscription_amount
        ) +
        Number(
            currentPayment.gift_amount
        );


    const difference =
        grandTotal -
        originalTotal;


    document.getElementById(
        "split-difference"
    ).textContent =
        formatCurrency(
            difference
        );


    const saveButton =
        document.getElementById(
            "save-split"
        );


    saveButton.disabled =
        Math.abs(
            difference
        ) > 0.005;
}


function updateSplitRowHeadings() {

    const rows =
        document.querySelectorAll(
            "#split-rows > .card"
        );


    rows.forEach(
        (row, index) => {

            row.querySelector(
                "h5"
            ).textContent =
                `Split payment ${index + 1}`;
        }
    );
}


function initialiseSplitPayments() {

    const container =
        document.getElementById(
            "split-rows"
        );


    container.innerHTML =
        "";


    splitRowCounter =
        0;


    createSplitRow();

    createSplitRow();


    document.getElementById(
        "split-original-total"
    ).textContent =
        formatCurrency(
            Number(
                currentPayment.subscription_amount
            ) +
            Number(
                currentPayment.gift_amount
            )
        );
}


async function saveSplit() {

    if (!currentPayment) {

        showMessage(
            "split-message",
            "Load a payment before splitting it.",
            "danger"
        );

        return;
    }


    const rows =
        document.querySelectorAll(
            "#split-rows > .card"
        );


    if (rows.length < 2) {

        showMessage(
            "split-message",
            "A split must contain at least two payments.",
            "danger"
        );

        return;
    }


    const payments =
        [];


    for (
        const row of rows
    ) {

        const memberId =
            Number(
                row.querySelector(
                    ".split-member-id"
                ).value
            );


        if (!memberId) {

            showMessage(
                "split-message",
                "Please select a member for every payment.",
                "danger"
            );

            return;
        }


        const subscription =
            row.querySelector(
                ".split-subscription"
            ).value;


        const gift =
            row.querySelector(
                ".split-gift"
            ).value;


        payments.push({

            payment_date:
                row.querySelector(
                    ".split-date"
                ).value,

            statement_reference:
                row.querySelector(
                    ".split-reference"
                ).value.trim(),

            member_id:
                memberId,

            subscription_amount:
                subscription,

            gift_amount:
                gift,

            calendar_year:
                Number(
                    row.querySelector(
                        ".split-year"
                    ).value
                )
        });
    }


    try {

        showMessage(
            "split-message",
            "Saving split...",
            "info"
        );


        const user =
            await requireLogin();

        if (!user) {
            return;
        }


        const response =
            await fetch(
                `${API_BASE}/api/payments/${currentPayment.id}/split`,
                {
                    method: "POST",

                    headers: {
                        Authorization:
                            `Bearer ${user.access_token}`,

                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            payments
                        })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Unable to split payment."
            );
        }


        showMessage(
            "split-message",
            "Payment split successfully.",
            "success"
        );


        document.getElementById(
            "payment-section"
        ).hidden = true;

        currentPayment = null;

    } catch (error) {

        console.error(
            "Payment split error:",
            error
        );

        showMessage(
            "split-message",
            error.message ||
            "Unable to split payment.",
            "danger"
        );
    }
}




// --------------------------------------------------
// Event handlers
// --------------------------------------------------

document.addEventListener(
    "DOMContentLoaded",
    () => {

        const params =
            new URLSearchParams(
                window.location.search
            );

        const id =
            params.get("id");


        const paymentIdInput =
            document.getElementById(
                "payment-id"
            );


        const loadButton =
            document.getElementById(
                "load-payment-button"
            );


        const saveButton =
            document.getElementById(
                "save-payment"
            );
			
		const memberSearch =
            document.getElementById(
                "member-search"
            );


        if (id) {

            paymentIdInput.value =
                id;

            loadPayment(
                id
            );
        }


        loadButton.addEventListener(
            "click",
            () => {

                const paymentId =
                    paymentIdInput.value.trim();

                if (!paymentId) {

                    showMessage(
                        "load-message",
                        "Please enter a payment ID.",
                        "danger"
                    );

                    return;
                }

                loadPayment(
                    paymentId
                );
            }
        );


        saveButton.addEventListener(
            "click",
            () => {

                console.log(
                    "SAVE BUTTON CLICKED"
                );

                savePayment();
            }
        );
		
		memberSearch.addEventListener(
            "input",
            searchMembers
        );
		
		const addSplitRowButton =
            document.getElementById(
            "add-split-row"
            );
		
		const saveSplitButton =
            document.getElementById(
                "save-split"
            );
		
		addSplitRowButton.addEventListener(
            "click",
            () => {

                const container =
                    document.getElementById(
                        "split-rows"
                    );

                if (
                    container.children.length === 0
                ) {
                    initialiseSplitPayments();
                } else {
                    createSplitRow();
                }

            }
        );
		
        saveSplitButton.addEventListener(
            "click",
            saveSplit
        );		

        // Recalculate the displayed
        // new total as amounts change.

        document.getElementById(
            "subscription-amount"
        ).addEventListener(
            "input",
            updateNewTotal
        );


        document.getElementById(
            "gift-amount"
        ).addEventListener(
            "input",
            updateNewTotal
        );
		
		
		
    }
);


function selectMember(
    member
) {

    document.getElementById(
        "member-id"
    ).value =
        member.id;


    const selectedMember =
        document.getElementById(
            "selected-member"
        );


    selectedMember.textContent =
        `${member.first_name} ` +
        `${member.surname} ` +
        `(${member.membership_number})`;


    selectedMember.hidden =
        false;


    document.getElementById(
        "member-search-results"
    ).innerHTML = "";


    document.getElementById(
        "member-search"
    ).value = "";
}


async function searchMembers() {

    const searchInput =
        document.querySelector(
            "#member-search"
        );

    const resultsContainer =
        document.querySelector(
            "#member-search-results"
        );

    const search =
        searchInput.value.trim();

    resultsContainer.innerHTML = "";

    if (!search) {
        return;
    }


    try {

        const user =
            await requireLogin();

        if (!user) {
            return;
        }


        const response =
            await fetch(
                `${API_BASE}/api/members?search=${encodeURIComponent(search)}`,
                {
                    method: "GET",

                    headers: {
                        "Authorization":
                            `Bearer ${user.access_token}`
                    }
                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            throw new Error(
                result.error ||
                "Unable to search for members."
            );
        }


        const members =
            Array.isArray(result)
                ? result
                : result.members || [];


        if (members.length === 0) {

            const empty =
                document.createElement("p");

            empty.textContent =
                "No members found.";

            resultsContainer.appendChild(
                empty
            );

            return;
        }


        members.forEach(
            member => {

                const row =
                    document.createElement(
                        "div"
                    );

                row.className =
                    "d-flex align-items-center gap-2 mb-2";


                const text =
                    document.createElement(
                        "span"
                    );

                text.className =
                    "flex-grow-1";

                text.textContent =
                    `${member.first_name} ` +
                    `${member.surname} ` +
                    `(${member.membership_number})`;


                const selectButton =
                    document.createElement(
                        "button"
                    );

                selectButton.type =
                    "button";

                selectButton.className =
                    "btn btn-sm btn-primary";

                selectButton.textContent =
                    "Select";


                selectButton.addEventListener(
                    "click",
                    () => selectMember(member)
                );


                row.appendChild(
                    text
                );

                row.appendChild(
                    selectButton
                );

                resultsContainer.appendChild(
                    row
                );
            }
        );

    } catch (error) {

        console.error(
            "Payment member search error:",
            error
        );

        resultsContainer.textContent =
            error.message ||
            "Unable to search for members.";
    }
}
