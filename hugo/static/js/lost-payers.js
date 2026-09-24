import {
    requireLogin
} from "/js/auth.js";

import {
    downloadTableAsCsv
} from "/js/csv.js";

const API_BASE =
    `${window.API_BASE_URL}`;


const yearSelect =
    document.querySelector(
        "#lost-payers-year"
    );


const districtSelect =
    document.querySelector(
        "#lost-payers-district"
    );


const memberSearch =
    document.querySelector(
        "#lost-payers-member-search"
    );


const loadButton =
    document.querySelector(
        "#load-lost-payers-report"
    );


const reportBody =
    document.querySelector(
        "#lost-payers-report-body"
    );


const reportHeading =
    document.querySelector(
        "#lost-payers-report-heading"
    );


const emptyMessage =
    document.querySelector(
        "#lost-payers-report-empty"
    );


const error =
    document.querySelector(
        "#lost-payers-error"
    );


let members = [];

let sortColumn =
    "name";

let sortDirection =
    "asc";


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


function populateYears() {

    const currentYear =
        new Date().getFullYear();


    yearSelect.innerHTML =
        "";


    for (
        let year = currentYear + 2;
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
            district.toUpperCase();
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
    member,
    column
) {

    switch (column) {

        case "membership_number":

            return (
                member.membership_number || ""
            ).toLowerCase();


        case "name":

            return (
                `${member.surname} ${member.first_name}`
            ).toLowerCase();


        case "membership_class":

            return (
                member.membership_class || ""
            ).toLowerCase();


        case "full_member_type":

            return (
                member.full_member_type || ""
            ).toLowerCase();


        case "tower":

            return (
                member.tower_name || ""
            ).toLowerCase();


        case "district":

            return (
                member.district || ""
            ).toLowerCase();


        default:

            return "";
    }
}


function sortMembers() {

    const secondaryColumn =
        "name";


    members.sort(
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


            // Primary sort

            if (aValue < bValue) {

                return sortDirection === "asc"
                    ? -1
                    : 1;
            }


            if (aValue > bValue) {

                return sortDirection === "asc"
                    ? 1
                    : -1;
            }


            // Primary values are equal:
            // secondary sort by name,
            // always ascending

            const aSecondary =
                getSortValue(
                    a,
                    secondaryColumn
                );


            const bSecondary =
                getSortValue(
                    b,
                    secondaryColumn
                );


            if (aSecondary < bSecondary) {

                return -1;
            }


            if (aSecondary > bSecondary) {

                return 1;
            }


            return 0;
        }
    );
}


function updateSortIndicators() {

    const headings =
        document.querySelectorAll(
            "#lost-payers-report-table th[data-sort]"
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


function getFilteredMembers() {

    const search =
        memberSearch
            ? memberSearch.value
                .trim()
                .toLowerCase()
            : "";


    if (!search) {

        return members;
    }


    return members.filter(
        member => {

            const membershipNumber =
                String(
                    member.membership_number || ""
                ).toLowerCase();


            const firstName =
                String(
                    member.first_name || ""
                ).toLowerCase();


            const surname =
                String(
                    member.surname || ""
                ).toLowerCase();


            const memberName =
                `${firstName} ${surname}`;


            return (
                membershipNumber.includes(
                    search
                ) ||
                firstName.includes(
                    search
                ) ||
                surname.includes(
                    search
                ) ||
                memberName.includes(
                    search
                )
            );
        }
    );
}


function renderMembers() {

    reportBody.innerHTML =
        "";


    const filteredMembers =
        getFilteredMembers();


    if (
        filteredMembers.length === 0
    ) {

        emptyMessage.hidden =
            false;

        reportHeading.hidden =
            false;

        reportHeading.textContent =
            `No delinquent payers found for ${yearSelect.value}.`;

        return;
    }


    emptyMessage.hidden =
        true;


    const district =
        districtSelect.value;


    if (district) {

        reportHeading.textContent =
            `${filteredMembers.length} delinquent payer${
                filteredMembers.length === 1
                    ? ""
                    : "s"
            } in ${district} — payment year ${yearSelect.value}`;

    } else {

        reportHeading.textContent =
            `${filteredMembers.length} delinquent payer${
                filteredMembers.length === 1
                    ? ""
                    : "s"
            } — payment year ${yearSelect.value}`;
    }


    reportHeading.hidden =
        false;


    filteredMembers.forEach(
        member => {

            const row =
                document.createElement(
                    "tr"
                );


            row.innerHTML = `
                <td>
                    ${member.membership_number || ""}
                </td>

                <td>
                    ${member.first_name || ""}
                    ${member.surname || ""}
                </td>

                <td>
                    ${member.membership_class || ""}
                </td>

                <td>
                    ${member.full_member_type || ""}
                </td>

                <td>
                    ${member.tower_name || ""}
                </td>

                <td>
                    ${member.district || ""}
                </td>
            `;


            reportBody.appendChild(
                row
            );
        }
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
            `${API_BASE}/api/reports/payments/lost-payers?calendar_year=${encodeURIComponent(year)}`;


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
                "Unable to load delinquent payer report."
            );
        }


        members =
            data.members || [];


        sortMembers();

        renderMembers();


    } catch (err) {

        console.error(
            "Delinquent payer report error:",
            err
        );


        showError(
            err.message ||
            "Unable to load delinquent payer report."
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
        "#lost-payers-report-table th[data-sort]"
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


                    sortMembers();

                    renderMembers();
                }
            );
        }
    );


if (memberSearch) {

    memberSearch.addEventListener(
        "input",
        () => {

            renderMembers();

        }
    );
}


loadButton.addEventListener(
    "click",
    loadReport
);


const downloadButton =
    document.querySelector(
        "#lost-payers-report-download"
    );


if (downloadButton) {

    downloadButton.addEventListener(
        "click",
        () => {

            const table =
                document.querySelector(
                    "#lost-payers-report-table"
                );


            try {

                downloadTableAsCsv(
                    table,
                    "delinquent-payers.csv"
                );

            } catch (err) {

                console.error(
                    "Delinquent payer CSV export error:",
                    err
                );


                window.alert(
                    err.message ||
                    "Unable to download delinquent payer report."
                );
            }
        }
    );
}


populateYears();

readUrlParameters();

loadReport();