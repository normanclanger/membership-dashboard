import { requireLogin } from "/js/auth.js";

const API_BASE =
    "https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com/api";

const ALLOWED_GROUPS = [
    "PaymentAdmin",
    "ApplicationAdmin"
];


function getGroups(user) {

    const groups =
        user?.profile?.["cognito:groups"];

    if (!groups) {
        return [];
    }

    return Array.isArray(groups)
        ? groups
        : [groups];
}


function userCanManagePayments(user) {

    const groups =
        getGroups(user);

    return groups.some(group =>
        ALLOWED_GROUPS.includes(group)
    );
}


function showError(message) {

    const error =
        document.querySelector(
            "#payment-imports-error"
        );

    error.textContent =
        message;

    error.hidden =
        false;
}


function formatDate(value) {

    if (!value) {
        return "—";
    }

    return new Date(value)
        .toLocaleDateString(
            "en-GB"
        );
}


function statusLabel(status) {

    switch (status) {

        case "IN_PROGRESS":
            return "In progress";

        case "PARTIALLY_COMMITTED":
            return "Partially committed";

        case "COMPLETE":
            return "Complete";

        default:
            return status;
    }
}


async function loadImports(user) {

    const response =
        await fetch(
            `${API_BASE}/payment-imports`,
            {
                headers: {
                    Authorization:
                        `Bearer ${user.access_token}`
                }
            }
        );

    if (!response.ok) {

        throw new Error(
            `API returned ${response.status}`
        );
    }

    return response.json();
}


function displayImports(data) {

    const tbody =
        document.querySelector(
            "#payment-imports-table-body"
        );

    tbody.innerHTML = "";

    const imports =
        data.imports || [];

    if (imports.length === 0) {

        const row =
            document.createElement("tr");

        row.innerHTML = `
            <td colspan="4">
                No payment imports found.
            </td>
        `;

        tbody.appendChild(row);

        return;
    }

    imports.forEach(paymentImport => {

        const row =
            document.createElement("tr");

        row.innerHTML = `
            <td>
                <a href="/payments/import?id=${paymentImport.id}">
                    #${paymentImport.id}
                </a>
            </td>

            <td>
                ${formatDate(
                    paymentImport.created_at
                )}
            </td>

            <td>
                ${paymentImport.created_by || "—"}
            </td>

            <td>
                ${statusLabel(
                    paymentImport.status
                )}
            </td>
        `;

        tbody.appendChild(row);
    });
}


document.addEventListener(
    "DOMContentLoaded",
    async () => {

        try {

            const user =
                await requireLogin();

            if (!user) {
                return;
            }

            if (!userCanManagePayments(user)) {

                showError(
                    "You do not have permission to manage payment imports."
                );

                return;
            }

            const data =
                await loadImports(user);

            displayImports(data);

            const newImportButton =
                document.querySelector(
                    "#new-payment-import-button"
                );

            newImportButton.addEventListener(
                "click",
                () => {

                    window.location.href =
                        "/payments/imports/new/";
                }
            );

        } catch (error) {

            console.error(error);

            showError(
                "Unable to load payment imports."
            );
        }
    }
);
