# Google Verification: Step by Step

Goal: anyone with a Google account can sign in, without being added as a test user and without the "unverified app" warning.

There are two checks:
- **Brand verification** (minutes to 3 business days): confirms your name, homepage, privacy policy.
- **Sensitive scope verification** for Gmail "send" (usually a few weeks): confirms why you need to send email.

Your site layout:
- `https://www.mass-outreach.com`: homepage (new, static site)
- `https://www.mass-outreach.com/privacy` and `/terms`
- `https://mass-outreach.com`: the app (unchanged)

---

## Part 1: Put the website online (Cloudflare Pages, free, ~15 min)

**1a. Free up `www`**
1. **Render** > outreach-desk > **Settings** > **Custom Domains**: delete `www.mass-outreach.com` (keep `mass-outreach.com`).
2. **Cloudflare** > mass-outreach.com > **DNS** > **Records**: delete the `www` CNAME record (keep the `A` record for `mass-outreach.com`).

**1b. Upload the site**
1. Cloudflare dashboard > **Workers & Pages** > **Create** > **Pages** > **Upload assets** (Direct Upload).
2. Project name: `mass-outreach-site` > **Create project**.
3. Drag in the **`site` folder** from `outreach-desk\UPLOAD_THESE\site` (4 files: index.html, privacy.html, terms.html, style.css) > **Deploy site**.
4. Open the `...pages.dev` link it gives you and check the pages load.

**1c. Connect `www`**
1. In the Pages project > **Custom domains** > **Set up a custom domain** > `www.mass-outreach.com` > **Continue** > **Activate domain**. Cloudflare adds the DNS record for you.
2. Wait a few minutes, then open `https://www.mass-outreach.com`, `/privacy`, and `/terms`.

## Part 2: Verify you own the domain (~10 min)

1. Go to **search.google.com/search-console**, signed in with the **same Google account** that owns your Google Cloud project.
2. **Add property** > **Domain** > `mass-outreach.com` > **Continue**.
3. Copy the **TXT record** Google shows (starts with `google-site-verification=`).
4. Cloudflare > DNS > **Add record**: Type **TXT**, Name `@`, Content = the value you copied > **Save**.
5. Back in Search Console, click **Verify**. (If it fails, wait 10 minutes and try again.)

## Part 3: Fill in Branding in Google Cloud (~10 min)

console.cloud.google.com > your project > **Google Auth Platform** > **Branding**:

| Field | Value |
|---|---|
| App name | `Mass Outreach` |
| User support email | your Gmail |
| App logo | **leave empty** for now (a logo adds extra review) |
| Application home page | `https://www.mass-outreach.com` |
| Application privacy policy link | `https://www.mass-outreach.com/privacy` |
| Application terms of service link | `https://www.mass-outreach.com/terms` |
| Authorized domains | `mass-outreach.com` (remove any old `streamlit.app` or `onrender.com` entries) |
| Developer contact email | your Gmail |

Click **Save**.

Also check **Clients** > your OAuth client > **Authorized redirect URIs** contains `https://mass-outreach.com` and remove the old streamlit.app / onrender.com ones.

## Part 4: Publish the app

**Audience** > **Publishing status** > **Publish app** > **Confirm**.
(Until scope verification finishes, users see an "unverified app" warning and there's a cap of 100 users. That's expected.)

## Part 5: Verify branding

**Verification Center** (in Google Auth Platform) > **Verify branding**. Usually done in minutes; sometimes 2 to 3 business days.

## Part 6: Verify the Gmail "send" permission

**Data Access** > make sure the only scopes are `openid`, `.../auth/userinfo.email`, and `.../auth/gmail.send`. Then submit for verification. Google asks for:

**Scope justification** (paste):
> Mass Outreach lets job seekers send personalized outreach emails about specific job openings from their own Gmail account. The user writes one message, adds the recipients they chose, previews every email, and then clicks Send. We use gmail.send only to send those user-approved messages. We do not read, search, or store the user's email, and gmail.send is the narrowest scope that lets a user send email from their own address.

**Demo video** (unlisted YouTube link, 2 to 3 minutes). Record your screen showing:
1. The browser address bar with `https://mass-outreach.com`.
2. Clicking **Sign in with Google** and the full consent screen, including the app name and the "Send email on your behalf" permission. Use **English** as the language.
3. Filling in a job, names, and a message, then the preview.
4. Clicking **Send** (test mode is fine) and the email arriving in Gmail's **Sent** folder.
5. Briefly showing the Privacy Policy link.

Free recorder: Windows **Snipping Tool** (record mode) or **Xbox Game Bar** (Win + G). Upload to YouTube as **Unlisted**.

Google may email follow-up questions to your developer contact email. Reply promptly.

---

## Before submitting, quick checklist
- [ ] www.mass-outreach.com, /privacy, /terms all load publicly
- [ ] Domain verified in Search Console with the same Google account
- [ ] Branding fields match exactly (URLs, name "Mass Outreach")
- [ ] App published
- [ ] Latest app.py uploaded to GitHub (adds Privacy/Terms links in the app)
