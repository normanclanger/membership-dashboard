/*

* Gift Aid member-facing declaration
*
* This page is accessed using a one-time invitation token:
*
* /gift-aid/declaration/?token=...
*
* It does not require Cognito authentication.
*
* This page must NOT call the general members API.
  */

/* =====================================================
API
===================================================== */

const API_BASE =
String(window.API_BASE_URL);

/* =====================================================
Page elements
===================================================== */

const loading =
document.querySelector(
"#gift-aid-loading"
);

const errorMessage =
document.querySelector(
"#gift-aid-error"
);

const statusMessage =
document.querySelector(
"#gift-aid-status"
);

const declaration =
document.querySelector(
"#gift-aid-declaration"
);

const giftAidActions =
document.querySelector(
"#gift-aid-actions"
);

const cancelButton =
document.querySelector(
"#gift-aid-cancel"
);

const declineButton =
document.querySelector(
"#gift-aid-decline"
);

const coveredElsewhereButton =
document.querySelector(
"#gift-aid-covered-elsewhere"
);

const declarerName =
document.querySelector(
"#gift-aid-declarer-name"
);

const declarerAddressLine1 =
document.querySelector(
"#gift-aid-declarer-address-line-1"
);

const declarerAddressLine2 =
document.querySelector(
"#gift-aid-declarer-address-line-2"
);

const declarerPostcode =
document.querySelector(
"#gift-aid-declarer-postcode"
);

const declarerEmail =
document.querySelector(
"#gift-aid-declarer-email"
);

const referenceContainer =
document.querySelector(
"#gift-aid-reference-container"
);

const reference =
document.querySelector(
"#gift-aid-reference"
);

const coveredMembersElement =
document.querySelector(
"#gift-aid-covered-members"
);

const coveredMemberNumber =
document.querySelector(
"#gift-aid-covered-member-number"
);

const coveredMemberName =
document.querySelector(
"#gift-aid-covered-member-name"
);

const coveredMemberAddButton =
document.querySelector(
"#gift-aid-covered-member-add"
);

const declarationText =
document.querySelector(
"#gift-aid-declaration-text"
);

const affirmation =
document.querySelector(
"#gift-aid-affirmation"
);

const submitButton =
document.querySelector(
"#gift-aid-submit"
);

const successMessage =
document.querySelector(
"#gift-aid-success"
);

/* =====================================================
Data returned by the Gift Aid GET request
===================================================== */

let giftAidData = null;

let coveredMembers = [];

/* =====================================================
Get invitation token
===================================================== */

function getToken() {


const params =
    new URLSearchParams(
        window.location.search
    );

return params.get("token");


}

/* =====================================================
Show error
===================================================== */

function showError(message) {


errorMessage.textContent =
    message;

errorMessage.hidden =
    false;


}

/* =====================================================
Hide error
===================================================== */

function clearError() {


errorMessage.textContent =
    "";

errorMessage.hidden =
    true;


}

/* =====================================================
Display declaration status
===================================================== */

function displayDeclarationStatus(
data
) {


if (!statusMessage) {
    return;
}

const existingDeclaration =
    data.declaration;

if (!existingDeclaration) {

    statusMessage.textContent =
        "No declaration stored by Suffolk Guild";

    statusMessage.className =
        "alert alert-secondary mb-4";

    statusMessage.hidden =
        false;

    return;
}

const action =
    existingDeclaration.action;

const date =
    existingDeclaration.affirmed_date ||
    (
        existingDeclaration.recorded_at
            ? existingDeclaration.recorded_at.slice(0, 10)
            : ""
    );

if (action === "CANCELLED") {

    if (
        existingDeclaration.status ===
        "PENDING_REVIEW"
    ) {

        statusMessage.textContent =
            "Gift Aid declaration cancelled on " +
            date +
            " — pending administrative review";

        statusMessage.className =
            "alert alert-warning mb-4";

    } else {

        statusMessage.textContent =
            "Gift Aid declaration cancelled on " +
            date;

        statusMessage.className =
            "alert alert-info mb-4";
    }

} else if (action === "DECLINED") {

    statusMessage.textContent =
        "Gift Aid declined on " +
        date;

    statusMessage.className =
        "alert alert-info mb-4";

} else if (action === "COVERED_ELSEWHERE") {

    statusMessage.textContent =
        "Gift Aid information submitted on " +
        date +
        " — pending administrative review";

    statusMessage.className =
        "alert alert-warning mb-4";

} else if (action === "UPDATED") {

    statusMessage.textContent =
        "Last declaration updated " +
        date;

    statusMessage.className =
        "alert alert-info mb-4";

} else {

    statusMessage.textContent =
        "Last declaration affirmed " +
        date;

    statusMessage.className =
        "alert alert-info mb-4";
}

statusMessage.hidden =
    false;


}

/* =====================================================
Display action buttons
===================================================== */

function displayActionButtons(data) {


if (!giftAidActions) {
    return;
}

/*
 * The member is considered currently affirmed only
 * when the latest declaration is AFFIRMED or UPDATED,
 * is affirmed, and is confirmed.
 *
 * A CANCELLED, DECLINED or COVERED_ELSEWHERE record
 * therefore presents the "I don't want to Gift Aid"
 * option instead.
 */

const existingDeclaration =
    data.declaration;
	

const currentlyAffirmed =
    existingDeclaration &&
    (
        existingDeclaration.action === "AFFIRMED" ||
        existingDeclaration.action === "UPDATED"
    ) &&
    existingDeclaration.affirmed === true;

if (currentlyAffirmed) {

    cancelButton.hidden =
        false;

    declineButton.hidden =
        true;

} else {

    cancelButton.hidden =
        true;

    declineButton.hidden =
        false;
}

/*
 * Covered Elsewhere is always available.
 */

coveredElsewhereButton.hidden =
    false;

giftAidActions.hidden =
    false;


}

/* =====================================================
Display covered members
===================================================== */

function displayCoveredMembers(members) {


coveredMembers = Array.isArray(members)
    ? members.map(
        member => Object.assign({}, member)
    )
    : [];

renderCoveredMembers();


}

function renderCoveredMembers() {


coveredMembersElement.innerHTML =
    "";

if (!coveredMembers.length) {

    coveredMembersElement.innerHTML =
        "<p class=\"text-muted mb-0\">" +
        "No other Guild members are currently " +
        "recorded as covered by this declaration." +
        "</p>";

    return;
}

const list =
    document.createElement("div");

list.className =
    "list-group";

coveredMembers.forEach(
    function(member, index) {

        const item =
            document.createElement("div");

        item.className =
            "list-group-item d-flex justify-content-between align-items-center";

        const membershipNumber =
            member.membership_number || "";

        const firstName =
            member.first_name || "";

        const surname =
            member.surname || "";

        const name =
            (firstName + " " + surname).trim();

        const displayName =
            name ||
            member.name ||
            member.description ||
            "Guild member";

        const text =
            document.createElement("span");

        if (membershipNumber) {

            text.textContent =
                membershipNumber +
                " - " +
                displayName;

        } else {

            text.textContent =
                displayName;
        }

        const removeButton =
            document.createElement("button");

        removeButton.type =
            "button";

        removeButton.className =
            "btn btn-sm btn-outline-danger";

        removeButton.textContent =
            "Remove";

        removeButton.addEventListener(
            "click",
            function() {

                coveredMembers.splice(
                    index,
                    1
                );

                renderCoveredMembers();
            }
        );

        item.appendChild(text);

        item.appendChild(removeButton);

        list.appendChild(item);
    }
);

coveredMembersElement.appendChild(list);


}

function addCoveredMember() {


clearError();

const membershipNumber =
    coveredMemberNumber.value.trim();

const name =
    coveredMemberName.value.trim();

if (!membershipNumber && !name) {

    showError(
        "Please enter a membership number or name."
    );

    coveredMemberNumber.focus();

    return;
}

coveredMembers.push({

    membership_number:
        membershipNumber,

    name:
        name
});

coveredMemberNumber.value =
    "";

coveredMemberName.value =
    "";

renderCoveredMembers();


}

/* =====================================================
Display declaration data
===================================================== */

function displayDeclaration(
data
) {


giftAidData =
    data;

const member =
    data.member;

if (!member) {

    throw new Error(
        "The Gift Aid declaration does not contain a declarer."
    );
}

declarerName.value =
    (member.first_name + " " + member.surname).trim();

const existingDeclaration =
    data.declaration;

declarerAddressLine1.value =
    existingDeclaration &&
    existingDeclaration.declarer_address_line_1
        ? existingDeclaration.declarer_address_line_1
        : "";

declarerAddressLine2.value =
    existingDeclaration &&
    existingDeclaration.declarer_address_line_2
        ? existingDeclaration.declarer_address_line_2
        : "";

declarerPostcode.value =
    existingDeclaration &&
    existingDeclaration.declarer_postcode
        ? existingDeclaration.declarer_postcode
        : "";

declarerEmail.value =
    existingDeclaration &&
    existingDeclaration.email_address
        ? existingDeclaration.email_address
        : "";

displayDeclarationStatus(
    data
);

if (data.gift_aid_reference) {

    reference.textContent =
        data.gift_aid_reference;

    referenceContainer.hidden =
        false;

} else {

    referenceContainer.hidden =
        true;
}

displayCoveredMembers(
    data.covered_members || []
);

if (
    existingDeclaration &&
    existingDeclaration.declaration_text
) {

    declarationText.textContent =
        existingDeclaration.declaration_text;

} else if (
    data.wording &&
    data.wording.wording
) {

    declarationText.textContent =
        data.wording.wording;

} else {

    throw new Error(
        "No Gift Aid declaration wording was supplied."
    );
}

displayActionButtons(
    data
);


}

/* =====================================================
Load declaration
===================================================== */

async function loadDeclaration() {


const token =
    getToken();

if (!token) {

    throw new Error(
        "No Gift Aid invitation token was supplied."
    );
}

const response =
    await fetch(
        API_BASE +
        "/api/gift-aid/declaration?token=" +
        encodeURIComponent(token)
    );

const data =
    await response.json();

if (!response.ok) {

    throw new Error(
        data.error ||
        "Unable to load the Gift Aid declaration."
    );
}

displayDeclaration(
    data
);

loading.hidden =
    true;

declaration.hidden =
    false;


}

/* =====================================================
Validate ordinary declaration form
===================================================== */

function validateForm() {


clearError();

if (
    !declarerAddressLine1.value.trim()
) {

    showError(
        "Please enter the first line of your home address."
    );

    declarerAddressLine1.focus();

    return false;
}

if (
    !declarerPostcode.value.trim()
) {

    showError(
        "Please enter your postcode."
    );

    declarerPostcode.focus();

    return false;
}

if (
    !declarerEmail.value.trim()
) {

    showError(
        "Please enter your email address."
    );

    declarerEmail.focus();

    return false;
}

if (
    !declarerEmail.checkValidity()
) {

    showError(
        "Please enter a valid email address."
    );

    declarerEmail.focus();

    return false;
}

if (!affirmation.checked) {

    showError(
        "Please tick the box to confirm and submit the Gift Aid declaration."
    );

    affirmation.focus();

    return false;
}

return true;


}

/* =====================================================
Validate details required by alternative actions
===================================================== */

function validateActionDetails() {


clearError();

if (
    !declarerAddressLine1.value.trim()
) {

    showError(
        "Please enter the first line of your home address."
    );

    declarerAddressLine1.focus();

    return false;
}

if (
    !declarerPostcode.value.trim()
) {

    showError(
        "Please enter your postcode."
    );

    declarerPostcode.focus();

    return false;
}

if (
    !declarerEmail.value.trim()
) {

    showError(
        "Please enter your email address."
    );

    declarerEmail.focus();

    return false;
}

if (
    !declarerEmail.checkValidity()
) {

    showError(
        "Please enter a valid email address."
    );

    declarerEmail.focus();

    return false;
}

return true;


}

/* =====================================================
Build common POST body
===================================================== */

function buildActionBody(action) {


const body = {

    action:

        action,

    declarer_name:

        (
            giftAidData.member.first_name +
            " " +
            giftAidData.member.surname
        ).trim(),

    declarer_address_line_1:

        declarerAddressLine1.value.trim(),

    declarer_address_line_2:

        declarerAddressLine2.value.trim(),

    declarer_postcode:

        declarerPostcode.value.trim(),

    email_address:

        declarerEmail.value.trim(),

    affirmed:

        false,

    wording_version_id:

        giftAidData.wording?.wording_version_id ||
        giftAidData.declaration?.wording_version_id ||
        1,

    declaration_text:

        giftAidData.declaration?.declaration_text ||
        giftAidData.wording?.wording ||
        "",

    covered_members:

        coveredMembers
};

if (action === "CANCELLED") {

    body.affirmed_date =
        new Date()
            .toISOString()
            .slice(0, 10);
}

return body;


}

/* =====================================================
Submit ordinary declaration
===================================================== */

async function submitDeclaration() {


if (!validateForm()) {
    return;
}

const token =
    getToken();

if (!token) {

    showError(
        "No Gift Aid invitation token was supplied."
    );

    return;
}

const action =
    giftAidData?.gift_aid_reference
        ? "UPDATED"
        : "AFFIRMED";

submitButton.disabled =
    true;

submitButton.textContent =
    "Submitting...";

try {

    const body = {

        action:

            action,

        declarer_name:

            (
                giftAidData.member.first_name +
                " " +
                giftAidData.member.surname
            ).trim(),

        declarer_address_line_1:

            declarerAddressLine1.value.trim(),

        declarer_address_line_2:

            declarerAddressLine2.value.trim(),

        declarer_postcode:

            declarerPostcode.value.trim(),

        email_address:

            declarerEmail.value.trim(),

        affirmed_date:

            new Date()
                .toISOString()
                .slice(0, 10),

        affirmed:

            true,

        wording_version_id:

            giftAidData.wording?.wording_version_id ||
            giftAidData.declaration?.wording_version_id ||
            1,

        declaration_text:

            giftAidData.declaration?.declaration_text ||
            giftAidData.wording?.wording ||
            "",

        covered_members:

            coveredMembers
    };

    const response =
        await fetch(
            API_BASE +
            "/api/gift-aid/declaration?token=" +
            encodeURIComponent(token),
            {

                method:
                    "POST",

                headers: {

                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify(body)
            }
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data.error ||
            "Unable to submit the Gift Aid declaration."
        );
    }

    showSuccess(
        data,
        "Gift Aid declaration submitted",
        "Thank you. Your Gift Aid declaration has been recorded successfully."
    );

} catch (err) {

    console.error(
        "Gift Aid declaration submission error:",
        err
    );

    showError(
        err.message ||
        "Unable to submit the Gift Aid declaration."
    );

} finally {

    submitButton.disabled =
        false;

    submitButton.textContent =
        "Submit Gift Aid declaration";
}


}

/* =====================================================
Submit a single alternative action
===================================================== */


async function postAlternativeAction(
    action,
    coveredElsewhere,
    options
) {

    const token =
        getToken();

    if (!token) {

        throw new Error(
            "No Gift Aid invitation token was supplied."
        );
    }

    const body =
        buildActionBody(
            action
        );

    if (coveredElsewhere) {

        body.covered_elsewhere =
            coveredElsewhere;
    }

    if (options) {

        if (
            options.follow_up_action
        ) {

            body.follow_up_action =
                options.follow_up_action;
        }
    }

    const response =
        await fetch(
            API_BASE +
            "/api/gift-aid/declaration?token=" +
            encodeURIComponent(token),
            {

                method:
                    "POST",

                headers: {

                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify(body)
            }
        );

    const data =
        await response.json();

    if (!response.ok) {

        throw new Error(
            data.error ||
            "Unable to submit the Gift Aid action."
        );
    }

    return data;
}



/* =====================================================
Submit alternative action
===================================================== */

async function submitAlternativeAction(
action,
coveredElsewhere
) {




let confirmationMessage =
    "";

if (action === "CANCELLED") {

    confirmationMessage =
        "Are you sure you want to cancel your Gift Aid declaration?";

} else if (action === "DECLINED") {

    confirmationMessage =
        "Are you sure you do not want to Gift Aid your donations?";

} else if (action === "COVERED_ELSEWHERE") {

    confirmationMessage =
        "Are you sure that your Gift Aid is covered by another person's declaration?";
}

if (
    !window.confirm(
        confirmationMessage
    )
) {

    return;
}

cancelButton.disabled =
    true;

declineButton.disabled =
    true;

coveredElsewhereButton.disabled =
    true;

try {

    /*
     * Covered Elsewhere is special when there is
     * currently an affirmed declaration.
     *
     * We deliberately make two separate POST calls:
     *
     * 1. CANCELLED
     * 2. COVERED_ELSEWHERE
     *
     * This gives us two separate audit events.
     */

    if (
        action === "COVERED_ELSEWHERE" &&
        giftAidData.declaration &&
        (
            giftAidData.declaration.action === "AFFIRMED" ||
            giftAidData.declaration.action === "UPDATED"
        ) &&
        giftAidData.declaration.affirmed === true

    ) {

    await postAlternativeAction(
        "CANCELLED",
        false,
        {
            follow_up_action: "COVERED_ELSEWHERE"
        }
    );

        await postAlternativeAction(
            "COVERED_ELSEWHERE",
            coveredElsewhere
        );

        showSuccess(
            {},
            "Gift Aid information submitted",
            "Your current Gift Aid declaration has been cancelled and your information about the other person's declaration has been submitted for administrative review."
        );

        return;
    }

    /*
     * For someone without a current affirmation,
     * Covered Elsewhere requires only one audit entry.
     */

    const data =
        await postAlternativeAction(
            action,
            coveredElsewhere
        );

    let heading =
        "Gift Aid declaration updated";

    let message =
        "Your Gift Aid declaration has been updated successfully.";

    if (action === "CANCELLED") {

        heading =
            "Gift Aid declaration cancelled";

        message =
            "Your Gift Aid declaration has been cancelled successfully.";

    } else if (action === "DECLINED") {

        heading =
            "No Gift Aid declaration recorded";

        message =
            "We have recorded that you do not wish to Gift Aid your donations.";

    } else if (action === "COVERED_ELSEWHERE") {

        heading =
            "Gift Aid information submitted";

        message =
            "Thank you. Your information has been received and will be reviewed by the Suffolk Guild.";
    }

    showSuccess(
        data,
        heading,
        message
    );

} catch (err) {

    console.error(
        "Gift Aid alternative action error:",
        err
    );

    showError(
        err.message ||
        "Unable to submit the Gift Aid action."
    );

} finally {

    cancelButton.disabled =
        false;

    declineButton.disabled =
        false;

    coveredElsewhereButton.disabled =
        false;
}


}

/* =====================================================
Show success message
===================================================== */

function showSuccess(
data,
heading,
message
) {


declaration.hidden =
    true;

statusMessage.hidden =
    true;

if (giftAidActions) {

    giftAidActions.hidden =
        true;
}

const referenceHtml =
    data.gift_aid_reference
        ? "<p class=\"mb-0\">" +
          "Gift Aid reference: " +
          "<strong>" +
          data.gift_aid_reference +
          "</strong>" +
          "</p>"
        : "";

const statusHtml =
    data.status === "PENDING_REVIEW"
        ? "<p>" +
          "Your information has been received and " +
          "is awaiting administrative review." +
          "</p>"
        : "";

successMessage.innerHTML =
    "<h2 class=\"h4\">" +
    heading +
    "</h2>" +

    "<p>" +
    message +
    "</p>" +

    statusHtml +

    referenceHtml;

successMessage.hidden =
    false;


}

/* =====================================================
Covered elsewhere prompt
===================================================== */

function showCoveredElsewherePrompt() {


clearError();

let promptCard =
    document.querySelector(
        "#gift-aid-covered-elsewhere-prompt"
    );

if (promptCard) {

    promptCard.hidden =
        false;

    promptCard.scrollIntoView({
        behavior:
            "smooth",

        block:
            "center"
    });

    return;
}

promptCard =
    document.createElement("div");

promptCard.id =
    "gift-aid-covered-elsewhere-prompt";

promptCard.className =
    "card mt-3";

promptCard.innerHTML =
    "<div class=\"card-body\">" +

    "<h3 class=\"card-title h5\">" +
    "Whose declaration covers your Gift Aid?" +
    "</h3>" +

    "<p>" +
    "Please enter the other person's name or " +
    "membership number, if known. This information " +
    "will be reviewed by the Guild and will not " +
    "automatically change any membership records." +
    "</p>" +

    "<div class=\"mb-3\">" +

    "<label " +
    "for=\"gift-aid-other-person-number\" " +
    "class=\"form-label\">" +
    "Membership number" +
    "</label>" +

    "<input " +
    "type=\"text\" " +
    "class=\"form-control\" " +
    "id=\"gift-aid-other-person-number\">" +

    "</div>" +

    "<div class=\"mb-3\">" +

    "<label " +
    "for=\"gift-aid-other-person-name\" " +
    "class=\"form-label\">" +
    "Name" +
    "</label>" +

    "<input " +
    "type=\"text\" " +
    "class=\"form-control\" " +
    "id=\"gift-aid-other-person-name\">" +

    "</div>" +

    "<div class=\"d-flex gap-2\">" +

    "<button " +
    "type=\"button\" " +
    "class=\"btn btn-primary\" " +
    "id=\"gift-aid-covered-elsewhere-submit\">" +
    "Submit information" +
    "</button>" +

    "<button " +
    "type=\"button\" " +
    "class=\"btn btn-secondary\" " +
    "id=\"gift-aid-covered-elsewhere-cancel\">" +
    "Cancel" +
    "</button>" +

    "</div>" +

    "</div>";

giftAidActions.appendChild(
    promptCard
);

const numberInput =
    document.querySelector(
        "#gift-aid-other-person-number"
    );

const nameInput =
    document.querySelector(
        "#gift-aid-other-person-name"
    );

const submitElsewhereButton =
    document.querySelector(
        "#gift-aid-covered-elsewhere-submit"
    );

const cancelElsewhereButton =
    document.querySelector(
        "#gift-aid-covered-elsewhere-cancel"
    );

submitElsewhereButton.addEventListener(
    "click",
    function() {

        const membershipNumber =
            numberInput.value.trim();

        const name =
            nameInput.value.trim();

        if (
            !membershipNumber &&
            !name
        ) {

            showError(
                "Please enter the other person's membership number or name."
            );

            numberInput.focus();

            return;
        }

        /*
         * Keep exactly what the member supplied.
         *
         * The Lambda/admin process will interpret it.
         * This page does not attempt to identify the person.
         */

        const details = [];

        if (membershipNumber) {

            details.push(
                "Membership number: " +
                membershipNumber
            );
        }

        if (name) {

            details.push(
                "Name: " +
                name
            );
        }

        submitAlternativeAction(
            "COVERED_ELSEWHERE",
            details.join("; ")
        );
    }
);

cancelElsewhereButton.addEventListener(
    "click",
    function() {

        promptCard.hidden =
            true;

        clearError();
    }
);

promptCard.scrollIntoView({
    behavior:
        "smooth",

    block:
        "center"
});


}

/* =====================================================
Button event handlers
===================================================== */

if (submitButton) {


submitButton.addEventListener(
    "click",
    submitDeclaration
);


}

if (coveredMemberAddButton) {


coveredMemberAddButton.addEventListener(
    "click",
    addCoveredMember
);


}

if (cancelButton) {


cancelButton.addEventListener(
    "click",
    function() {

        submitAlternativeAction(
            "CANCELLED"
        );
    }
);


}

if (declineButton) {


declineButton.addEventListener(
    "click",
    function() {

        submitAlternativeAction(
            "DECLINED"
        );
    }
);


}

if (coveredElsewhereButton) {


coveredElsewhereButton.addEventListener(
    "click",
    showCoveredElsewherePrompt
);


}

/* =====================================================
Initialise
===================================================== */

loadDeclaration()
.catch(
function(err) {


        console.error(
            "Gift Aid declaration load error:",
            err
        );

        loading.hidden =
            true;

        if (giftAidActions) {
            giftAidActions.hidden =
            true;
            }

        showError(
            err.message ||
            "Unable to load the Gift Aid declaration."
        );
    }
);

