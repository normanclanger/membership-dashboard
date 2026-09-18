import {
    requireLogin
} from "/js/auth.js";


const API_BASE =
    `${window.API_BASE_URL}`;


document.addEventListener(
    "DOMContentLoaded",
    async () => {

        const form =
            document.querySelector(
                "#declaration-form"
            );
			
		form.addEventListener(
            "submit",
            handleSave
        );	
		
		const process2ConfirmButton =
            document.querySelector("#process-2-confirm");

        process2ConfirmButton.addEventListener(
            "click",
            confirmProcess2
);

        const loading =
            document.querySelector(
                "#declaration-loading"
            );

        const error =
            document.querySelector(
                "#declaration-error"
            );

        const params =
            new URLSearchParams(
                window.location.search
            );

        const auditId =
            params.get("id");


        try {

            const user =
                await requireLogin();

            if (!user) {
                return;
            }


            /*
             * No audit ID means this is a
             * new declaration.
             *
             * Leave the form blank.
             */

            if (!auditId) {

                loading.hidden = true;
                form.hidden = false;

                return;
            }


            /*
             * Existing declaration:
             * load it from the admin API.
             */

            const response =
                await fetch(
                    `${API_BASE}/api/gift-aid/admin/declaration/edit?id=${encodeURIComponent(auditId)}`,
                    {
                        method: "GET",

                        headers: {
                            "Authorization":
                                `Bearer ${user.access_token}`
                        }
                    }
                );


            const result =
                await response.json();


            if (!response.ok) {

                throw new Error(
                    result.error ||
                    "Unable to load the Gift Aid declaration"
                );
            }


            populateForm(result);


            loading.hidden = true;
            form.hidden = false;

        } catch (err) {

            console.error(
                "Gift Aid declaration load error:",
                err
            );

            loading.hidden = true;

            error.textContent =
                err.message ||
                "Unable to load the Gift Aid declaration";

            error.hidden = false;
        }
    }
);


function populateForm(
    declaration
) {

    document.querySelector(
        "#member-name"
    ).value =
        `${declaration.first_name} ${declaration.surname}`;

    document.querySelector("#member-id").value =
        declaration.member_id;

    document.querySelector(
        "#membership-number"
    ).value =
        declaration.membership_number || "";


    document.querySelector(
        "#gift-aid-reference"
    ).value =
        declaration.gift_aid_reference || "";


    document.querySelector(
        "#declarer-name"
    ).value =
        declaration.declarer_name || "";


    document.querySelector(
        "#declarer-address-line-1"
    ).value =
        declaration.declarer_address_line_1 || "";


    document.querySelector(
        "#declarer-address-line-2"
    ).value =
        declaration.declarer_address_line_2 || "";


    document.querySelector(
        "#declarer-postcode"
    ).value =
        declaration.declarer_postcode || "";


    document.querySelector(
        "#email-address"
    ).value =
        declaration.email_address || "";


    document.querySelector(
        "#affirmed-date"
    ).value =
        declaration.affirmed_date || "";


    document.querySelector(
        "#wording-version-id"
    ).value =
        declaration.wording_version_id || "";


    document.querySelector(
        "#declaration-text"
    ).value =
        declaration.declaration_text || "";


    document.querySelector(
        "#affirmed"
    ).checked =
        declaration.affirmed === true;


    populateCoveredMembers(
        declaration.covered_members || []
    );
}



let coveredMembers = [];
let process2AuditId = null;

const coveredMemberSearch =
    document.querySelector(
        "#covered-member-search"
    );

const coveredMemberSearchButton =
    document.querySelector(
        "#covered-member-search-button"
    );
	
coveredMemberSearchButton.addEventListener(
    "click",
    searchCoveredMembers
);

const coveredMemberSearchResults =
    document.querySelector(
        "#covered-member-search-results"
    );


function populateCoveredMembers(
    members
) {

    coveredMembers = [];

    const container =
        document.querySelector(
            "#covered-members-list"
        );

    container.innerHTML = "";


    if (members.length === 0) {

        const empty =
            document.createElement(
                "p"
            );

        empty.textContent =
            "No covered members.";

        container.appendChild(
            empty
        );

        return;
    }


    members.forEach(
        member => {

            if (
                member.member_id !== undefined &&
                member.member_id !== null
            ) {

                coveredMembers.push({
                    member_id:
                        Number(member.member_id),

                    first_name:
                        member.first_name || "",

                    surname:
                        member.surname || "",

                    membership_number:
                        member.membership_number || ""
                });

            } else {

                /*
                 * Informal / unresolved member.
                 *
                 * Keep it separately so that it
                 * cannot accidentally be submitted.
                 */

                coveredMembers.push({
                    unresolved: true,

                    name:
                        member.name || "",

                    membership_number:
                        member.membership_number || ""
                });
            }
        }
    );


    renderCoveredMembers();
}

function renderCoveredMembers() {

    const container =
        document.querySelector(
            "#covered-members-list"
        );

    container.innerHTML = "";


    if (coveredMembers.length === 0) {

        const empty =
            document.createElement(
                "p"
            );

        empty.textContent =
            "No covered members.";

        container.appendChild(
            empty
        );

        return;
    }


    coveredMembers.forEach(
        member => {

            const row =
                document.createElement(
                    "div"
                );

            row.className =
                "d-flex align-items-center mb-2";


            const text =
                document.createElement(
                    "span"
                );

            text.className =
                "flex-grow-1";


            if (member.unresolved) {

                text.textContent =
                    `⚠ Unresolved: ${member.name} ` +
                    `(${member.membership_number})`;

            } else {

                text.textContent =
                    `${member.first_name} ` +
                    `${member.surname} ` +
                    `(${member.membership_number})`;
            }


            const removeButton =
                document.createElement(
                    "button"
                );

            removeButton.type =
                "button";

            removeButton.className =
                "btn btn-sm btn-warning";

            removeButton.textContent =
                "Remove";


            removeButton.addEventListener(
                "click",
                () => {

                    coveredMembers =
                        coveredMembers.filter(
                            existing =>
                                existing !== member
                        );

                    renderCoveredMembers();
                }
            );


            row.appendChild(
                text
            );

            row.appendChild(
                removeButton
            );

            container.appendChild(
                row
            );
        }
    );
}

async function searchCoveredMembers() {

    const searchInput =
        document.querySelector(
            "#covered-member-search"
        );

    const resultsContainer =
        document.querySelector(
            "#covered-member-search-results"
        );

    const search =
        searchInput.value.trim();


    resultsContainer.innerHTML =
        "";


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
                    method: "GET",

                    headers: {
                        "Authorization":
                            `Bearer ${user.access_token}`
                    }
                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            throw new Error(
                result.error ||
                "Unable to search for members"
            );
        }


        const members =
            Array.isArray(result)
                ? result
                : result.members || [];


        if (members.length === 0) {

            const empty =
                document.createElement(
                    "p"
                );

            empty.textContent =
                "No members found.";

            resultsContainer.appendChild(
                empty
            );

            return;
        }


        members.forEach(
            member => {

                const row =
                    document.createElement(
                        "div"
                    );

                row.className =
                    "d-flex align-items-center mb-2";


                const text =
                    document.createElement(
                        "span"
                    );
					
				text.className = "flex-grow-1";

                text.textContent =
                    `${member.first_name} ${member.surname} ` +
                    `(${member.membership_number})`;

                const unresolvedIndex =
                    coveredMembers.findIndex(
                        existing =>
                            existing.unresolved &&
                            existing.membership_number ===
                                member.membership_number
                    );


                if (unresolvedIndex !== -1) {

                    coveredMembers[unresolvedIndex] = {
                        member_id:
                            memberId,

                        membership_number:
                            member.membership_number,

                        first_name:
                            member.first_name,

                        surname:
                            member.surname
                    };

                    return;
}


                const alreadySelected =
                    coveredMembers.some(
                        existing =>
                            existing.member_id ===
                            Number(member.id)
                    );


                const addButton =
                    document.createElement(
                        "button"
                    );

                addButton.type =
                    "button";

                addButton.className =
                    "btn btn-sm btn-primary";
					
				addButton.style.width =
                    "70px";

                addButton.textContent =
                    alreadySelected
                        ? "Added"
                        : "Add";

                addButton.disabled =
                    alreadySelected;


                addButton.addEventListener(
                    "click",
                    () => {

                        addCoveredMember(
                            member
                        );

                        renderCoveredMembers();

                        searchCoveredMembers();
                    }
                );


                row.appendChild(
                    text
                );

                row.appendChild(
                    addButton
                );

                resultsContainer.appendChild(
                    row
                );
            }
        );

    } catch (error) {

        console.error(
            "Covered member search error:",
            error
        );

        resultsContainer.textContent =
            error.message ||
            "Unable to search for members.";
    }
}


function addCoveredMember(
    member
) {

    const memberId =
        Number(member.id);


    if (
        !Number.isInteger(memberId)
    ) {

        return;
    }


    if (
        memberId ===
        Number(
            document.querySelector(
                "#member-id"
            )?.value
        )
    ) {

        return;
    }


    const existingIndex =
        coveredMembers.findIndex(
            existing =>
                existing.unresolved &&
                existing.membership_number ===
                    member.membership_number
        );


    if (existingIndex !== -1) {

        coveredMembers[existingIndex] = {
            member_id:
                memberId,

            membership_number:
                member.membership_number,

            first_name:
                member.first_name,

            surname:
                member.surname
        };

        return;
    }


    const alreadySelected =
        coveredMembers.some(
            existing =>
                existing.member_id ===
                memberId
        );


    if (alreadySelected) {

        return;
    }


    coveredMembers.push({
        member_id:
            memberId,

        membership_number:
            member.membership_number,

        first_name:
            member.first_name,

        surname:
            member.surname
    });
}

async function handleSave(event) {

    event.preventDefault();

    const errorContainer =
        document.querySelector(
            "#declaration-error"
        );

    errorContainer.textContent =
        "";

    try {

        const user =
            await requireLogin();

        if (!user) {
            return;
        }


        const auditId =
            new URLSearchParams(
                window.location.search
            ).get("id");


        const mode =
            auditId
                ? "edit"
                : "new";


        const coveredMembersForSave =
            coveredMembers.map(
                member => {

                    if (member.unresolved) {
                        return {
                            name:
                                member.name,

                            membership_number:
                                member.membership_number
                        };
                    }

                    return {
                        member_id:
                            member.member_id,

                        first_name:
                            member.first_name,

                        surname:
                            member.surname,

                        membership_number:
                            member.membership_number
                    };
                }
            );


        const body = {
            mode:
                mode,

            audit_id:
                auditId
                    ? Number(auditId)
                    : null,

            member_id:
                Number(
                    document.querySelector(
                        "#member-id"
                    ).value
                ),

            declarer_name:
                document.querySelector(
                    "#declarer-name"
                ).value.trim(),

            declarer_address_line_1:
                document.querySelector(
                    "#declarer-address-line-1"
                ).value.trim(),

            declarer_address_line_2:
                document.querySelector(
                    "#declarer-address-line-2"
                ).value.trim(),

            declarer_postcode:
                document.querySelector(
                    "#declarer-postcode"
                ).value.trim(),

            email_address:
                document.querySelector(
                    "#email-address"
                ).value.trim(),

            affirmed_date:
                document.querySelector(
                    "#affirmed-date"
                ).value,

            wording_version_id:
                Number(
                    document.querySelector(
                        "#wording-version-id"
                    ).value
                ),

            declaration_text:
                document.querySelector(
                    "#declaration-text"
                ).value,

            affirmed:
                document.querySelector(
                    "#affirmed"
                ).checked,

            covered_members:
                coveredMembersForSave
        };


        const response =
            await fetch(
                `${API_BASE}/api/gift-aid/admin/declaration/save`,
                {
                    method:
                        "POST",

                    headers: {
                        "Authorization":
                            `Bearer ${user.access_token}`,

                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(body)
                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            throw new Error(
                result.error ||
                "Unable to save Gift Aid declaration"
            );
        }


        console.log(
            "Gift Aid declaration saved:",
            result
        );


        if (
            result.relationships_match
        ) {

            alert(
                "Declaration saved."
            );

        } else {

            showProcess2(
                result
            );
        }


    } catch (error) {

        console.error(
            "Gift Aid declaration save error:",
            error
        );

        errorContainer.textContent =
            error.message ||
            "Unable to save Gift Aid declaration.";
    }
}

function showProcess2(result) {

    const process2 =
        document.querySelector(
            "#process-2"
        );

    const added =
        document.querySelector(
            "#process-2-added"
        );

    const removed =
        document.querySelector(
            "#process-2-removed"
        );

    process2AuditId = result.audit_id;

    added.innerHTML =
        "";

    removed.innerHTML =
        "";


    if (
        result.added_member_details &&
        result.added_member_details.length > 0
    ) {

        result.added_member_details.forEach(
            member => {

                const item =
                    document.createElement(
                        "p"
                    );

                item.textContent =
                    `${member.first_name} ` +
                    `${member.surname} ` +
                    `(${member.membership_number})`;

                added.appendChild(
                    item
                );
            }
        );

    } else {

        added.textContent =
            "None";
    }


    if (
        result.removed_member_details &&
        result.removed_member_details.length > 0
    ) {

        result.removed_member_details.forEach(
            member => {

                const item =
                    document.createElement(
                        "p"
                    );

                item.textContent =
                    `${member.first_name} ` +
                    `${member.surname} ` +
                    `(${member.membership_number})`;

                removed.appendChild(
                    item
                );
            }
        );

    } else {

        removed.textContent =
            "None";
    }


    process2.hidden =
        false;
}

async function confirmProcess2() {

    try {

        const confirmButton =
            document.querySelector("#process-2-confirm");

        confirmButton.disabled = true;


        const auditId =
            process2AuditId;

        if (!auditId) {

            throw new Error(
                "No pending declaration audit ID is available"
            );
        }


        const user =
            await requireLogin();

        if (!user) {

            confirmButton.disabled = false;

            return;
        }


        const response =
            await fetch(
                `${API_BASE}/api/gift-aid/admin/pending/${encodeURIComponent(auditId)}/confirm-relationships`,
                {
                    method: "POST",

                    headers: {
                        "Authorization":
                            `Bearer ${user.access_token}`,

                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        confirmed: true
                    })
                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            throw new Error(
                `HTTP ${response.status}: ` +
                (
                    result.error ||
                    JSON.stringify(result)
                )
            );
        }


        const process2 =
            document.querySelector(
                "#process-2"
            );

        process2.hidden =
            true;


        const success =
            document.createElement(
                "div"
            );

        success.className =
            "alert alert-success mt-3";


        const message =
            document.createElement(
                "p"
            );

        message.textContent =
            "Declaration and Gift Aid relationships confirmed.";


        const dashboardLink =
            document.createElement(
                "a"
            );

        dashboardLink.href =
            "/giftaiddashboard/";

        dashboardLink.className =
            "btn btn-primary";

        dashboardLink.textContent =
            "Back to Gift Aid dashboard";


        success.appendChild(
            message
        );

        success.appendChild(
            dashboardLink
        );


        process2.parentNode.insertBefore(
            success,
            process2
        );


    } catch (error) {

        console.error(
            "Process 2 confirmation error:",
            error
        );


        const confirmButton =
            document.querySelector(
                "#process-2-confirm"
            );

        if (confirmButton) {

            confirmButton.disabled =
                false;
        }


        document.querySelector(
            "#declaration-error"
        ).textContent =
            error.message ||
            "Unable to confirm Gift Aid relationships.";
    }
}