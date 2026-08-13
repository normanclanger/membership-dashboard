import { requireLogin } from "/js/auth.js";

const API_BASE =
    "https://ns6zyyxykl.execute-api.eu-north-1.amazonaws.com/api";

const ALLOWED_GROUPS = [
    "MembershipAdmin",
    "ApplicationAdmin"
];

function showError(message) {
    const error = document.querySelector("#patch-member-error");

    error.textContent = message;
    error.hidden = false;
}

function hideError() {
    const error = document.querySelector("#patch-member-error");

    error.textContent = "";
    error.hidden = true;
}

function getGroups(user) {
    const groups = user?.profile?.["cognito:groups"];

    if (!groups) {
        return [];
    }

    return Array.isArray(groups)
        ? groups
        : [groups];
}

function userCanPatch(user) {
    const groups = getGroups(user);

    return groups.some(group =>
        ALLOWED_GROUPS.includes(group)
    );
}

async function apiGet(path, user) {
    const response = await fetch(
        `${API_BASE}${path}`,
        {
            headers: {
                Authorization:
                    `Bearer ${user.access_token}`
            }
        }
    );

    if (!response.ok) {
        throw new Error(
            `API returned ${response.status}`
        );
    }

    return response.json();
}

function populateSelect(
    selectId,
    items,
    labelFunction
) {
    const select =
        document.querySelector(`#${selectId}`);

    select.innerHTML =
        '<option value="">Please select...</option>';

    items.forEach(item => {

        const option =
            document.createElement("option");

        option.value = item.id;
        option.textContent =
            labelFunction(item);

        select.appendChild(option);
    });
}

function updateMemberTypeState() {

    const classSelect =
        document.querySelector(
            "#membership_class_id"
        );

    const typeSelect =
        document.querySelector(
            "#full_member_type_id"
        );

    const selectedOption =
        classSelect.options[
            classSelect.selectedIndex
        ];

    const selectedClass =
        selectedOption?.textContent || "";

    const isFull =
        selectedClass
            .trim()
            .toUpperCase()
            .startsWith("FULL");

    if (isFull) {
        typeSelect.disabled = false;
    } else {
        typeSelect.disabled = true;
        typeSelect.value = "";
    }
}

async function loadFormData(user, member) {

    const [
        towersData,
        classesData,
        statusesData,
        typesData
    ] = await Promise.all([

        apiGet("/towers", user),

        apiGet(
            "/membership-classes",
            user
        ),

        apiGet(
            "/membership-statuses",
            user
        ),

        apiGet(
            "/full-member-types",
            user
        )
    ]);

    populateSelect(
        "tower_id",
        towersData.towers || [],
        tower =>
            `${tower.tower_name} (${tower.district_code})`
    );

    populateSelect(
        "membership_class_id",
        classesData.membership_classes || [],
        item =>
            `${item.code} - ${item.name}`
    );

    populateSelect(
        "membership_status_id",
        statusesData.membership_statuses || [],
        item =>
            `${item.code} - ${item.name}`
    );

    populateSelect(
        "full_member_type_id",
        typesData.full_member_types || [],
        item =>
            `${item.code} - ${item.name}`
    );

    document.querySelector("#tower_id").value =
        member.tower?.id ?? "";

    document.querySelector("#membership_class_id").value =
        member.membership_class?.id ?? "";

    document.querySelector("#membership_status_id").value =
        member.membership_status?.id ?? "";

    document.querySelector("#full_member_type_id").value =
        member.full_member_type?.id ?? "";

    updateMemberTypeState();
}

async function patchMember(user, memberId) {

    const form =
        document.querySelector(
            "#patch-member-form"
        );

    const button =
        document.querySelector(
            "#patch-member-button"
        );

    const formData =
        new FormData(form);

    const body = {
//        membership_number:
//            formData
//                .get("membership_number")
//                .trim(),

        first_name:
            formData
                .get("first_name")
                .trim(),

        surname:
            formData
                .get("surname")
                .trim(),

        tower_id:
            Number(
                formData.get("tower_id")
            ),

        date_of_birth:
            formData.get("date_of_birth") ||
            null,

        membership_class_id:
            formData.get(
                "membership_class_id"
            )
                ? Number(
                    formData.get(
                        "membership_class_id"
                    )
                )
                : null,

        membership_status_id:
            formData.get(
                "membership_status_id"
            )
                ? Number(
                    formData.get(
                        "membership_status_id"
                    )
                )
                : null,

        full_member_type_id:
            formData.get(
                "full_member_type_id"
            )
                ? Number(
                    formData.get(
                        "full_member_type_id"
                    )
                )
                : null
    };

    button.disabled = true;
    button.textContent = "Saving...";

    try {

        const response =
            await fetch(
                `${API_BASE}/members/${memberId}`,
                {
                    method: "PATCH",

                    headers: {
                        "Content-Type":
                            "application/json",

                        Authorization:
                            `Bearer ${user.access_token}`
                    },

                    body:
                        JSON.stringify(body)
                }
            );

        const data =
            await response.json();

        if (!response.ok) {

            if (response.status === 409) {
                throw new Error(
                    "That membership number already exists."
                );
            }

            if (response.status === 403) {
                throw new Error(
                    "You do not have permission to patch members."
                );
            }

            if (response.status === 404) {
                throw new Error(
                    "Member not found."
                );
            }

            if (response.status === 400) {
                throw new Error(
                    data.error ||
                    "The member details were not valid."
                );
            }

            throw new Error(
                data.error ||
                `API returned ${response.status}`
            );
        }

        if (
            !data.member ||
            !data.member.id
        ) {
            throw new Error(
                "The member was updated but no member ID was returned."
            );
        }

        window.location.href =
            `/member/?id=${data.member.id}`;

    } catch (error) {

        console.error(error);

        showError(error.message);

        button.disabled = false;
        button.textContent =
            "Save changes";
    }
}

document.addEventListener(
    "DOMContentLoaded",
    async () => {

        hideError();

        try {

            const user =
                await requireLogin();

            if (!user) {
                return;
            }

            window.currentUser = user;

            if (!userCanPatch(user)) {

                document.querySelector(
                    "#patch-member-page"
                ).innerHTML =
                    "<p>You do not have permission to edit members.</p>";

                return;
            }

            const params =
                new URLSearchParams(
                    window.location.search
                );

            const memberId =
                params.get("id");


            if (!memberId) {

                showError(
                    "No member ID was supplied."
                );

                return;
            }

            const memberData =
                await apiGet(
                    `/members/${memberId}`,
                    user
                );

            const member =
                memberData.member;

            if (!member) {
                throw new Error(
                    "Member not found."
                );
            }

            document.querySelector(
                "#membership_number"
            ).value =
                member.membership_number || "";

            document.querySelector(
                "#first_name"
            ).value =
                member.first_name || "";

            document.querySelector(
                "#surname"
            ).value =
                member.surname || "";

            document.querySelector(
                "#date_of_birth"
            ).value =
                member.date_of_birth || "";

            await loadFormData(
                user,
                member
            );

            document.querySelector(
                "#patch-member-loading"
            ).hidden = true;

            document.querySelector(
                "#patch-member-form"
            ).hidden = false;

            document.querySelector(
                "#membership_class_id"
            ).addEventListener(
                "change",
                updateMemberTypeState
            );

            document.querySelector(
                "#patch-member-form"
            ).addEventListener(
                "submit",
                async event => {

                    event.preventDefault();

                    hideError();

                    await patchMember(
                        user,
                        memberId
                    );
                }
            );

        } catch (error) {

            console.error(error);

            document.querySelector(
                "#patch-member-loading"
            ).hidden = true;

            showError(
                "Unable to initialise the patch member page."
            );
        }
    }
);
