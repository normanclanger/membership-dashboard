import {
    requireLogin
} from "/js/auth.js";

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
        `;


        if (canEdit) {

            const actionsCell =
                document.createElement(
                    "td"
                );


            const deleteButton =
                document.createElement(
                    "button"
                );


            deleteButton.type =
                "button";


            deleteButton.className =
                "btn btn-sm btn-danger";


            deleteButton.textContent =
                "Delete";


            deleteButton.addEventListener(
                "click",
                () =>
                    deleteGiftAidRelationship(
                        relationship.id,
                        user
                    )
            );


            actionsCell.appendChild(
                deleteButton
            );


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
        `;


        if (canEdit) {

            const actionsCell =
                document.createElement(
                    "td"
                );


            const deleteButton =
                document.createElement(
                    "button"
                );


            deleteButton.type =
                "button";


            deleteButton.className =
                "btn btn-sm btn-danger";


            deleteButton.textContent =
                "Delete";


            deleteButton.addEventListener(
                "click",
                () =>
                    deleteGiftAidRelationship(
                        relationship.id,
                        user
                    )
            );


            actionsCell.appendChild(
                deleteButton
            );


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
   Delete Gift Aid relationship
   ===================================================== */

async function deleteGiftAidRelationship(
    relationshipId,
    user
) {

    const confirmed =
        window.confirm(
            "Are you sure you want to delete this Gift Aid relationship?"
        );


    if (!confirmed) {
        return;
    }


    try {

        const response =
            await fetch(
                `${API_BASE}/api/gift-aid/${relationshipId}`,
                {
                    method: "DELETE",

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
                "Unable to delete Gift Aid relationship."
            );
        }


        /*
         * Refresh the current view.
         *
         * Reference page:
         * reload the current reference or full list.
         *
         * Member page:
         * reload the selected member.
         */

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

    } catch (err) {

        console.error(
            "Gift Aid delete error:",
            err
        );


        const error =
            document.createElement(
                "div"
            );


        error.className =
            "alert alert-danger mt-3";


        error.textContent =
            err.message ||
            "Unable to delete Gift Aid relationship.";


        if (memberDetails) {

            memberDetails.prepend(
                error
            );

        } else if (referenceResults) {

            referenceResults.prepend(
                error
            );
        }
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


        memberSearchResults.hidden = false;

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

        memberSearchResults.hidden = false;
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
   Automatically load all relationships
   on the appropriate Gift Aid page
   ===================================================== */

if (referenceResults) {
    loadAllGiftAidRelationships();
}


if (memberDetails) {
    loadAllMemberGiftAidRelationships();
}