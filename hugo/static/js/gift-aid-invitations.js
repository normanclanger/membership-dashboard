import {
    requireLogin
} from "/js/auth.js";


const API_BASE =
    String(window.API_BASE_URL);


const membershipNumbers =
    document.getElementById(
        "membership-numbers"
    );


const checkButton =
    document.getElementById(
        "check-button"
    );


const checkMessage =
    document.getElementById(
        "check-message"
    );


const errorMessage =
    document.getElementById(
        "error-message"
    );


const resultsSection =
    document.getElementById(
        "results-section"
    );


const resultsContainer =
    document.getElementById(
        "results"
    );


const generationMessage =
    document.getElementById(
        "generation-message"
    );


const generateButton =
    document.getElementById(
        "generate-button"
    );


const generatedSection =
    document.getElementById(
        "generated-section"
    );


const commaDelimitedOutput =
    document.getElementById(
        "comma-delimited-output"
    );


const copyAllButton =
    document.getElementById(
        "copy-all-button"
    );


let checkedMembershipNumbers = [];


/* =====================================================
Messages
===================================================== */

function showError(message) {

    errorMessage.textContent =
        message;

    errorMessage.hidden =
        false;

}


function clearError() {

    errorMessage.textContent =
        "";

    errorMessage.hidden =
        true;

}


function showCheckMessage(message) {

    checkMessage.textContent =
        message;

    checkMessage.hidden =
        false;

}


function clearCheckMessage() {

    checkMessage.textContent =
        "";

    checkMessage.hidden =
        true;

}


/* =====================================================
Read membership numbers
===================================================== */

function getMembershipNumbers() {

    return membershipNumbers.value
        .split(/\r?\n/)
        .map(
            value => value.trim()
        )
        .filter(
            value => value !== ""
        );

}


/* =====================================================
State descriptions
===================================================== */

function stateDescription(result) {

    switch (result.state) {

        case "EXISTING_DECLARATION":

            return "Existing Gift Aid declaration";


        case "NO_DECLARATION":

            return "No Gift Aid declaration";


        case "CANCELLED":

            return "Declaration cancelled";


        case "DECLINED":

            return "Gift Aid previously declined";


        case "COVERED_ELSEWHERE":

            return "Recorded as covered by another declaration";


        case "PENDING_REVIEW":

            return "Pending administrative review";


        default:

            return result.state ||
                "Unknown";

    }

}


/* =====================================================
Display check results
===================================================== */

function displayResults(results) {

    resultsContainer.innerHTML =
        "";

    results.forEach(
        result => {

            const row =
                document.createElement(
                    "div"
                );

            row.className =
                "border rounded p-3 mb-3";


            const name =
                document.createElement(
                    "div"
                );

            name.className =
                "fw-bold";

            name.textContent =
                `${result.first_name} ` +
                `${result.surname}`;

            row.appendChild(
                name
            );


            const membership =
                document.createElement(
                    "div"
                );

            membership.textContent =
                `Membership number: ` +
                `${result.membership_number}`;

            row.appendChild(
                membership
            );


            const state =
                document.createElement(
                    "div"
                );

            state.textContent =
                `Gift Aid status: ` +
                `${stateDescription(result)}`;

            row.appendChild(
                state
            );


            if (
                result.gift_aid_reference !==
                null &&
                result.gift_aid_reference !==
                undefined
            ) {

                const reference =
                    document.createElement(
                        "div"
                    );

                reference.textContent =
                    `Gift Aid reference: ` +
                    `${result.gift_aid_reference}`;

                row.appendChild(
                    reference
                );

            }


            resultsContainer.appendChild(
                row
            );

        }
    );

}


/* =====================================================
Check members
===================================================== */

async function checkMembers() {

    clearError();

    clearCheckMessage();


    resultsSection.hidden =
        true;

    generatedSection.hidden =
        true;

    generationMessage.hidden =
        true;

    generateButton.disabled =
        true;


    const numbers =
        getMembershipNumbers();


    if (numbers.length === 0) {

        showError(
            "Please enter at least one membership number."
        );

        return;

    }


    checkButton.disabled =
        true;

    checkButton.textContent =
        "Checking...";


    try {

        const user =
            await requireLogin();

        if (!user) {
            return;
        }


        const response =
            await fetch(
                `${API_BASE}/api/gift-aid/admin/invitations/check`,
                {
                    method: "POST",

                    headers: {
                        "Authorization":
                            `Bearer ${user.access_token}`,

                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        membership_numbers:
                            numbers
                    })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.message ||
                data.error ||
                `HTTP ${response.status}`
            );

        }


        checkedMembershipNumbers =
            numbers;


        displayResults(
            data.results || []
        );


        resultsSection.hidden =
            false;


        if (
            data.status ===
            "READY"
        ) {

            showCheckMessage(
                "All members are ready for invitation generation."
            );

            generateButton.disabled =
                false;

        } else {

            showCheckMessage(
                data.message ||
                "Invitation generation is blocked."
            );

            generationMessage.textContent =
                "Resolve the pending Gift Aid review(s) before generating invitations.";

            generationMessage.hidden =
                false;

        }

    } catch (error) {

        console.error(
            "Gift Aid invitation check error:",
            error
        );

        showError(
            error.message ||
            "Unable to check members."
        );

    } finally {

        checkButton.disabled =
            false;

        checkButton.textContent =
            "Check members";

    }

}


/* =====================================================
Invitation wording
===================================================== */

function buildInvitationText(
    invitation
) {

    switch (
        invitation.state
    ) {

        case "EXISTING_DECLARATION":

            return (
			    "The Suffolk Guild hold an existing declaration linked to your name.  " +
                "Please use the link below to review " +
                "your existing Gift Aid declaration and " +
                "confirm that the information is still " +
                "correct, or update it if necessary."
            );


        case "NO_DECLARATION":

            return (
			    "The Suffolk Guild does not hold any information about your gift-aid wishes.  " +
                "Please use the link below to inform us " +
                "of your status. You can make a new " +
                "declaration, confirm that you do not want " +
                "to make a declaration, or request to be " +
                "covered by another person's declaration."
            );


        case "CANCELLED":

            return (
                "The Suffolk Guild records show that your previous Gift Aid " +
                "declaration has been cancelled. You do not need " +
                "to do anything unless you would like to reinstate " +
                "your Gift Aid declaration or request to be covered " +
                "by another person's declaration. If this is the " +
                "case, please use the link below."
            );


        case "DECLINED":

            return (
                "The Suffolk Guild records show that you previously declined " +
                "to make a Gift Aid declaration. If you would now " +
                "like to make a declaration, or request to be " +
                "covered by another person's declaration, please " +
                "use the link below."
            );


        case "COVERED_ELSEWHERE":

            return (
                "The Suffolk Guild records show that you are currently recorded " +
                "as being covered by another person's Gift Aid " +
                "declaration, opposed to having your own declaration. Please use the link below if you " +
                "need to review or update your Gift Aid status."
            );


        default:

            return (
                "Please use the link below to review your " +
                "Gift Aid information."
            );

    }

}


/* =====================================================
Build combined output
===================================================== */

function buildCommaDelimitedOutput(
    invitations
) {

    return invitations
        .map(
            invitation => {

                const text =
                    buildInvitationText(
                        invitation
                    );


                const singleLineText =
                    text
                        .replace(
                            /\r?\n/g,
                            " "
                        )
                        .replace(
                            /\s+/g,
                            " "
                        )
                        .trim();


                return (
                    `${invitation.membership_number},` +
                    `"${singleLineText}",` +
                    `${invitation.url}`
                );

            }
        )
        .join("\n");

}


/* =====================================================
Display generated invitations
===================================================== */

function displayGeneratedInvitations(
    invitations
) {

    commaDelimitedOutput.value =
        buildCommaDelimitedOutput(
            invitations
        );


    generatedSection.hidden =
        false;

}


/* =====================================================
Generate invitations
===================================================== */

async function generateInvitations() {

    clearError();


    generationMessage.hidden =
        true;


    if (
        checkedMembershipNumbers.length ===
        0
    ) {

        showError(
            "Please check the members before generating invitations."
        );

        return;

    }


    generateButton.disabled =
        true;

    generateButton.textContent =
        "Generating...";


    try {

        const user =
            await requireLogin();

        if (!user) {
            return;
        }


        const response =
            await fetch(
                `${API_BASE}/api/gift-aid/admin/invitations/generate`,
                {
                    method: "POST",

                    headers: {
                        "Authorization":
                            `Bearer ${user.access_token}`,

                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        membership_numbers:
                            checkedMembershipNumbers
                    })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.message ||
                data.error ||
                `HTTP ${response.status}`
            );

        }


        if (
            data.status !==
            "CREATED"
        ) {

            throw new Error(
                data.message ||
                "Invitations were not created."
            );

        }


        displayGeneratedInvitations(
            data.invitations || []
        );


    } catch (error) {

        console.error(
            "Gift Aid invitation generation error:",
            error
        );

        showError(
            error.message ||
            "Unable to generate Gift Aid invitations."
        );

    } finally {

        generateButton.disabled =
            false;

        generateButton.textContent =
            "Generate invitations";

    }

}


/* =====================================================
Copy all
===================================================== */

async function copyAllInvitations() {

    try {

        await navigator.clipboard.writeText(
            commaDelimitedOutput.value
        );

        copyAllButton.textContent =
            "Copied!";

        setTimeout(
            () => {

                copyAllButton.textContent =
                    "Copy all";

            },
            2000
        );

    } catch (error) {

        console.error(
            "Unable to copy invitation output:",
            error
        );

        showError(
            "Unable to copy the invitation list."
        );

    }

}


/* =====================================================
Event handlers
===================================================== */

checkButton.addEventListener(
    "click",
    checkMembers
);


generateButton.addEventListener(
    "click",
    generateInvitations
);


copyAllButton.addEventListener(
    "click",
    copyAllInvitations
);

