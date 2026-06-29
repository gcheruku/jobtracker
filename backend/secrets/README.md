# Gmail credentials (not committed)

The real `credentials.json` and `token.json` are gitignored. Only the
`*.example.json` templates are committed. To enable Gmail ingestion:

1. In **Google Cloud Console**, create a project and **enable the Gmail API**.
2. Create an **OAuth client ID** of type **Desktop app**, download it, and save it
   here as `backend/secrets/credentials.json` (see `credentials.example.json`).
3. Generate `token.json` by running a one-time OAuth consent flow with the
   read-only scope `https://www.googleapis.com/auth/gmail.readonly`, e.g.:

   ```python
   from google_auth_oauthlib.flow import InstalledAppFlow
   flow = InstalledAppFlow.from_client_secrets_file(
       "backend/secrets/credentials.json",
       ["https://www.googleapis.com/auth/gmail.readonly"],
   )
   creds = flow.run_local_server(port=0)
   open("backend/secrets/token.json", "w").write(creds.to_json())
   ```

   The app refreshes this token automatically afterward (see `token.example.json`
   for the shape).
4. In Gmail, create a label (default **`Job alerts`**, override with `GMAIL_LABEL`)
   and route your Dice/LinkedIn/Glassdoor/Indeed alert emails to it.

Paths are overridable via `GMAIL_CREDENTIALS_PATH` / `GMAIL_TOKEN_PATH`.
