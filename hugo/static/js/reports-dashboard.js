import {
    requireLogin
} from "/js/auth.js";


const API_BASE = `${window.API_BASE_URL}`;


const yearSelect =
    document.querySelector(
        "#payment-year"
    );


const summaryBody =
    document.querySelector(
        "#payment-summary-body"
    );


const subscriptionsTotal =
    document.querySelector(
        "#payment-summary-subscriptions-total"
    );




const giftsTotal =
    document.querySelector(
        "#payment-summary-gifts-total"
    );



const totalAmount =
    document.querySelector(
        "#payment-summary-total"
    );
	

const subscriptionsGiftAidEligibleTotal =
    document.querySelector(
        "#payment-summary-gift-aid-subs-total"
    );


const giftsGiftAidEligibleTotal =
    document.querySelector(
        "#payment-summary-gift-aid-gifts-total"
    );


const totalGiftAidEligibleTotal =
    document.querySelector(
        "#payment-summary-gift-aid-total"
    );


const error =
    document.querySelector(
        "#reports-dashboard-error"
    );


function showError(message) {

    error.textContent = message;
    error.hidden = false;
}


function clearError() {

    error.textContent = "";
    error.hidden = true;
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

    yearSelect.innerHTML = "";

    for (
        let year = currentYear;
        year >= 2025;
        year--
    ) {

        const option =
            document.createElement(
                "option"
            );

        option.value = year;
        option.textContent = year;

        yearSelect.appendChild(
            option
        );
    }
}


async function loadSummary() {

    clearError();

    summaryBody.innerHTML = "";

    subscriptionsTotal.textContent = "";
    subscriptionsGiftAidEligibleTotal.textContent = "";

    giftsTotal.textContent = "";
    giftsGiftAidEligibleTotal.textContent = "";

    totalAmount.textContent = "";
    totalGiftAidEligibleTotal.textContent = "";


    try {

        const user =
            await requireLogin();


        if (!user) {
            return;
        }


        const year =
            yearSelect.value;


        const response =
            await fetch(
                `${API_BASE}/api/reports/payments/summary?year=${year}`,
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
                "Unable to load payment summary."
            );
        }


        for (
            const district
            of data.districts
        ) {

            const row =
                document.createElement(
                    "tr"
                );


            row.innerHTML = `
                <td>
                    ${district.district_code}
                </td>

                <td class="text-end">
                    ${formatCurrency(
                        district.subscriptions
                    )}
                </td>


                <td class="text-end">
                    ${formatCurrency(
                        district.gifts
                    )}
                </td>

                <td class="text-end">
                    ${formatCurrency(
                        district.total
                    )}
                </td>
				
				
				<td class="text-end">
                    ${formatCurrency(
                        district.subscriptions_gift_aid_eligible
                    )}
                </td>

                <td class="text-end">
                    ${formatCurrency(
                        district.gifts_gift_aid_eligible
                    )}
                </td>



                <td class="text-end">
                    ${formatCurrency(
                        district.total_gift_aid_eligible
                    )}
                </td>
            `;


            summaryBody.appendChild(
                row
            );
        }


        subscriptionsTotal.textContent =
            formatCurrency(
                data.totals.subscriptions
            );


        subscriptionsGiftAidEligibleTotal.textContent =
            formatCurrency(
                data.totals.subscriptions_gift_aid_eligible
            );


        giftsTotal.textContent =
            formatCurrency(
                data.totals.gifts
            );


        giftsGiftAidEligibleTotal.textContent =
            formatCurrency(
                data.totals.gifts_gift_aid_eligible
            );


        totalAmount.textContent =
            formatCurrency(
                data.totals.total
            );


        totalGiftAidEligibleTotal.textContent =
            formatCurrency(
                data.totals.total_gift_aid_eligible
            );

    } catch (err) {

        console.error(
            "Payment summary error:",
            err
        );

        showError(
            err.message ||
            "Unable to load payment summary."
        );
    }
}


populateYears();


yearSelect.addEventListener(
    "change",
    loadSummary
);


loadSummary();
