import {
    requireLogin
} from "/js/auth.js";


const API_BASE =
    `${window.API_BASE_URL}`;


const totalMembers =
    document.querySelector(
        "#gift-aid-total-members"
    );


const confirmedDeclarations =
    document.querySelector(
        "#gift-aid-confirmed-declarations"
    );


const pendingReview =
    document.querySelector(
        "#gift-aid-pending-review"
    );


const declined =
    document.querySelector(
        "#gift-aid-declined"
    );


const cancelled =
    document.querySelector(
        "#gift-aid-cancelled"
    );


const coveredElsewhere =
    document.querySelector(
        "#gift-aid-covered-elsewhere"
    );


const membersInvited =
    document.querySelector(
        "#gift-aid-members-invited"
    );


const openInvitations =
    document.querySelector(
        "#gift-aid-open-invitations"
    );


const usedInvitations =
    document.querySelector(
        "#gift-aid-used-invitations"
    );

const relationshipMismatchesCount =
    document.querySelector(
        "#gift-aid-relationship-mismatches-count"
    );

const relationshipMismatches =
    document.querySelector(
        "#gift-aid-relationship-mismatches"
    );


const unresolvedMembersCount =
    document.querySelector(
        "#gift-aid-unresolved-members-count"
    );

const unresolvedMembers =
    document.querySelector(
        "#gift-aid-unresolved-members"
    );


const coverageRequestsCount =
    document.querySelector(
        "#gift-aid-coverage-requests-count"
    );

const coverageRequests =
    document.querySelector(
        "#gift-aid-coverage-requests"
    );


const coveredElsewhereReviewsCount =
    document.querySelector(
        "#gift-aid-covered-elsewhere-reviews-count"
    );

const coveredElsewhereReviews =
    document.querySelector(
        "#gift-aid-covered-elsewhere-reviews"
    );
	
const missingRelationshipsCount =
    document.querySelector(
        "#gift-aid-missing-relationships-count"
    );

const missingRelationships =
    document.querySelector(
        "#gift-aid-missing-relationships"
    );


const extraRelationshipsCount =
    document.querySelector(
        "#gift-aid-extra-relationships-count"
    );

const extraRelationships =
    document.querySelector(
        "#gift-aid-extra-relationships"
    );


const inactiveRelationshipsCount =
    document.querySelector(
        "#gift-aid-inactive-relationships-count"
    );

const inactiveRelationships =
    document.querySelector(
        "#gift-aid-inactive-relationships"
    );


const noDeclarationCount =
    document.querySelector(
        "#gift-aid-no-declaration-count"
    );

const noDeclaration =
    document.querySelector(
        "#gift-aid-no-declaration"
    );	

const error =
    document.querySelector(
        "#reports-dashboard-error"
    );


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


function formatNumber(value) {

    return Number(value).toLocaleString(
        "en-GB"
    );
}


async function loadSummary() {

    clearError();


    try {

        const user =
            await requireLogin();


        if (!user) {
            return;
        }


        const response =
            await fetch(
                `${API_BASE}/api/gift-aid/admin/dashboard`,
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
                "Unable to load Gift Aid dashboard."
            );
        }


        totalMembers.textContent =
            formatNumber(
                data.total_members
            );


        confirmedDeclarations.textContent =
            formatNumber(
                data.confirmed_declarations
            );


        pendingReview.textContent =
            formatNumber(
                data.pending_review
            );


        declined.textContent =
            formatNumber(
                data.declined
            );


        cancelled.textContent =
            formatNumber(
                data.cancelled
            );


        coveredElsewhere.textContent =
            formatNumber(
                data.covered_elsewhere
            );


        membersInvited.textContent =
            formatNumber(
                data.members_invited
            );


        openInvitations.textContent =
            formatNumber(
                data.open_invitations
            );


        usedInvitations.textContent =
            formatNumber(
                data.used_invitations
            );
			
			
		populateExceptions(
            relationshipMismatches,
            relationshipMismatchesCount,
            data.relationship_mismatches || [],
            "No relationship mismatches."
        );


        populateExceptions(
            unresolvedMembers,
            unresolvedMembersCount,
            data.unresolved_members || [],
            "No unresolved members."
        );


        populateExceptions(
            coverageRequests,
            coverageRequestsCount,
            data.coverage_requests || [],
            "No coverage requests."
        );


        populateExceptions(
            coveredElsewhereReviews,
            coveredElsewhereReviewsCount,
            data.covered_elsewhere_reviews || [],
            "No covered-elsewhere reviews.",
            true
        );
		
		populateRelationshipConsistency(
            missingRelationships,
              missingRelationshipsCount,
              data.missing_relationships || [],
              "No missing relationships."
          );

          populateRelationshipConsistency(
              extraRelationships,
              extraRelationshipsCount,
              data.extra_relationships || [],
              "No extra relationships."
          );

          populateRelationshipConsistency(
              inactiveRelationships,
              inactiveRelationshipsCount,
              data.inactive_relationships || [],
              "No inactive relationships."
          );

          populateRelationshipConsistency(
              noDeclaration,
              noDeclarationCount,
              data.no_declaration_relationships || [],
              "No relationships without declarations."
          );

    } catch (err) {

        console.error(
            "Gift Aid dashboard error:",
            err
        );


        showError(
            err.message ||
            "Unable to load Gift Aid dashboard."
        );
    }
}

function populateExceptions(
    container,
    countElement,
    items,
    emptyMessage,
    coveredElsewhere = false
) {

    countElement.textContent =
        formatNumber(items.length);

    container.innerHTML = "";


    if (items.length === 0) {

        container.textContent =
            emptyMessage;

        return;
    }


    items.forEach(item => {

        const row =
            document.createElement("div");

        row.className =
            "mb-3";


        const description =
            document.createElement("div");

        if (item.gift_aid_reference !== null) {

            description.textContent =
                `${item.first_name} ` +
                `${item.surname} ` +
                `(${item.membership_number}) ` +
                `— Gift Aid ref ${item.gift_aid_reference}`;

        } else {

            description.textContent =
                `${item.first_name} ` +
                `${item.surname} ` +
                `(${item.membership_number})`;
        }


        row.appendChild(
            description
        );


        const link =
            document.createElement("a");


        if (coveredElsewhere) {

            link.href =
                `/gift-aid/declarations/covered-elsewhere/?id=${encodeURIComponent(item.audit_id)}`;

            link.textContent =
                "Manage covered-elsewhere request";

        } else {

            link.href =
                `/gift-aid/declarations/edit/?id=${encodeURIComponent(item.audit_id)}`;

            link.textContent =
                "Edit declaration";
        }


        row.appendChild(
            link
        );

        container.appendChild(
            row
        );
    });
}

function populateRelationshipConsistency(
    container,
    countElement,
    items,
    emptyMessage
) {
    countElement.textContent =
        formatNumber(items.length);

    container.innerHTML = "";

    if (items.length === 0) {
        container.textContent =
            emptyMessage;
        return;
    }

    items.forEach(item => {
        const row =
            document.createElement("div");

        row.className =
            "mb-3";

        const description =
            document.createElement("div");

        description.textContent =
            `Gift Aid ref ${item.gift_aid_reference} — ` +
            `${item.first_name} ` +
            `${item.surname} ` +
            `(${item.membership_number})`;

        row.appendChild(
            description
        );

        container.appendChild(
            row
        );
    });
}

loadSummary();