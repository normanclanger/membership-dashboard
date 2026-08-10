import { UserManager } from "https://cdn.jsdelivr.net/npm/oidc-client-ts/+esm";

const cognitoAuthConfig = {
    authority:
        "https://cognito-idp.eu-north-1.amazonaws.com/eu-north-1_KEeAlTjpo",

    client_id:
        "6vpsd8o224ft4srqclmfs8nsv9",

    redirect_uri:
        window.location.origin + "/callback",

    response_type:
        "code",

    scope:
        "email openid phone"
};

export const userManager = new UserManager(cognitoAuthConfig);


export async function signOutRedirect() {
    const logoutUri = window.location.origin + "/";

    const cognitoDomain =
        "https://eu-north-1keealtjpo.auth.eu-north-1.amazoncognito.com";

    const clientId =
        "6vpsd8o224ft4srqclmfs8nsv9";

    await userManager.removeUser();

    window.location.href =
        `${cognitoDomain}/logout?client_id=${clientId}&logout_uri=${encodeURIComponent(logoutUri)}`;
}


export async function requireLogin() {
    const user = await userManager.getUser();

    if (!user || user.expired) {
        await userManager.signinRedirect();
        return null;
    }

    return user;
}


document.addEventListener("DOMContentLoaded", () => {

    const signInButton = document.getElementById("login-button");

    if (signInButton) {
        signInButton.addEventListener("click", async () => {
            await userManager.signinRedirect();
        });
    }

});

