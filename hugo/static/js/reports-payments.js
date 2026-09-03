
import {
    requireLogin
} from "/js/auth.js";

import {
    downloadTableAsCsv
} from "/js/csv.js";

const API_BASE = `${window.API_BASE_URL}`;


const yearSelect =
    document.querySelector(
        "#payment-year"
    );


const districtSelect =
    document.querySelector(
        "#payment-district"
    );


const loadButton =
    document.querySelector(
        "#load-payment-report"
    );


const reportBody =
    document.querySelector(
        "#payment-report-body"
    );


const reportHeading =
    document.querySelector(
        "#payment-report-heading"
    );


const subscriptionsTotal =
    document.querySelector(
        "#payment-report-subscriptions-total"
    );


const giftsTotal =
    document.querySelector(
        "#payment-report-gifts-total"
    );


const totalAmount =
    document.querySelector(
        "#payment-report-total"
    );


const emptyMessage =
    document.querySelector(
        "#payment-report-empty"
    );


const error =
    document.querySelector(
        "#reports-payments-error"
    );


let payments = [];

let sortColumn = "payment_date";

let sortDirection = "asc";


function showError(message) {

    error.textContent =
        message;

    error.hidden =
        false;
}


function clearError() {

    error.textContent =
        "";

    error.hidden =
        true;
}


function formatCurrency(value) {

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


function populateYears() {

    const currentYear =
        new Date().getFullYear();


    yearSelect.innerHTML =
        "";


    for (
        let year = currentYear+2;
        year >= 2025;
        year--
    ) {

        const option =
            document.createElement(
                "option"
            );


        option.value =
            year;

        option.textContent =
            year;


        yearSelect.appendChild(
            option
        );
    }
}


function readUrlParameters() {

    const params =
        new URLSearchParams(
            window.location.search
        );


    const year =
        params.get(
            "calendar_year"
        );


    const district =
        params.get(
            "district"
        );


    if (year) {

        yearSelect.value =
            year;
    }


    if (district) {

        districtSelect.value =
            district;
    }
}


function updateUrl() {

    const params =
        new URLSearchParams();


    params.set(
        "calendar_year",
        yearSelect.value
    );


    if (
        districtSelect.value
    ) {

        params.set(
            "district",
            districtSelect.value
        );
    }


    const newUrl =
        `${window.location.pathname}?${params.toString()}`;


    window.history.replaceState(
        {},
        "",
        newUrl
    );
}


function getSortValue(
    payment,
    column
) {

    switch (column) {

        case "payment_date":

            return payment.payment_date;


        case "name":

            return (
                `${payment.surname} ${payment.first_name}`
            ).toLowerCase();
			
		case "membership_number":

            return (
                payment.membership_number || ""
				).toLowerCase();	


        case "tower":

            return (
                payment.tower_name || ""
            ).toLowerCase();


        case "district":

            return (
                payment.district_code || ""
            ).toLowerCase();


        case "subscription":

            return Number(
                payment.subscription_amount
            );


        case "gift":

            return Number(
                payment.gift_amount
            );


        case "total":

            return Number(
                payment.total
            );


        default:

            return "";
    }
}


function sortPayments() {

    payments.sort(
        (a, b) => {

            const aValue =
                getSortValue(
                    a,
                    sortColumn
                );


            const bValue =
                getSortValue(
                    b,
                    sortColumn
                );


            if (
                aValue <
                bValue
            ) {

                return sortDirection === "asc"
                    ? -1
                    : 1;
            }


            if (
                aValue >
                bValue
            ) {

                return sortDirection === "asc"
                    ? 1
                    : -1;
            }


            return 0;
        }
    );
}


function updateSortIndicators() {

    const headings =
        document.querySelectorAll(
            "#payment-report-table th[data-sort]"
        );


    headings.forEach(
        heading => {

            const column =
                heading.dataset.sort;


            const originalText =
                heading.dataset.label ||
                heading.textContent
                    .replace(
                        " ▲",
                        ""
                    )
                    .replace(
                        " ▼",
                        ""
                    )
                    .trim();


            heading.dataset.label =
                originalText;


            if (
                column === sortColumn
            ) {

                heading.textContent =
                    `${originalText} ${
                        sortDirection === "asc"
                            ? "▲"
                            : "▼"
                    }`;

            } else {

                heading.textContent =
                    originalText;
            }
        }
    );
}


function renderPayments() {

    reportBody.innerHTML =
        "";


    if (
        payments.length === 0
    ) {

        emptyMessage.hidden =
            false;

        reportHeading.hidden =
            false;

        reportHeading.textContent =
            `No payments found for ${yearSelect.value}.`;

        subscriptionsTotal.textContent =
            formatCurrency(0);

        giftsTotal.textContent =
            formatCurrency(0);

        totalAmount.textContent =
            formatCurrency(0);

        return;
    }


    emptyMessage.hidden =
        true;


    const district =
        districtSelect.value;


    if (district) {

        reportHeading.textContent =
            `Payments for ${district} — membership year ${yearSelect.value}`;

    } else {

        reportHeading.textContent =
            `All payments for membership year ${yearSelect.value}`;
    }


    reportHeading.hidden =
        false;


    let subscriptions =
        0;

    let gifts =
        0;

    let total =
        0;


    payments.forEach(
        payment => {

            subscriptions +=
                Number(
                    payment.subscription_amount
                );


            gifts +=
                Number(
                    payment.gift_amount
                );


            total +=
                Number(
                    payment.total
                );


            const row =
                document.createElement(
                    "tr"
                );


            const member =
                `${payment.membership_number} — ${payment.first_name} ${payment.surname}`;


            row.innerHTML = `
                <td>
                    ${payment.payment_date}
                </td>

                <td>
                    ${payment.membership_number}
                </td>

                <td>
                    ${payment.first_name} ${payment.surname}
                </td>

                <td>
                    ${payment.tower_name}
                </td>

                <td>
                    ${payment.district_code}
                </td>

                <td
                    class="text-end"
                    data-csv-value="${Number(payment.subscription_amount).toFixed(2)}"
                >
                    ${formatCurrency(
                        payment.subscription_amount
                    )}
                </td>

                <td
                    class="text-end"
                    data-csv-value="${Number(payment.gift_amount).toFixed(2)}"
                >
                    ${formatCurrency(
                        payment.gift_amount
                    )}
                </td>

                <td
                    class="text-end"
                    data-csv-value="${Number(payment.total).toFixed(2)}"
                >
                    ${formatCurrency(
                        payment.total
                    )}
                </td>
            `;


            reportBody.appendChild(
                row
            );
        }
    );


    subscriptionsTotal.textContent =
        formatCurrency(
            subscriptions
        );


    giftsTotal.textContent =
        formatCurrency(
            gifts
        );


    totalAmount.textContent =
        formatCurrency(
            total
        );


    updateSortIndicators();
}


async function loadReport() {

    clearError();


    reportBody.innerHTML =
        "";


    emptyMessage.hidden =
        true;


    try {

        const user =
            await requireLogin();


        if (!user) {

            return;
        }


        updateUrl();


        const year =
            yearSelect.value;


        const district =
            districtSelect.value;


        let url =
            `${API_BASE}/api/reports/payments/list?calendar_year=${encodeURIComponent(year)}`;


        if (district) {

            url +=
                `&district=${encodeURIComponent(district)}`;
        }


        loadButton.disabled =
            true;


        loadButton.textContent =
            "Loading...";


        const response =
            await fetch(
                url,
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
                "Unable to load payment report."
            );
        }


        payments =
            data.payments || [];


        sortPayments();

        renderPayments();


    } catch (err) {

        console.error(
            "Payment report error:",
            err
        );


        showError(
            err.message ||
            "Unable to load payment report."
        );


    } finally {

        loadButton.disabled =
            false;

        loadButton.textContent =
            "View report";
    }
}


document
    .querySelectorAll(
        "#payment-report-table th[data-sort]"
    )
    .forEach(
        heading => {

            heading.addEventListener(
                "click",
                () => {

                    const column =
                        heading.dataset.sort;


                    if (
                        column ===
                        sortColumn
                    ) {

                        sortDirection =
                            sortDirection === "asc"
                                ? "desc"
                                : "asc";

                    } else {

                        sortColumn =
                            column;

                        sortDirection =
                            "asc";
                    }


                    sortPayments();

                    renderPayments();
                }
            );
        }
    );


loadButton.addEventListener(
    "click",
    loadReport
);

const downloadButton =
    document.querySelector(
        "#payment-report-download"
    );


if (downloadButton) {

    downloadButton.addEventListener(
        "click",
        () => {

            const table =
                document.querySelector(
                    "#payment-report-table"
                );


            try {

                downloadTableAsCsv(
                    table,
                    "payment-report.csv"
                );

            } catch (err) {

                console.error(
                    "Payment report CSV export error:",
                    err
                );

                window.alert(
                    err.message ||
                    "Unable to download payment report."
                );
            }
        }
    );
}


populateYears();

readUrlParameters();

loadReport();

