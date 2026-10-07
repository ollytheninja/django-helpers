(() => {
    "use strict";

    const decode = value => {
        const padded = value.replace(/-/g, "+").replace(/_/g, "/");
        const binary = atob(padded + "=".repeat((4 - padded.length % 4) % 4));
        return Uint8Array.from(binary, character => character.charCodeAt(0));
    };
    const encode = value => btoa(String.fromCharCode(...new Uint8Array(value)))
        .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    const csrf = () => document.querySelector('[name="csrfmiddlewaretoken"]')?.value || "";

    async function requestJson(url, method = "GET", body = undefined) {
        const response = await fetch(url, {
            method,
            credentials: "same-origin",
            headers: {"Content-Type": "application/json", "X-CSRFToken": csrf()},
            body: body === undefined ? undefined : JSON.stringify(body),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Passkey request failed.");
        return result;
    }

    function publicKeyOptions(options) {
        options.challenge = decode(options.challenge);
        if (options.user) options.user.id = decode(options.user.id);
        for (const key of ["allowCredentials", "excludeCredentials"]) {
            for (const item of options[key] || []) item.id = decode(item.id);
        }
        return options;
    }

    function credentialPayload(credential) {
        const response = credential.response;
        const payload = {
            id: credential.id,
            rawId: encode(credential.rawId),
            type: credential.type,
            authenticatorAttachment: credential.authenticatorAttachment,
            clientExtensionResults: credential.getClientExtensionResults(),
            response: {clientDataJSON: encode(response.clientDataJSON)},
        };
        for (const key of ["attestationObject", "authenticatorData", "signature", "userHandle"]) {
            if (response[key]) payload.response[key] = encode(response[key]);
        }
        if (response.getTransports) payload.response.transports = response.getTransports();
        return payload;
    }

    function showError(error) {
        const target = document.getElementById("passkey-error");
        if (target) {
            target.textContent = error.message || "The passkey request failed.";
            target.hidden = false;
        }
    }

    const signIn = document.getElementById("passkey-login-btn");
    signIn?.addEventListener("click", async () => {
        signIn.disabled = true;
        try {
            if (!window.PublicKeyCredential) throw new Error("Passkeys are unavailable in this browser.");
            const options = publicKeyOptions(await requestJson(signIn.dataset.optionsUrl));
            const credential = await navigator.credentials.get({publicKey: options});
            const result = await requestJson(signIn.dataset.verifyUrl, "POST", credentialPayload(credential));
            window.location.assign(result.redirect);
        } catch (error) {
            showError(error);
            signIn.disabled = false;
        }
    });

    const register = document.getElementById("passkey-register-btn");
    register?.addEventListener("click", async () => {
        register.disabled = true;
        try {
            if (!window.PublicKeyCredential) throw new Error("Passkeys are unavailable in this browser.");
            const name = document.getElementById("id_passkey_name").value.trim();
            if (!name) throw new Error("Enter a name for this passkey.");
            const options = publicKeyOptions(await requestJson(register.dataset.optionsUrl, "POST"));
            const credential = await navigator.credentials.create({publicKey: options});
            const payload = credentialPayload(credential);
            payload.name = name;
            await requestJson(register.dataset.verifyUrl, "POST", payload);
            window.location.reload();
        } catch (error) {
            showError(error);
            register.disabled = false;
        }
    });
})();
