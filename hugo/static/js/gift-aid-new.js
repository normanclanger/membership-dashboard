import {
    requireLogin
} from "/js/auth.js";


const API_BASE =
    `${window.API_BASE_URL}`;


const ALLOWED_GROUPS = [
    "MembershipAdmin",
    "ApplicationAdmin",
    "PaymentAdmin"
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


function userCanEdit(user) {

    const groups =
        getGroups(user);


    return groups.some(group =>
        ALLOWED_GROUPS.includes(group)
    );
}


const memberSearchInput =
    document.querySelector(
        "#gift-aid-new-member-search"
    );


const memberSearchResults =
    document.querySelector(
        "#gift-aid-new-member-results"
    );


const memberDetails =
    document.querySelector(
        "#gift-aid-new-member-details"
    );


const newForm =
    document.querySelector(
        "#gift-aid-new-form"
    );


const referenceInput =
    document.querySelector(
        "#gift-aid-new-reference"
    );


const submitButton =
    document.querySelector(
        "#gift-aid-new-submit"
    );


const message =
    document.querySelector(
        "#gift-aid-new-message"
    );


let memberSearchTimeout = null;

let selectedMember = null;



/* =====================================================
   Search members
   ===================================================== */

async function searchMembers() {

    const search =
        memberSearchInput.value.trim();


    memberSearchResults.innerHTML = "";

    memberSearchResults.hidden = true;


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
                "Unable to search members."
            );
        }


        const members =
            data.members || data;


        if (!members.length) {

            memberSearchResults.innerHTML = `
                <div class="list-group-item text-muted">
                    No members found.
                </div>
            `;

            memberSearchResults.hidden = false;

            return;
        }


        for (
            const member
            of members
        ) {

            const item =
                document.createElement(
                    "button"
                );


            item.type = "button";

            item.className =
                "list-group-item list-group-item-action";


            item.textContent =
                `${member.membership_number} - ` +
                `${member.first_name} ${member.surname} - ` +
                `${member.tower?.name || "—"} - ` +
                `${member.district?.name || "—"}`;


            item.addEventListener(
                "click",
                () => selectMember(member)
            );


            memberSearchResults.appendChild(
                item
            );
        }


        memberSearchResults.hidden = false;

    } catch (err) {

        console.error(
            "Gift Aid member search error:",
            err
        );


        memberSearchResults.innerHTML = `
            <div class="list-group-item text-danger">
                ${err.message ||
                  "Unable to search members."}
            </div>
        `;

        memberSearchResults.hidden = false;
    }
}



/* =====================================================
   Select member
   ===================================================== */

function selectMember(member) {

    selectedMember =
        member;


    memberSearchResults.innerHTML = "";
    memberSearchResults.hidden = true;


    memberSearchInput.value =
        `${member.membership_number} - ` +
        `${member.first_name} ${member.surname}`;


    memberDetails.innerHTML = `
        <div class="card bg-light">

            <div class="card-body">

                <h3 class="h5">
                    Selected member
                </h3>

                <dl class="row mb-0">

                    <dt class="col-sm-3">
                        Membership
                    </dt>

                    <dd class="col-sm-9">
                        ${member.membership_number}
                    </dd>


                    <dt class="col-sm-3">
                        Name
                    </dt>

                    <dd class="col-sm-9">
                        ${member.first_name}
                        ${member.surname}
                    </dd>


                    <dt class="col-sm-3">
                        Tower
                    </dt>

                    <dd class="col-sm-9">
                        ${member.tower?.name || "—"}
                    </dd>


                    <dt class="col-sm-3">
                        District
                    </dt>

                    <dd class="col-sm-9">
                        ${member.district?.name || "—"}
                    </dd>

                </dl>

            </div>

        </div>
    `;


    newForm.hidden = false;

    message.innerHTML = "";

    referenceInput.value = "";

    referenceInput.focus();
}



/* =====================================================
   Add Gift Aid relationship
   ===================================================== */

async function addGiftAidRelationship() {

    message.innerHTML = "";


    if (!selectedMember) {

        message.innerHTML = `
            <div class="alert alert-danger">
                Please select a member first.
            </div>
        `;

        return;
    }


    const reference =
        referenceInput.value.trim();


    if (!reference) {

        message.innerHTML = `
            <div class="alert alert-danger">
                Please enter a Gift Aid reference.
            </div>
        `;

        referenceInput.focus();

        return;
    }


    try {

        const giftAidReference =
            Number(reference);


        if (
            !Number.isInteger(giftAidReference) ||
            giftAidReference <= 0
        ) {

            throw new Error(
                "Gift Aid reference must be a positive number."
            );
        }


        const user =
            await requireLogin();


        if (!user) {
            return;
        }


        if (!userCanEdit(user)) {

            throw new Error(
                "You do not have permission to add Gift Aid relationships."
            );
        }


        submitButton.disabled = true;

        submitButton.textContent =
            "Adding...";


        const response =
            await fetch(
                `${API_BASE}/api/gift-aid`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json",

                        Authorization:
                            `Bearer ${user.access_token}`
                    },

                    body: JSON.stringify({
                        member_id:
                            selectedMember.id,

                        gift_aid_reference:
                            giftAidReference
                    })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.error ||
                "Unable to add Gift Aid relationship."
            );
        }


        /*
         * Show confirmation of the successful addition.
         */

        message.innerHTML = `
            <div class="alert alert-success">

                <strong>
                    Gift Aid relationship added.
                </strong>

                ${data.membership_number}
                -
                ${data.first_name}
                ${data.surname}
                -
                Gift Aid reference
                ${data.gift_aid_reference}

            </div>
        `;


        /*
         * Reset the form ready for the next
         * member to be added.
         */

        selectedMember = null;

        memberSearchInput.value = "";

        memberSearchResults.innerHTML = "";
        memberSearchResults.hidden = true;

        memberDetails.innerHTML = "";

        referenceInput.value = "";

        newForm.hidden = true;


        /*
         * Return the cursor to the member search box.
         */

        memberSearchInput.focus();

    } catch (err) {

        console.error(
            "Add Gift Aid relationship error:",
            err
        );


        message.innerHTML = `
            <div class="alert alert-danger">
                ${err.message ||
                  "Unable to add Gift Aid relationship."}
            </div>
        `;

    } finally {

        submitButton.disabled = false;

        submitButton.textContent =
            "Add Gift Aid relationship";
    }
}



/* =====================================================
   Member search type-ahead
   ===================================================== */

if (memberSearchInput) {

    memberSearchInput.addEventListener(
        "input",
        () => {

            selectedMember = null;

            newForm.hidden = true;

            memberDetails.innerHTML = "";

            message.innerHTML = "";


            clearTimeout(
                memberSearchTimeout
            );


            const search =
                memberSearchInput.value.trim();


            if (!search) {
                return;
            }


            memberSearchTimeout =
                setTimeout(
                    searchMembers,
                    300
                );
        }
    );
}



/* =====================================================
   Add button
   ===================================================== */

if (submitButton) {

    submitButton.addEventListener(
        "click",
        addGiftAidRelationship
    );
}



/* =====================================================
   Require login when page loads
   ===================================================== */

requireLogin();