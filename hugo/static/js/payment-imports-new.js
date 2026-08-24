import { requireLogin } from "/js/auth.js";

const API_BASE =
"https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com/api";

let parsedLines = [];

/*

* ============================================================
* Show error
* ============================================================
  */

function showError(message) {


const error =
    document.querySelector(
        "#payment-import-new-error"
    );

error.textContent =
    message;

error.hidden =
    false;

error.scrollIntoView({
    behavior: "smooth",
    block: "start"
});


}

/*

* ============================================================
* Clear error
* ============================================================
  */

function clearError() {


const error =
    document.querySelector(
        "#payment-import-new-error"
    );

error.textContent =
    "";

error.hidden =
    true;


}

/*

* ============================================================
* Parse spreadsheet data
* ============================================================
  */

function parseSpreadsheet(text) {


const rows =
    text
        .split(/\r?\n/)
        .map(row => row.trim())
        .filter(row => row !== "");

if (rows.length === 0) {

    throw new Error(
        "Please paste some statement lines first."
    );
}

const lines = [];

rows.forEach((row, index) => {

    const columns =
        row.split("\t");

    if (columns.length < 5) {

        throw new Error(
            `Line ${index + 1} does not contain `
            + "the expected five columns."
        );
    }

    const reference =
        columns[0].trim();

    const date =
        columns[1].trim();

    const amount =
        columns[2].trim();

    const type =
        columns[3].trim();

    const description =
        columns
            .slice(4)
            .join("\t")
            .trim();

    if (!reference) {

        throw new Error(
            `Line ${index + 1}: reference is empty.`
        );
    }

    if (!date) {

        throw new Error(
            `Line ${index + 1}: date is empty.`
        );
    }

    if (!amount) {

        throw new Error(
            `Line ${index + 1}: amount is empty.`
        );
    }

    if (!type) {

        throw new Error(
            `Line ${index + 1}: type is empty.`
        );
    }

    if (!description) {

        throw new Error(
            `Line ${index + 1}: description is empty.`
        );
    }

    const numericAmount =
        Number(
            amount.replace(/,/g, "")
        );

    if (!Number.isFinite(numericAmount)) {

        throw new Error(
            `Line ${index + 1}: amount is not a number.`
        );
    }

    /*
     * Convert DD/MM/YYYY into YYYY-MM-DD.
     */

    const dateParts =
        date.split("/");

    if (dateParts.length !== 3) {

        throw new Error(
            `Line ${index + 1}: date must be DD/MM/YYYY.`
        );
    }

    const [
        day,
        month,
        year
    ] = dateParts;

    if (
        day.length !== 2 ||
        month.length !== 2 ||
        year.length !== 4
    ) {

        throw new Error(
            `Line ${index + 1}: invalid date.`
        );
    }

    const isoDate =
        `${year}-${month}-${day}`;

    lines.push({

        statement_reference:
            reference,

        payment_date:
            isoDate,

        statement_amount:
            numericAmount.toFixed(2),

        statement_type:
            type,

        description:
            description,

        /*
         * We deliberately don't expose IGNORE
         * in the new-import UI.
         */

        action:
            "IMPORT"
    });
});

return lines;


}

/*

* ============================================================
* Display preview
* ============================================================
  */

function displayPreview(lines) {


const preview =
    document.querySelector(
        "#payment-import-preview"
    );

const tbody =
    document.querySelector(
        "#payment-import-preview-body"
    );

const count =
    document.querySelector(
        "#payment-import-preview-count"
    );

tbody.innerHTML = "";

lines.forEach(line => {

    const row =
        document.createElement("tr");

    row.innerHTML = `
        <td>
            ${line.statement_reference}
        </td>

        <td>
            ${formatDisplayDate(
                line.payment_date
            )}
        </td>

        <td>
            £${line.statement_amount}
        </td>

        <td>
            ${line.statement_type}
        </td>

        <td>
            ${line.description}
        </td>
    `;

    tbody.appendChild(row);
});

count.textContent =
    `${lines.length} line${lines.length === 1 ? "" : "s"} ready to import.`;

preview.hidden =
    false;

preview.scrollIntoView({
    behavior: "smooth",
    block: "start"
});


}

/*

* ============================================================
* Display date
* ============================================================
  */

function formatDisplayDate(value) {


const [
    year,
    month,
    day
] = value.split("-");

return `${day}/${month}/${year}`;


}

/*

* ============================================================
* Create payment import
* ============================================================
  */

async function createPaymentImport(user) {


/*
 * First create the empty payment import.
 */

const importResponse =
    await fetch(
        `${API_BASE}/payment-imports`,
        {
            method: "POST",

            headers: {
                Authorization:
                    `Bearer ${user.access_token}`
            }
        }
    );

if (!importResponse.ok) {

    throw new Error(
        `Unable to create payment import `
        + `(${importResponse.status})`
    );
}

const importData =
    await importResponse.json();

const importId =
    importData.import?.id;

if (!importId) {

    throw new Error(
        "Payment import was created but no import ID was returned."
    );
}


/*
 * Now create all statement lines in one request.
 */

const linesResponse =
    await fetch(
        `${API_BASE}/payment-imports/${importId}/lines`,
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
                    lines:
                        parsedLines
                })
        }
    );

if (!linesResponse.ok) {

    throw new Error(
        `Unable to create payment import lines `
        + `(${linesResponse.status})`
    );
}


/*
 * Everything succeeded.
 *
 * Go to the normal payment import page.
 */

window.location.href =
    `/payments/import?id=${importId}`;


}

/*

* ============================================================
* Page
* ============================================================
  */

document.addEventListener(
"DOMContentLoaded",
async () => {


    try {

        const user =
            await requireLogin();

        if (!user) {
            return;
        }


        /*
         * Preview button
         */

        const previewButton =
            document.querySelector(
                "#preview-payment-import"
            );

        previewButton.addEventListener(
            "click",
            () => {

                clearError();

                try {

                    const textarea =
                        document.querySelector(
                            "#payment-import-paste"
                        );

                    parsedLines =
                        parseSpreadsheet(
                            textarea.value
                        );

                    displayPreview(
                        parsedLines
                    );

                } catch (error) {

                    console.error(error);

                    showError(
                        error.message
                    );
                }
            }
        );


        /*
         * Create/import button
         */

        const createButton =
            document.querySelector(
                "#create-payment-import"
            );

        createButton.addEventListener(
            "click",
            async () => {

                clearError();

                if (!parsedLines.length) {

                    showError(
                        "Please preview the statement lines first."
                    );

                    return;
                }

                createButton.disabled =
                    true;

                createButton.textContent =
                    "Importing...";

                try {

                    await createPaymentImport(
                        user
                    );

                } catch (error) {

                    console.error(error);

                    createButton.disabled =
                        false;

                    createButton.textContent =
                        "Import";

                    showError(
                        "Unable to create payment import. "
                        + error.message
                    );
                }
            }
        );


        /*
         * Cancel button
         */

        const cancelButton =
            document.querySelector(
                "#cancel-payment-import"
            );

        cancelButton.addEventListener(
            "click",
            () => {

                window.location.href =
                    "/payments/imports/";
            }
        );

    } catch (error) {

        console.error(error);

        showError(
            "Unable to load the new payment import page."
        );
    }
}


);
