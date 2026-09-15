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


loadSummary();