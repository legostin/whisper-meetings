# Google Calendar preview

The panel can select upcoming primary-calendar events directly, without an agent searching the calendar. Access is optional and read-only. Pasting a Google Meet link works in every installation and needs no Google account setup.

## Current distribution status

Direct Google login is available in locally configured preview installations. It is **not yet configured for every user of the public Git release**. The publisher project is in Google Testing, with explicitly listed test accounts. Google verification and a supported public client-distribution strategy remain outstanding; OpenAI Directory approval is a separate process.

The native flow uses Desktop OAuth, PKCE S256, a random-port `127.0.0.1` callback and the system browser. Google rejected a real token-endpoint request without `client_secret` with `client_secret is missing`. The package does not pretend that distributing only a client ID makes login work. Google's [credential-handling guidance](https://developers.google.com/identity/protocols/oauth2/resources/best-practices) says not to publish client credentials in a repository; the public ZIP excludes that configuration. No publisher OAuth relay is operated by this release.

## Configure a developer or private preview

1. In Google Cloud, create a project and enable **Google Calendar API**.
2. Configure the external consent screen, public privacy/terms links and developer contact. Request only `https://www.googleapis.com/auth/calendar.events.readonly`.
3. While in Testing, explicitly add each participating account under **Audience → Test users**. Confirm that the saved table contains the email; an uncommitted input is not enough.
4. Create an OAuth client of type **Desktop app** for the interactive panel. Download its JSON. Do not use a Web client or upload the JSON to GitHub.
5. After normal local runtime setup, import it from outside the repository:

```sh
python3 plugins/whisper-meetings/scripts/configure_google.py /absolute/path/downloaded-client.json
```

This writes owner-only configuration to the local data directory, outside the plugin cache and source checkout. It never prints credentials. If `WHISPER_MEETINGS_HOME` is set, use the same value for setup, configuration and the server.

## Use the connection

Click **Connect Google**, choose an account in the system browser and allow calendar access. Return to the panel and pick a meeting. Its title, times and Calendar/Meet links are attached when you start recording or explicitly link a saved recording. Connection or selection never starts recording by itself.

**Refresh meetings** loads up to 100 events from two hours ago through seven days ahead, ordered by start time. This release reads the primary calendar only. It does not request attendees or descriptions, change events or join Meet. Access/refresh tokens stay in macOS Keychain and never appear in tool responses or exports. Panel status polling reads only local state; it does not repeatedly call Google.

**Cancel sign-in** invalidates a pending login. **Disconnect** deletes local account tokens and cached Google event choices and attempts to revoke the Google grant. Already saved meeting associations remain. A revoked or expired grant prompts reconnection. Google Testing refresh tokens can expire after seven days; see [Google native OAuth guidance](https://developers.google.com/identity/protocols/oauth2/native-app).

## Resolve Google errors

- **403 / access_denied before consent:** use an account explicitly saved under Test users. Workspace account policy can independently deny access.
- **disallowed_useragent:** use the system browser. Embedded webviews are not supported by Google OAuth.
- **Calendar request fails after consent:** confirm Calendar API is enabled in the same project and choose Refresh meetings. The UI retains the connection after a temporary calendar failure.
- **Client setup unavailable:** complete runtime setup and import a valid Desktop JSON. Public preview users can paste a Meet link instead.

For public rollout, first provide verified publisher domains and consent branding, complete the applicable Google verification and choose a supported credential-distribution architecture. Do not publish secrets to bypass setup, claim approval before Google grants it, or send private calendar data to public issues.
