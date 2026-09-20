import { requireLogin } from "/js/auth.js";

const API_BASE = `${window.API_BASE_URL}`;

let auditId = null;
let requestingMemberId = null;
let selectedMember = null;
let selectedDeclaration = null;

document.addEventListener("DOMContentLoaded", async () => {

const loading =
    document.querySelector("#loading");

const form =
    document.querySelector("#coverage-form");

const error =
    document.querySelector("#declaration-error");

const searchButton =
    document.querySelector("#covered-member-search-button");

const searchInput =
    document.querySelector("#covered-member-search");

const resolveButton =
    document.querySelector("#resolve-coverage-button");
	
resolveButton.addEventListener(
    "click",
    resolveCoverage
);

const confirmProcess2Button =
    document.querySelector(
        "#confirm-process-2-button"
    );

confirmProcess2Button.addEventListener(
    "click",
    () => {
        console.log("Confirm relationships button clicked");
        confirmProcess2();
    }
);

try {

    const params =
        new URLSearchParams(
            window.location.search
        );

    auditId =
        params.get("id");

    if (!auditId) {
        throw new Error(
            "No Gift Aid audit ID was supplied."
        );
    }

    const user =
        await requireLogin();

    if (!user) {
        return;
    }

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
            "Unable to load the coverage request."
        );
    }

    /*
     * Make sure this is actually an unresolved
     * Covered Elsewhere request.
     */
    if (
        result.action !== "COVERED_ELSEWHERE" ||
        result.status !== "PENDING_REVIEW" ||
        result.pending_review_type !== "COVERAGE_REQUEST"
    ) {
        throw new Error(
            "This is not a current Covered Elsewhere request."
        );
    }

    /*
     * Store the requesting member ID.
     */
    requestingMemberId =
        Number(result.member_id);

    if (!Number.isInteger(requestingMemberId)) {
        throw new Error(
            "The coverage request has an invalid requesting member."
        );
    }

    /*
     * Populate requesting member.
     */
    document.querySelector(
        "#requesting-member-name"
    ).textContent =
        `${result.first_name} ${result.surname}`;

    document.querySelector(
        "#requesting-membership-number"
    ).textContent =
        result.membership_number;

    /*
     * Populate the informal description of
     * the requested declaration holder.
     */
    const coveredMembers =
        Array.isArray(result.covered_members)
            ? result.covered_members
            : [];

    if (coveredMembers.length !== 1) {
        throw new Error(
            "The coverage request does not contain exactly one requested declaration holder."
        );
    }

    const requestedMember =
        coveredMembers[0];

    const description =
        requestedMember.description ||
        requestedMember.name ||
        requestedMember.membership_number ||
        "No description supplied.";

    document.querySelector(
        "#requested-declaration-description"
    ).textContent =
        description;

    /*
     * Wire the member search.
     */
    searchButton.addEventListener(
        "click",
        searchMembers
    );

    searchInput.addEventListener(
        "keydown",
        event => {
            if (event.key === "Enter") {
                event.preventDefault();
                searchMembers();
            }
        }
    );

    /*
     * Process 3 will be wired later.
     */
    resolveButton.disabled = true;

    loading.hidden = true;
    form.hidden = false;

} catch (err) {

    console.error(
        "Covered Elsewhere load error:",
        err
    );

    loading.hidden = true;

    error.textContent =
        err.message ||
        "Unable to load the coverage request.";

    error.hidden = false;
}

});

async function searchMembers() {

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

resultsContainer.innerHTML = "";

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
            "Unable to search for members."
        );
    }

    const members =
        Array.isArray(result)
            ? result
            : result.members || [];

    if (members.length === 0) {

        const empty =
            document.createElement("p");

        empty.textContent =
            "No members found.";

        resultsContainer.appendChild(
            empty
        );

        return;
    }

    members.forEach(member => {

        const row =
            document.createElement("div");

        row.className =
            "d-flex align-items-center gap-2 mb-2";

        const text =
            document.createElement("span");

        text.className =
            "flex-grow-1";

        text.textContent =
            `${member.first_name} ` +
            `${member.surname} ` +
            `(${member.membership_number})`;

        const addButton =
            document.createElement("button");

        addButton.type =
            "button";

        addButton.className =
            "btn btn-sm btn-primary";

        addButton.textContent =
            "Add";

        addButton.addEventListener(
            "click",
            () => selectMember(member)
        );

        row.appendChild(text);
        row.appendChild(addButton);

        resultsContainer.appendChild(row);
    });

} catch (error) {

    console.error(
        "Covered Elsewhere member search error:",
        error
    );

    resultsContainer.textContent =
        error.message ||
        "Unable to search for members.";
}

}

async function selectMember(member) {

const resultsContainer =
    document.querySelector(
        "#covered-member-search-results"
    );

const selectedDeclarationElement =
    document.querySelector(
        "#selected-declaration"
    );

const resolveButton =
    document.querySelector(
        "#resolve-coverage-button"
    );

resultsContainer.innerHTML = "";

selectedDeclarationElement.hidden = true;
resolveButton.disabled = true;

selectedMember = null;
selectedDeclaration = null;

document.querySelector(
    "#selected-member-name"
).textContent = "";

document.querySelector(
    "#selected-membership-number"
).textContent = "";

document.querySelector(
    "#selected-gift-aid-reference"
).textContent = "";

try {

    const user =
        await requireLogin();

    if (!user) {
        return;
    }

    const memberId =
        Number(member.id);

    if (!Number.isInteger(memberId)) {
        throw new Error(
            "The selected member has an invalid ID."
        );
    }

    /*
     * The requesting member cannot be selected
     * as the declaration holder.
     */
    if (memberId === requestingMemberId) {

        throw new Error(
            "The requesting member cannot be selected as the declaration holder."
        );
    }

    const response =
        await fetch(
            `${API_BASE}/api/gift-aid/admin/declaration-for-member?id=${encodeURIComponent(memberId)}`,
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
            "This member does not have a current usable Gift Aid declaration."
        );
    }

    selectedMember = member;
    selectedDeclaration = result;

    document.querySelector(
        "#selected-member-name"
    ).textContent =
        `${result.first_name} ${result.surname}`;

    document.querySelector(
        "#selected-membership-number"
    ).textContent =
        result.membership_number;

    document.querySelector(
        "#selected-gift-aid-reference"
    ).textContent =
        result.gift_aid_reference;

    selectedDeclarationElement.hidden = false;

    /*
     * Check whether the requesting member is
     * already covered by this declaration.
     */
    const declarationCoveredMembers =
        Array.isArray(result.covered_members)
            ? result.covered_members
            : [];

    const alreadyCovered =
        declarationCoveredMembers.some(
            coveredMember =>
                Number(
                    coveredMember.member_id
                ) === requestingMemberId
        );

    if (alreadyCovered) {

        showCoveredAlready();

    } else {

        showReadyToResolve();
    }

} catch (error) {

    console.error(
        "Covered Elsewhere declaration lookup error:",
        error
    );

    showSelectionError(
        error.message ||
        "Unable to load this member's Gift Aid declaration."
    );
}

}


function showSelectionError(message) {

    const selectedDeclaration =
        document.querySelector(
            "#selected-declaration"
        );

    selectedDeclaration.hidden =
        false;

    selectedDeclaration.classList.remove(
        "alert-info",
        "alert-success"
    );

    selectedDeclaration.classList.add(
        "alert-warning"
    );

    const messageElement =
        document.querySelector(
            "#covered-already-message"
        );

    if (messageElement) {
        messageElement.remove();
    }

    const existingError =
        document.querySelector(
            "#selection-error-message"
        );

    if (existingError) {
        existingError.remove();
    }

    const errorElement =
        document.createElement("p");

    errorElement.id =
        "selection-error-message";

    errorElement.className =
        "mb-0 mt-3";

    errorElement.textContent =
        message;

    selectedDeclaration.appendChild(
        errorElement
    );

    const resolveButton =
        document.querySelector(
            "#resolve-coverage-button"
        );

    resolveButton.disabled =
        true;
		
	

}

function showCoveredAlready() {

const selectedDeclaration =
    document.querySelector(
        "#selected-declaration"
    );

selectedDeclaration.classList.remove(
    "alert-warning"
);

selectedDeclaration.classList.add(
    "alert-success"
);

let message =
    document.querySelector(
        "#covered-already-message"
    );

if (!message) {

    message =
        document.createElement("p");

    message.id =
        "covered-already-message";

    message.className =
        "mb-0 mt-3";

    selectedDeclaration.appendChild(
        message
    );
}
const errorMessage =
    document.querySelector(
        "#selection-error-message"
    );

if (errorMessage) {
    errorMessage.remove();
}

message.textContent =
    "The requesting member is already covered by this declaration.";

const resolveButton =
    document.querySelector(
        "#resolve-coverage-button"
    );

resolveButton.textContent =
    "Mark request complete";

resolveButton.disabled =
    false;

}

function showReadyToResolve() {

const selectedDeclaration =
    document.querySelector(
        "#selected-declaration"
    );

selectedDeclaration.classList.remove(
    "alert-success",
    "alert-warning"
);

selectedDeclaration.classList.add(
    "alert-info"
);

const message =
    document.querySelector(
        "#covered-already-message"
    );

if (message) {
    message.remove();
	
	
}

const errorMessage =
    document.querySelector(
        "#selection-error-message"
    );

if (errorMessage) {
    errorMessage.remove();
}

const resolveButton =
    document.querySelector(
        "#resolve-coverage-button"
    );

resolveButton.textContent =
    "Resolve coverage request";

resolveButton.disabled =
    false;

}

async function resolveCoverage() {

    const resolveButton =
        document.querySelector(
            "#resolve-coverage-button"
        );

    /*
     * The same button is also used for the
     * separate "Mark request complete" action.
     * That will be wired separately.
     */
    if (
        resolveButton.textContent.trim() ===
        "Mark request complete"
    ) {
        return;
    }

    if (!selectedMember || !selectedDeclaration) {
        return;
    }

    resolveButton.disabled = true;
    resolveButton.textContent =
        "Resolving...";

    try {

        const user =
            await requireLogin();

        if (!user) {
            return;
        }

        const response =
            await fetch(
                `${API_BASE}/api/gift-aid/admin/pending/${encodeURIComponent(auditId)}/resolve-coverage`,
                {
                    method: "POST",
                    headers: {
                        "Authorization":
                            `Bearer ${user.access_token}`,
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        resolutions: [
                            {
                                covered_member_index: 0,
                                member_id:
                                    Number(
                                        selectedMember.id
                                    )
                            }
                        ],
                        add_requester: true
                    })
                }
            );

        const result =
            await response.json();

        console.log(
            "Covered Elsewhere Process 3 result:",
            result
        );

        if (!response.ok) {
            throw new Error(
                result.error ||
                "Unable to resolve the coverage request."
            );
        }


        /*
         * Process 3 has created the new receiving
         * declaration. Check whether its relationships
         * already match the live relationships.
         */

        const selectedDeclarationElement =
            document.querySelector(
                "#selected-declaration"
            );

        selectedDeclarationElement.classList.remove(
            "alert-info",
            "alert-warning"
        );

        selectedDeclarationElement.classList.add(
            "alert-success"
        );

        const message =
            document.querySelector(
                "#selection-error-message"
            );

        if (message) {
            message.remove();
        }

        /*
         * Process 2 is required if the relationship
         * sets do not match.
         */
        if (!result.relationships_match) {

            const relationshipIds =
                Array.isArray(result.relationship_ids)
                    ? result.relationship_ids.map(Number)
                    : [];

            const liveRelationshipIds =
                Array.isArray(result.live_relationship_ids)
                    ? result.live_relationship_ids.map(Number)
                    : [];

            const addedMembers =
                relationshipIds.filter(
                    id =>
                        !liveRelationshipIds.includes(id)
                );

            const removedMembers =
                liveRelationshipIds.filter(
                    id =>
                        !relationshipIds.includes(id)
                );

            /*
             * Hide the declaration selection area
             * now that Process 3 is complete.
             */
            selectedDeclarationElement.hidden =
                true;

            resolveButton.hidden =
                true;

            /*
             * Show Process 2.
             */
            const process2 =
                document.querySelector(
                    "#process-2"
                );

            process2.hidden =
                false;

            /*
             * Display members to add.
             */
            const addedContainer =
                document.querySelector(
                    "#process-2-added"
                );

            await displayRelationshipMembers(
                addedContainer,
                addedMembers
            );

            /*
             * Display members to remove.
             */
            const removedContainer =
                document.querySelector(
                    "#process-2-removed"
    )            ;

            await displayRelationshipMembers(
                removedContainer,
                removedMembers
            );

            /*
             * Store the new declaration audit ID
             * for Process 2.
             */
            process2.dataset.auditId =
                result.audit_id;

        } else {

            /*
             * No relationship changes are required.
             * Process 3 is completely finished.
             */
            resolveButton.textContent =
                "Resolved";

            resolveButton.disabled =
                true;
        }



    } catch (error) {

        console.error(
            "Covered Elsewhere resolution error:",
            error
        );

        resolveButton.disabled =
            false;

        resolveButton.textContent =
            "Resolve coverage request";

        showSelectionError(
            error.message ||
            "Unable to resolve the coverage request."
        );
    }
}

async function displayRelationshipMembers(
    container,
    memberIds
) {

    container.innerHTML = "";

    if (memberIds.length === 0) {

        container.textContent =
            "None";

        return;
    }

    const user =
        await requireLogin();

    if (!user) {
        return;
    }

    for (const memberId of memberIds) {

        const row =
            document.createElement("div");

        row.className =
            "mb-2";

        try {

            const response =
                await fetch(
                    `${API_BASE}/api/members/${encodeURIComponent(memberId)}`,
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
                    "Unable to load member."
                );
            }

            row.textContent =
                `${result.member.first_name} ` +
                `${result.member.surname} ` +
                `(${result.member.membership_number})`;

        } catch (error) {

            console.error(
                `Unable to load member ${memberId}:`,
                error
            );

            /*
             * Fall back to the ID if the lookup
             * fails, rather than hiding the change.
             */
            row.textContent =
                `Member ID ${memberId}`;
        }

        container.appendChild(row);
    }
}

async function confirmProcess2() {

    const process2 =
        document.querySelector(
            "#process-2"
        );

    const confirmButton =
        document.querySelector(
            "#confirm-process-2-button"
        );

    const process2AuditId =
        process2.dataset.auditId;

    if (!process2AuditId) {

        showSelectionError(
            "No declaration audit ID is available for relationship confirmation."
        );

        return;
    }

    confirmButton.disabled = true;
    confirmButton.textContent =
        "Confirming...";

    try {

        const user =
            await requireLogin();

        if (!user) {
            return;
        }

        const response =
            await fetch(
                `${API_BASE}/api/gift-aid/admin/pending/${encodeURIComponent(process2AuditId)}/confirm-relationships`,
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

        console.log(
            "Covered Elsewhere Process 2 result:",
            result
        );

        if (!response.ok) {

            throw new Error(
                result.error ||
                "Unable to confirm the Gift Aid relationships."
            );
        }

        /*
         * Process 2 has completed successfully.
         * Hide the relationship section and show
         * a success message.
         */
        process2.hidden = true;

        const success =
            document.createElement("div");

        success.className =
            "alert alert-success mt-4";

        success.textContent =
            "The Covered Elsewhere request has been resolved and the Gift Aid relationships have been updated.";

        process2.parentNode.insertBefore(
            success,
            process2
        );

        confirmButton.textContent =
            "Confirmed";

    } catch (error) {

        console.error(
            "Covered Elsewhere Process 2 error:",
            error
        );

        confirmButton.disabled =
            false;

        confirmButton.textContent =
            "Confirm relationships";

        const process2Error =
            document.querySelector(
                "#process-2-error"
            );

        if (process2Error) {
            process2Error.remove();
        }

        const errorElement =
            document.createElement("div");

        errorElement.id =
            "process-2-error";

        errorElement.className =
            "alert alert-danger mt-3";

        errorElement.textContent =
            error.message ||
            "Unable to confirm the Gift Aid relationships.";

        process2.appendChild(
            errorElement
        );
    }
}