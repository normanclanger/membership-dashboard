import { requireLogin } from "/js/auth.js";

const API_BASE = `${window.API_BASE_URL}/api`;

const ALLOWED_GROUPS = [
    "MembershipAdmin",
    "ApplicationAdmin"
];

function showError(message) {
    const error = document.querySelector("#create-member-error");

    error.textContent = message;
    error.hidden = false;
}

function hideError() {
    const error = document.querySelector("#create-member-error");

    error.textContent = "";
    error.hidden = true;
}

function getGroups(user) {
    const groups = user?.profile?.["cognito:groups"];

    if (!groups) {
        return [];
    }

    return Array.isArray(groups) ? groups : [groups];
}

function userCanCreate(user) {
    const groups = getGroups(user);

    return groups.some(group =>
        ALLOWED_GROUPS.includes(group)
    );
}

async function apiGet(path, user) {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: {
            Authorization: `Bearer ${user.access_token}`
        }
    });

    if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
    }

    return response.json();
}

function populateSelect(selectId, items, labelFunction) {
    const select = document.querySelector(`#${selectId}`);

    select.innerHTML =
        '<option value="">Please select...</option>';

    items.forEach(item => {
        const option = document.createElement("option");

        option.value = item.id;
        option.textContent = labelFunction(item);

        select.appendChild(option);
    });
}

async function loadFormData(user) {
    const [
        membersData,
        towersData,
        classesData,
        statusesData,
        typesData
    ] = await Promise.all([
        apiGet("/members", user),
        apiGet("/towers", user),
        apiGet("/membership-classes", user),
        apiGet("/membership-statuses", user),
        apiGet("/full-member-types", user)
    ]);

    const lastCreated =
        membersData.last_created?.membership_number;

    document.querySelector("#last-membership-number").textContent =
        lastCreated || "None";

    populateSelect(
        "tower_id",
        towersData.towers || [],
        tower => `${tower.tower_name} (${tower.district_code})`
    );

    const classes =
        classesData.membership_classes || [];

    populateSelect(
        "membership_class_id",
        classes,
        item => `${item.code} - ${item.name}`
    );

    const fullClass =
        classes.find(
            item => item.code.toUpperCase() === "FULL"
        );

    if (fullClass) {
        document.querySelector("#membership_class_id").value =
            fullClass.id;
    }



    const statuses =
      statusesData.membership_statuses || [];

    populateSelect(
        "membership_status_id",
        statuses,
        item => `${item.code} - ${item.name}`
    );

    const activeStatus =
        statuses.find(
            item => item.code.toUpperCase() === "ACTIVE"
        );

    if (activeStatus) {
        document.querySelector("#membership_status_id").value =
            activeStatus.id;
    }

    populateSelect(
        "full_member_type_id",
        typesData.full_member_types || [],
        item => `${item.code} - ${item.name}`
    );
}

function updateMemberTypeState() {
    const classSelect =
        document.querySelector("#membership_class_id");

    const typeSelect =
        document.querySelector("#full_member_type_id");

    const selectedOption =
        classSelect.options[classSelect.selectedIndex];

    const selectedClass =
        selectedOption?.textContent || "";

    const isFull =
        selectedClass.trim().toUpperCase().startsWith("FULL");

    if (isFull) {
        typeSelect.disabled = false;
    } else {
        typeSelect.disabled = true;
        typeSelect.value = "";
    }
}

async function createMember(user) {
    const form = document.querySelector("#create-member-form");
    const button = document.querySelector("#create-member-button");

    const formData = new FormData(form);

    const body = {
        membership_number:
            formData.get("membership_number").trim(),

        first_name:
            formData.get("first_name").trim(),

        surname:
            formData.get("surname").trim(),

        tower_id:
            Number(formData.get("tower_id")),

        date_of_birth:
            formData.get("date_of_birth") || null,

        membership_class_id:
            formData.get("membership_class_id")
                ? Number(formData.get("membership_class_id"))
                : null,

        membership_status_id:
            formData.get("membership_status_id")
                ? Number(formData.get("membership_status_id"))
                : null,

        full_member_type_id:
            formData.get("full_member_type_id")
                ? Number(formData.get("full_member_type_id"))
                : null
    };

    button.disabled = true;
    button.textContent = "Creating...";

    try {
        const response = await fetch(
            `${API_BASE}/members`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json",
                    Authorization:
                        `Bearer ${user.access_token}`
                },

                body: JSON.stringify(body)
            }
        );

        const data = await response.json();

        if (!response.ok) {
            if (response.status === 409) {
                throw new Error(
                    "That membership number already exists."
                );
            }

            if (response.status === 403) {
                throw new Error(
                    "You do not have permission to create members."
                );
            }

            if (response.status === 400) {
                throw new Error(
                    data.error || "The member details were not valid."
                );
            }

            throw new Error(
                data.error ||
                `API returned ${response.status}`
            );
        }

        if (!data.member || !data.member.id) {
            throw new Error(
                "The member was created but no member ID was returned."
            );
        }

        window.location.href =
            `/member/?id=${data.member.id}`;

    } catch (error) {
        console.error(error);

        showError(error.message);

        button.disabled = false;
        button.textContent = "Create member";
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    hideError();

    try {
        const user = await requireLogin();

        if (!user) {
            return;
        }

        window.currentUser = user;

        if (!userCanCreate(user)) {
            document.querySelector("#create-member-page").innerHTML =
                "<p>You do not have permission to create members.</p>";
            return;
        }

        await loadFormData(user);

	document
    		.querySelector("#membership_class_id")
    		.addEventListener("change", updateMemberTypeState);

	updateMemberTypeState();

        document
            .querySelector("#create-member-form")
            .addEventListener("submit", async event => {
                event.preventDefault();

                hideError();

                await createMember(user);
            });

    } catch (error) {
        console.error(error);

        showError(
            "Unable to initialise the create member page."
        );
    }
});
