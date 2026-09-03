import {
    requireLogin
} from "/js/auth.js";

import {
    downloadTableAsCsv
} from "/js/csv.js";

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


const API_BASE =
    `${window.API_BASE_URL}`;


const memberSearchInput =
    document.querySelector(
        "#gift-aid-member-search"
    );


const memberSearchResults =
    document.querySelector(
        "#gift-aid-member-results"
    );


const memberDetails =
    document.querySelector(
        "#gift-aid-member-details"
    );


let memberSearchTimeout = null;


const referenceInput =
    document.querySelector(
        "#gift-aid-reference-search"
    );


const referenceButton =
    document.querySelector(
        "#gift-aid-reference-search-button"
    );


const referenceResults =
    document.querySelector(
        "#gift-aid-reference-results"
    );


/* =====================================================
   End Gift-Aid status modal elements
   ===================================================== */

const endGiftAidModalElement =
    document.querySelector(
        "#end-gift-aid-modal"
    );


const endGiftAidMemberDetails =
    document.querySelector(
        "#end-gift-aid-member-details"
    );


const endGiftAidOptions =
    document.querySelector(
        "#end-gift-aid-options"
    );


const endGiftAidMemberOnlyButton =
    document.querySelector(
        "#end-gift-aid-member-only"
    );


const endGiftAidEntireFormButton =
    document.querySelector(
        "#end-gift-aid-entire-form"
    );


const endGiftAidForm =
    document.querySelector(
        "#end-gift-aid-form"
    );


const endGiftAidDate =
    document.querySelector(
        "#end-gift-aid-date"
    );


const endGiftAidConfirmation =
    document.querySelector(
        "#end-gift-aid-confirmation"
    );


const endGiftAidBackButton =
    document.querySelector(
        "#end-gift-aid-back"
    );


const endGiftAidConfirmButton =
    document.querySelector(
        "#end-gift-aid-confirm"
    );


const endGiftAidError =
    document.querySelector(
        "#end-gift-aid-error"
    );


let endGiftAidModal = null;
let endGiftAidRelationship = null;
let endGiftAidMode = null;
let endGiftAidTargetRelationships = [];


/* =====================================================
   Initialise Bootstrap modal
   ===================================================== */

if (
    endGiftAidModalElement &&
    window.bootstrap
) {

    endGiftAidModal =
        new bootstrap.Modal(
            endGiftAidModalElement
        );
}


/* =====================================================
   Format a stored date for display
   ===================================================== */

function formatDate(dateString) {

    if (!dateString) {
        return "—";
    }

    const parts =
        dateString.split("-");

    if (parts.length !== 3) {
        return dateString;
    }

    return `${parts[2]}/${parts[1]}/${parts[0]}`;
}


/* =====================================================
   Display Gift Aid relationships as a table
   ===================================================== */

function displayGiftAidRelationships(
    relationships,
    user
) {

    referenceResults.innerHTML = "";


    if (!relationships.length) {

        referenceResults.innerHTML = `
            <div class="alert alert-info">
                No Gift Aid relationships found.
            </div>
        `;

        return;
    }


    const tableWrapper =
        document.createElement(
            "div"
        );

    tableWrapper.className =
        "table-responsive";


    const table =
        document.createElement(
            "table"
        );
		
    table.id =
        "gift-aid-reference-table";

    table.className =
        "table table-striped table-hover";


    const canEdit =
        userCanEdit(user);


    table.innerHTML = `
        <thead>
            <tr>
                <th>Gift Aid reference</th>
                <th>Membership</th>
                <th>Name</th>
                <th>Tower</th>
                <th>Valid until</th>
                ${canEdit ? "<th>Actions</th>" : ""}
            </tr>
        </thead>

        <tbody></tbody>
    `;


    const tbody =
        table.querySelector(
            "tbody"
        );


    for (
        const relationship
        of relationships
    ) {

        const row =
            document.createElement(
                "tr"
            );


        row.innerHTML = `
            <td>
                ${relationship.gift_aid_reference}
            </td>

            <td>
                ${relationship.membership_number}
            </td>

            <td>
                ${relationship.first_name}
                ${relationship.surname}
            </td>

            <td>
                ${relationship.tower || "—"}
            </td>

            <td>
                ${formatDate(
                    relationship.valid_until
                )}
            </td>
        `;


        if (
            canEdit &&
            !relationship.valid_until
        ) {

            const actionsCell =
                document.createElement(
                    "td"
                );


            const endButton =
                document.createElement(
                    "button"
                );


            endButton.type =
                "button";


            endButton.className =
                "btn btn-sm btn-danger";


            endButton.textContent =
                "End Gift-Aid status";


            endButton.addEventListener(
                "click",
                () =>
                    openEndGiftAidModal(
                        relationship,
                        user
                    )
            );


            actionsCell.appendChild(
                endButton
            );


            row.appendChild(
                actionsCell
            );

        } else if (canEdit) {

            const actionsCell =
                document.createElement(
                    "td"
                );

            actionsCell.textContent =
                "—";

            row.appendChild(
                actionsCell
            );
        }


        tbody.appendChild(
            row
        );
    }


    tableWrapper.appendChild(
        table
    );


    referenceResults.appendChild(
        tableWrapper
    );
}



/* =====================================================
   Display Member Gift Aid relationships as a table
   ===================================================== */

function displayMemberGiftAidRelationships(
    relationships,
    user
) {

    memberDetails.innerHTML = "";


    if (!relationships.length) {

        memberDetails.innerHTML = `
            <div class="alert alert-info">
                No Gift Aid relationships found.
            </div>
        `;

        return;
    }


    const tableWrapper =
        document.createElement(
            "div"
        );

    tableWrapper.className =
        "table-responsive";


    const table =
        document.createElement(
            "table"
        );

    table.className =
        "table table-striped table-hover";


    const canEdit =
        userCanEdit(user);


    table.innerHTML = `
        <thead>
            <tr>
                <th>Membership</th>
                <th>Name</th>
                <th>Tower</th>
                <th>Gift Aid reference</th>
                <th>Valid until</th>
                ${canEdit ? "<th>Actions</th>" : ""}
            </tr>
        </thead>

        <tbody></tbody>
    `;


    const tbody =
        table.querySelector(
            "tbody"
        );


    for (
        const relationship
        of relationships
    ) {

        const row =
            document.createElement(
                "tr"
            );


        row.innerHTML = `
            <td>
                ${relationship.membership_number}
            </td>

            <td>
                ${relationship.first_name}
                ${relationship.surname}
            </td>

            <td>
                ${relationship.tower || "—"}
            </td>

            <td>
                ${relationship.gift_aid_reference}
            </td>

            <td>
                ${formatDate(
                    relationship.valid_until
                )}
            </td>
        `;


        if (
            canEdit &&
            !relationship.valid_until
        ) {

            const actionsCell =
                document.createElement(
                    "td"
                );


            const endButton =
                document.createElement(
                    "button"
                );


            endButton.type =
                "button";


            endButton.className =
                "btn btn-sm btn-danger";


            endButton.textContent =
                "End Gift-Aid status";


            endButton.addEventListener(
                "click",
                () =>
                    openEndGiftAidModal(
                        relationship,
                        user
                    )
            );


            actionsCell.appendChild(
                endButton
            );


            row.appendChild(
                actionsCell
            );

        } else if (canEdit) {

            const actionsCell =
                document.createElement(
                    "td"
                );

            actionsCell.textContent =
                "—";

            row.appendChild(
                actionsCell
            );
        }


        tbody.appendChild(
            row
        );
    }


    tableWrapper.appendChild(
        table
    );


    memberDetails.appendChild(
        tableWrapper
    );
}



/* =====================================================
   Open End Gift-Aid status modal
   ===================================================== */

function openEndGiftAidModal(
    relationship,
    user
) {

    if (!endGiftAidModal) {

        window.alert(
            "Unable to open the End Gift-Aid status dialog."
        );

        return;
    }


    endGiftAidRelationship =
        relationship;

    endGiftAidMode = null;

    endGiftAidTargetRelationships = [];


    endGiftAidMemberDetails.innerHTML = `
        <strong>
            ${relationship.first_name}
            ${relationship.surname}
        </strong>
        <br>
        Membership:
        ${relationship.membership_number}
        <br>
        Gift-Aid reference:
        ${relationship.gift_aid_reference}
    `;


    endGiftAidOptions.hidden =
        false;

    endGiftAidForm.hidden =
        true;

    endGiftAidConfirmation.hidden =
        true;

    endGiftAidConfirmation.textContent =
        "";

    endGiftAidError.hidden =
        true;

    endGiftAidError.textContent =
        "";

    endGiftAidDate.value =
        "";


    endGiftAidEntireFormButton.disabled =
        false;


    endGiftAidModal.show();
}



/* =====================================================
   Select "This member only"
   ===================================================== */

function selectMemberOnly() {

    endGiftAidMode =
        "member";

    endGiftAidTargetRelationships = [
        endGiftAidRelationship
    ];

    showEndGiftAidDateForm();

}



/* =====================================================
   Select "Entire Gift-Aid form"
   ===================================================== */

async function selectEntireForm() {

    endGiftAidMode =
        "form";


    endGiftAidError.hidden =
        true;

    endGiftAidError.textContent =
        "";


    endGiftAidEntireFormButton.disabled =
        true;


    try {

        const user =
            await requireLogin();


        if (!user) {
            return;
        }


        const reference =
            endGiftAidRelationship.gift_aid_reference;


        const response =
            await fetch(
                `${API_BASE}/api/gift-aid?gift_aid_reference=${encodeURIComponent(reference)}`,
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
                "Unable to load the Gift-Aid form relationships."
            );
        }


        const relationships =
            data.relationships || [];


        endGiftAidTargetRelationships =
            relationships.filter(
                relationship =>
                    !relationship.valid_until
            );


        if (
            !endGiftAidTargetRelationships.some(
                relationship =>
                    relationship.id ===
                    endGiftAidRelationship.id
            )
        ) {

            endGiftAidTargetRelationships.unshift(
                endGiftAidRelationship
            );
        }


        showEndGiftAidDateForm();


    } catch (err) {

        console.error(
            "Gift Aid form lookup error:",
            err
        );


        endGiftAidError.textContent =
            err.message ||
            "Unable to load the Gift-Aid form relationships.";

        endGiftAidError.hidden =
            false;

        endGiftAidMode =
            null;

    } finally {

        endGiftAidEntireFormButton.disabled =
            false;
    }
}



/* =====================================================
   Show date and confirmation section
   ===================================================== */

function showEndGiftAidDateForm() {

    endGiftAidOptions.hidden =
        true;

    endGiftAidForm.hidden =
        false;

    endGiftAidDate.focus();


    const count =
        endGiftAidTargetRelationships.length;


    if (endGiftAidMode === "member") {

        endGiftAidConfirmation.textContent =
            `This will end Gift-Aid status for ` +
            `${endGiftAidRelationship.first_name} ` +
            `${endGiftAidRelationship.surname} only.`;

    } else {

        endGiftAidConfirmation.textContent =
            `This will end Gift-Aid status for ` +
            `${count} active member` +
            `${count === 1 ? "" : "s"} ` +
            `attached to Gift-Aid reference ` +
            `${endGiftAidRelationship.gift_aid_reference}.`;
    }


    endGiftAidConfirmation.hidden =
        false;
}



/* =====================================================
   Return to member/form choice
   ===================================================== */

function backToEndGiftAidOptions() {

    endGiftAidMode =
        null;

    endGiftAidTargetRelationships =
        [];

    endGiftAidForm.hidden =
        true;

    endGiftAidOptions.hidden =
        false;

    endGiftAidConfirmation.hidden =
        true;

    endGiftAidError.hidden =
        true;

    endGiftAidDate.value =
        "";
}



/* =====================================================
   End one or more Gift-Aid relationships
   ===================================================== */

async function confirmEndGiftAid() {

    const validUntil =
        endGiftAidDate.value;


    if (!validUntil) {

        endGiftAidError.textContent =
            "Please enter the date the Gift-Aid status ended.";

        endGiftAidError.hidden =
            false;

        return;
    }


    if (
        !endGiftAidTargetRelationships.length
    ) {

        endGiftAidError.textContent =
            "No Gift-Aid relationships were selected.";

        endGiftAidError.hidden =
            false;

        return;
    }


    endGiftAidError.hidden =
        true;

    endGiftAidConfirmation.hidden =
        false;


    const confirmationDate =
        formatDate(validUntil);


    if (endGiftAidMode === "member") {

        endGiftAidConfirmation.textContent =
            `This will end Gift-Aid status for ` +
            `${endGiftAidRelationship.first_name} ` +
            `${endGiftAidRelationship.surname} ` +
            `on ${confirmationDate}.`;

    } else {

        endGiftAidConfirmation.textContent =
            `This will end Gift-Aid status for ` +
            `${endGiftAidTargetRelationships.length} active member` +
            `${endGiftAidTargetRelationships.length === 1 ? "" : "s"} ` +
            `attached to Gift-Aid reference ` +
            `${endGiftAidRelationship.gift_aid_reference} ` +
            `on ${confirmationDate}.`;
    }


    const confirmed =
        window.confirm(
            endGiftAidConfirmation.textContent +
            "\n\nAre you sure?"
        );


    if (!confirmed) {
        return;
    }


    endGiftAidConfirmButton.disabled =
        true;


    const succeeded = [];
    const failed = [];


    try {

        const user =
            await requireLogin();


        if (!user) {
            return;
        }


        for (
            const relationship
            of endGiftAidTargetRelationships
        ) {

            try {

                const response =
                    await fetch(
                        `${API_BASE}/api/gift-aid/${relationship.id}`,
                        {
                            method: "DELETE",

                            headers: {
                                Authorization:
                                    `Bearer ${user.access_token}`,
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({
                                valid_until:
                                    validUntil
                            })
                        }
                    );


                const data =
                    await response.json();


                if (!response.ok) {

                    throw new Error(
                        data.error ||
                        "Unable to end Gift-Aid status."
                    );
                }


                succeeded.push(
                    relationship
                );

            } catch (err) {

                failed.push({
                    relationship,
                    error:
                        err.message ||
                        "Unable to end Gift-Aid status."
                });
            }
        }


        if (endGiftAidModal) {
            endGiftAidModal.hide();
        }


        await refreshCurrentGiftAidView(
            user
        );


        if (failed.length) {

            showGiftAidOperationError(
                `Gift-Aid status was ended for ` +
                `${succeeded.length} relationship` +
                `${succeeded.length === 1 ? "" : "s"}, ` +
                `but ${failed.length} could not be ended.`
            );

        } else {

            showGiftAidOperationSuccess(
                `Gift-Aid status ended successfully for ` +
                `${succeeded.length} relationship` +
                `${succeeded.length === 1 ? "" : "s"}.`
            );
        }


    } catch (err) {

        console.error(
            "Gift Aid end status error:",
            err
        );


        showGiftAidOperationError(
            err.message ||
            "Unable to end Gift-Aid status."
        );

    } finally {

        endGiftAidConfirmButton.disabled =
            false;
    }
}



/* =====================================================
   Refresh whichever Gift Aid page is being viewed
   ===================================================== */

async function refreshCurrentGiftAidView(
    user
) {

    if (memberDetails) {

        const selectedMember =
            memberSearchInput?.dataset.memberId;


        if (selectedMember) {

            await loadMemberGiftAidRelationships(
                selectedMember,
                user
            );

        } else {

            await loadAllMemberGiftAidRelationships();
        }


    } else {

        const reference =
            referenceInput?.value.trim();


        if (reference) {

            await searchByGiftAidReference();

        } else {

            await loadAllGiftAidRelationships();
        }
    }
}



/* =====================================================
   Show successful operation message
   ===================================================== */

function showGiftAidOperationSuccess(
    message
) {

    const alert =
        document.createElement(
            "div"
        );

    alert.className =
        "alert alert-success mt-3";

    alert.textContent =
        message;


    if (memberDetails) {

        memberDetails.prepend(
            alert
        );

    } else if (referenceResults) {

        referenceResults.prepend(
            alert
        );
    }
}



/* =====================================================
   Show operation error message
   ===================================================== */

function showGiftAidOperationError(
    message
) {

    const alert =
        document.createElement(
            "div"
        );

    alert.className =
        "alert alert-danger mt-3";

    alert.textContent =
        message;


    if (memberDetails) {

        memberDetails.prepend(
            alert
        );

    } else if (referenceResults) {

        referenceResults.prepend(
            alert
        );
    }
}



/* =====================================================
   Load all Gift Aid relationships
   ===================================================== */

async function loadAllGiftAidRelationships() {

    try {

        const user =
            await requireLogin();


        if (!user) {
            return;
        }


        const response =
            await fetch(
                `${API_BASE}/api/gift-aid`,
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
                "Unable to load Gift Aid relationships."
            );
        }


        const relationships =
            data.relationships || [];


        displayGiftAidRelationships(
            relationships,
            user
        );

    } catch (err) {

        console.error(
            "Gift Aid list error:",
            err
        );


        if (referenceResults) {

            referenceResults.innerHTML = `
                <div class="alert alert-danger">
                    ${err.message ||
                      "Unable to load Gift Aid relationships."}
                </div>
            `;
        }
    }
}



/* =====================================================
   Load all Gift Aid relationships for member page
   ===================================================== */

async function loadAllMemberGiftAidRelationships() {

    try {

        const user =
            await requireLogin();


        if (!user) {
            return;
        }


        const response =
            await fetch(
                `${API_BASE}/api/gift-aid`,
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
                "Unable to load Gift Aid relationships."
            );
        }


        const relationships =
            data.relationships || [];


        displayMemberGiftAidRelationships(
            relationships,
            user
        );

    } catch (err) {

        console.error(
            "Member Gift Aid list error:",
            err
        );


        if (memberDetails) {

            memberDetails.innerHTML = `
                <div class="alert alert-danger">
                    ${err.message ||
                      "Unable to load Gift Aid relationships."}
                </div>
            `;
        }
    }
}



/* =====================================================
   Load Gift Aid relationships for selected member
   ===================================================== */

async function loadMemberGiftAidRelationships(
    memberId,
    user
) {

    try {

        memberDetails.innerHTML = `
            <div class="text-muted">
                Loading Gift Aid relationships...
            </div>
        `;


        const response =
            await fetch(
                `${API_BASE}/api/gift-aid?member_id=${encodeURIComponent(memberId)}`,
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
                "Unable to load Gift Aid relationships."
            );
        }


        const relationships =
            data.relationships || [];


        displayMemberGiftAidRelationships(
            relationships,
            user
        );

    } catch (err) {

        console.error(
            "Member Gift Aid load error:",
            err
        );


        memberDetails.innerHTML = `
            <div class="alert alert-danger">
                ${err.message ||
                  "Unable to load Gift Aid relationships."}
            </div>
        `;
    }
}



/* =====================================================
   Search by Gift Aid reference
   ===================================================== */

async function searchByGiftAidReference() {

    const reference =
        referenceInput.value.trim();


    /*
     * Empty search means:
     * return to the complete list.
     */

    if (!reference) {

        await loadAllGiftAidRelationships();

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
                `${API_BASE}/api/gift-aid?gift_aid_reference=${encodeURIComponent(reference)}`,
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
                "Unable to search Gift Aid relationships."
            );
        }


        const relationships =
            data.relationships || [];


        displayGiftAidRelationships(
            relationships,
            user
        );

    } catch (err) {

        console.error(
            "Gift Aid reference search error:",
            err
        );


        if (referenceResults) {

            referenceResults.innerHTML = `
                <div class="alert alert-danger">
                    ${err.message ||
                      "Unable to search Gift Aid relationships."}
                </div>
            `;
        }
    }
}



/* =====================================================
   Reference search button
   ===================================================== */

if (referenceButton) {

    referenceButton.addEventListener(
        "click",
        searchByGiftAidReference
    );
}

const referenceDownloadButton =
    document.querySelector(
        "#gift-aid-reference-download"
    );


if (referenceDownloadButton) {

    referenceDownloadButton.addEventListener(
        "click",
        () => {

            const table =
                document.querySelector(
                    "#gift-aid-reference-table"
                );


            if (!table) {

                window.alert(
                    "There is no Gift-Aid data to download."
                );

                return;
            }


            try {

                downloadTableAsCsv(
                    table,
                    "gift-aid-reference.csv",
                    {
                        excludeColumns: [
                            "Actions"
                        ]
                    }
                );

            } catch (err) {

                console.error(
                    "Gift Aid CSV export error:",
                    err
                );

                window.alert(
                    err.message ||
                    "Unable to download Gift-Aid data."
                );
            }
        }
    );
}



/* =====================================================
   Member search
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

            memberSearchResults.hidden =
                false;

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


            item.type =
                "button";


            item.className =
                "list-group-item list-group-item-action";


            item.innerHTML = `
                ${member.membership_number}
                - ${member.first_name} ${member.surname}
                - ${member.tower?.name || "—"}
                - ${member.district?.name || "—"}
            `;


            item.addEventListener(
                "click",
                () => selectMember(member)
            );


            memberSearchResults.appendChild(
                item
            );
        }


        memberSearchResults.hidden =
            false;

    } catch (err) {

        console.error(
            "Member search error:",
            err
        );


        memberSearchResults.innerHTML = `
            <div class="list-group-item text-danger">
                ${err.message ||
                  "Unable to search members."}
            </div>
        `;

        memberSearchResults.hidden =
            false;
    }
}



/* =====================================================
   Select member
   ===================================================== */

async function selectMember(member) {

    memberSearchResults.innerHTML = "";
    memberSearchResults.hidden = true;


    memberSearchInput.value =
        `${member.membership_number} - ${member.first_name} ${member.surname}`;


    memberSearchInput.dataset.memberId =
        member.id;


    try {

        const user =
            await requireLogin();


        if (!user) {
            return;
        }


        await loadMemberGiftAidRelationships(
            member.id,
            user
        );

    } catch (err) {

        console.error(
            "Member Gift Aid error:",
            err
        );


        memberDetails.innerHTML = `
            <div class="alert alert-danger">
                ${err.message ||
                  "Unable to load Gift Aid relationships."}
            </div>
        `;
    }
}



/* =====================================================
   Member search type-ahead
   ===================================================== */

if (memberSearchInput) {

    memberSearchInput.addEventListener(
        "input",
        () => {

            /*
             * Typing again means the previously selected
             * member is no longer necessarily selected.
             */

            delete memberSearchInput.dataset.memberId;


            clearTimeout(
                memberSearchTimeout
            );


            const search =
                memberSearchInput.value.trim();


            /*
             * If the search box has been cleared,
             * return to the complete Gift Aid list.
             */

            if (!search) {

                loadAllMemberGiftAidRelationships();

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
   End Gift-Aid modal event handlers
   ===================================================== */

if (endGiftAidMemberOnlyButton) {

    endGiftAidMemberOnlyButton.addEventListener(
        "click",
        selectMemberOnly
    );
}


if (endGiftAidEntireFormButton) {

    endGiftAidEntireFormButton.addEventListener(
        "click",
        selectEntireForm
    );
}


if (endGiftAidBackButton) {

    endGiftAidBackButton.addEventListener(
        "click",
        backToEndGiftAidOptions
    );
}


if (endGiftAidConfirmButton) {

    endGiftAidConfirmButton.addEventListener(
        "click",
        confirmEndGiftAid
    );
}



/* =====================================================
   Automatically load all relationships
   on the appropriate Gift Aid page
   ===================================================== */

if (referenceResults) {
    loadAllGiftAidRelationships();
}


if (memberDetails) {
    loadAllMemberGiftAidRelationships();
}