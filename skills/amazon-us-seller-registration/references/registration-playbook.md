# Registration Playbook

Last fact check: 2026-08-01. Recheck live official pages for fees, policies, accepted documents, and screen labels.

## 1. Default scenario and exceptions

Use this playbook for a Mainland China limited company registering Amazon US with:

- a real Chinese business license;
- the legal representative as primary identity verifier when practical;
- ZiNiao as the controlled browser/network environment;
- WorldFirst as a third-party USD receiving-account provider;
- one primary operator during registration;
- up to six concurrent team users after approval;
- an Individual selling plan during preparation, with later upgrade if needed;
- no brand or UPC at registration when that is the truth.

Pause and obtain specialist advice if the entity is a sole proprietorship, partnership, trust, financial institution, US entity, has filed Form 8832, has US effectively connected income, claims treaty benefits, or has an unresolved related/suspended seller account.

Handle historical accounts before creating anything new:

- active account for the same entity: continue or recover that account;
- incomplete registration: resume it;
- suspended or limited account: resolve its status before considering another account;
- additional account: require a real business need, truthful relationship records, good standing of existing accounts, and explicit user approval.

## 2. Intake facts

Collect only what the current phase needs. Maintain a source-of-truth table containing:

| Field | Authoritative source |
| --- | --- |
| Legal company name and registration number | Business license |
| Formation date and registered address | Business license |
| Legal representative name | License and government ID |
| Representative romanized name | One internally approved transliteration |
| Birth data, nationality, ID validity | Government ID |
| Residential address | Current address proof |
| Beneficial owners and percentages | Corporate records |
| Registration email and phone | Company-controlled records |
| Cardholder and billing address | Issuer record |
| WorldFirst account holder and address | WorldFirst account proof |
| Store display name and category | Approved business plan |

Never embed the actual values in this skill.

## 3. Preparation checklist

### Entity and people

- Valid color business-license file with all corners visible.
- Valid legal-representative ID or passport, front and back where applicable.
- Recent address proof if requested; Amazon's public registration guide currently describes a document issued within 180 days.
- Beneficial-owner and controller information.
- Real authorization evidence if a non-legal-representative acts for the company.

### Accounts and money

- Dedicated company-controlled email.
- Long-term phone capable of voice/SMS verification.
- Password manager, authenticator, and recovery custody.
- Current internationally enabled card with issuer-exact billing address.
- Approved WorldFirst enterprise account with a US USD receiving account.
- WorldFirst proof of account/statement generated for the exact Amazon company name and address.

### Store choices

- Three unique, locally natural display-name candidates.
- Truthful current product category.
- Brand/trademark status.
- GTIN/UPC status.
- Individual versus Professional plan decision.
- Real return-address plan.

## 4. ZiNiao operating model

Create one ZiNiao account environment per store. Bind the intended device/network before opening Amazon. Use a clear internal name such as `AMZ-US-COMPANY-01`.

Use these terms consistently:

- **ZiNiao account**: the internal store profile;
- **device/network**: the bound network resource and its IP/service characteristics;
- **environment**: the isolated browser state saved for that account;
- **member/concurrency**: people permitted to open or operate that environment.

For a traveling team:

- open the same bound environment from any location;
- do not layer random VPN/proxy nodes inside the store environment;
- avoid alternating with local Chrome or mobile browsers during registration;
- use a single registration operator;
- authorize only required ZiNiao members;
- set a concurrency limit appropriate to the plan. ZiNiao's device help currently recommends no more than six simultaneous users per device.

Six is a provider recommendation, not a guarantee that simultaneous editing is safe. Keep registration to one operator. After approval, prevent concurrent changes to entity, banking, tax, permissions, and other sensitive settings.

After approval, create separate Amazon users with least privilege. ZiNiao authorization controls access to the environment; Amazon User Permissions controls actions inside Seller Central. Configure both.

For another Amazon store or Temu store, create a separate account environment. Do not promise that sharing an IP or device is safe. Check both platform policies and ZiNiao's current risk notice. Never present environment isolation as a way to hide real account relationships.

## 5. Amazon form map

### Account creation

- Use a company-controlled email and real long-term phone.
- A routine contact phone need not always be legally registered to the legal representative, but comply when Amazon explicitly requires identity ownership.
- The user enters password, OTP, and recovery secrets.

### Company information

- Business location: `China` for a Mainland China company.
- Business type: the closest truthful corporate type, not individual.
- Legal name: exact business-license name.
- Registration number: for a Chinese company, generally the unified social credit code, not an EIN.
- Registered address: the license address, complete and consistently romanized if English is required.

When a field accepts Chinese, use the exact Chinese source value. When it requires Latin characters, use one truthful, documented romanization that preserves the legal name, company suffix, address order, and meaning. Do not claim that two different scripts can be character-for-character identical; record the approved mapping and reuse it consistently.

### Primary contact and owners

- Prefer the legal representative when practical.
- Enter all identity facts from the government document.
- Declare beneficial owners and legal-representative status truthfully.
- The Amazon public guide currently describes more than 25% ownership/voting rights or other control. Follow the live page if it differs, and stop for exactly 25%, indirect ownership, or ambiguous control rather than inferring a legal conclusion.

### Selling plan

- Individual: useful during setup or low-volume selling; Amazon's current public pricing page lists a per-item plan fee.
- Professional: monthly plan with bulk tools, ads, APIs, and other advanced features.
- Amazon currently allows plan changes after registration.
- Recheck the current fee page before quoting an amount.
- FBA availability and Professional-plan need are separate questions. Do not say Professional is universally required for FBA.
- Some registration links may default to Professional. Confirm the displayed plan before final account creation or any recurring charge.
- Before inviting multiple users, verify whether the current plan exposes the required User Permissions. Treat an upgrade as a separate paid decision.

### Store survey

- Display name is customer-facing and need not equal the legal company name.
- Use a unique name; do not impersonate a brand or claim “Official” without authorization.
- Category is a current truthful estimate, not a permanent catalog lock.
- If there is no brand, say no.
- If there is no GTIN/UPC, say no; later use legitimate GS1 identifiers or an eligible Amazon GTIN-exemption route.

## 6. Charge method versus deposit method

### Charge method

Purpose: pay Amazon fees and negative balances.

Check:

- supported card network on the live page;
- expiry, CVV, cardholder, issuer-exact address and postal code;
- international online and USD transactions;
- MOTO/recurring authorization if the issuer uses that control;
- available limit and fraud block.

Amazon's current public registration guide says the charge card need not be in the contact's or company's name, but a third-party card can create issuer, ownership, or continuity risk. Prefer a company-controlled or principal-controlled card and verify the live page.

Possible charges include selling-plan fees, referral fees, FBA, storage, advertising, refunds/adjustments, service fees, and small verification authorizations.

If `Unable to charge` appears, reauthenticate the sensitive page, recheck issuer data, contact the issuer, and replace the card only if necessary. A card assigned to multiple automatically created marketplaces does not by itself prove a charge was made.

### Deposit method

Purpose: receive Amazon sales proceeds.

For WorldFirst US USD details:

1. Open `Settings → Account Info → Deposit Methods` or the live equivalent.
2. Add a method for `Amazon.com`.
3. Select bank location `United States`.
4. Select business bank account `Yes` for the company's account.
5. Enter the provider bank/routing/account information exactly.
6. Use the exact registered company as account holder.
7. Assign only Amazon.com at startup unless the user expressly chooses other marketplaces.

The Amazon regional account may show US, Canada, Mexico, and/or Brazil depending on current account architecture. Automatic marketplace presence is not the same as active operation.

## 7. WorldFirst routing

### Enterprise registration

- Country/region: Mainland China.
- Account: enterprise.
- Company, representative, and address: exact real documents.
- Business type: closest truthful broad category; update it if the business materially changes.
- Export-tax-refund service is optional and not required for Amazon registration or a USD receiving account.

If enterprise KYC is pending or the US USD account is not open, pause the Amazon deposit step. Do not substitute a personal or unrelated account merely to continue.

### Amazon US authorization

Use the established Amazon ZiNiao environment when WorldFirst redirects to Amazon:

`Store Management → Add/authorize Amazon store → holder company → authorize now → United States → Amazon authorization`.

Authorization allows WorldFirst to link or verify the store; it may or may not finish Amazon's deposit-method configuration. After authorization, inspect Seller Central. If the correct USD account is already assigned to Amazon.com, do not duplicate it. Otherwise add it through Deposit Methods.

### Screen discrimination

| Screen | Meaning | Action |
| --- | --- | --- |
| WorldFirst asks for China beneficiary, SWIFT/BIC, and local bank account | Withdrawal destination from WorldFirst | Complete only when setting up local withdrawal |
| Amazon shows bank location China and ACCS/local PSP | Local-currency settlement route | Do not use when the intended account is WorldFirst US USD |
| Amazon bank location United States with routing/account fields | US USD deposit route | Use WorldFirst US account details |

The seller only needs to ask its Chinese bank about receiving USD when withdrawing USD from WorldFirst to that bank. It is not required for Amazon to pay WorldFirst.

### Proof of account

Use the current WorldFirst route, commonly:

`Store Management → My Stores → Store Details → View Account Details → Request/Download Proof of Account`.

When available:

- choose another account-holder name/address if the default differs from Seller Central;
- copy the Amazon company name and address exactly, including case, punctuation and spaces;
- include a statement when Amazon requests a bank statement;
- select a recent period;
- download a fresh unedited PDF.

Use custom display fields only when they still describe the same real company and the same real address. If either Amazon or WorldFirst contains an incorrect source record, correct that source through the official process first. Never rewrite proof text merely to make a review pass.

The evidence should contain the holder name/address, account identifier, issue date or statement period, and official bank/provider information. A charge-card statement is not proof of the deposit account.

If rejected, diagnose exact mismatch before resubmitting. Ask WorldFirst support for an Amazon-specific account proof/statement rather than editing the file.

## 8. Identity, address, and bank checks

### Identity

- Upload original color files, not screenshots or modified copies.
- Keep all corners visible and text readable.
- Have the named legal representative or specified contact perform face/video verification.
- Prepare original ID and business license if requested.

### Address

- Company registered address and personal residential address can differ because they serve different roles.
- Each address must match its own authoritative proof.
- Use a real deliverable address if Amazon sends a postcard.

### Bank evidence rejection

Check in this order:

1. right Amazon marketplace and deposit account;
2. US bank location for the WorldFirst USD account;
3. exact holder name and address;
4. account number/routing data;
5. recent issue date/period;
6. official provider/bank identity;
7. unedited PDF linked to the current account.

If an email template mentions another marketplace such as Japan, verify the live account, marketplace, and requested field. Do not switch marketplace based only on boilerplate text. Open a support case if the instructions conflict.

## 9. W-8BEN-E decision boundary

For an ordinary Mainland China limited company with no special US election or US business facts, the common Amazon interview path is:

- beneficial owner is an entity/business;
- non-US person/entity;
- country of organization China;
- W-8BEN-E;
- chapter 3 entity classification commonly `Corporation`, not `Private foundation`;
- permanent/registered address from company records;
- signature by the legal representative or another person with legal capacity to sign.

This is not universal. IRS instructions require classification under US tax principles. Stop for professional review if there is Form 8832, US entity/ECI, partnership/trust/disregarded-entity facts, treaty claim, GIIN/FFI/FATCA complexity, or uncertainty about signature authority.

Do not invent a Chapter 4/FATCA status. If the interview asks about Active NFFE, Passive NFFE, FFI, GIIN, US substantial owners, or financial income/assets, collect the underlying facts and verify them against current IRS guidance or a qualified adviser.

Before final submission:

1. summarize the selected entity type, country, address, certifications, signer and consequence;
2. ask for explicit confirmation from the authorized person;
3. let the user perform or directly approve the signature/submit action;
4. save the generated tax form and status.

## 10. Team permissions and evidence handling

Use separate Amazon users when the current plan supports them:

| Role | Typical access | Avoid by default |
| --- | --- | --- |
| Account owner | Account administration and recovery | Daily shared use |
| Finance | Statements, settlements, limited payment tasks | User administration unless approved |
| Operations | Listings, inventory, orders | Tax and bank changes |
| Customer service | Messages, returns, order support | Financial and identity data |
| Advertising | Ads and reports | Banking, tax, users |
| External provider | Authorized Partner or narrowly scoped access | Master email, MFA and recovery |

Give every user individual MFA. Review access after personnel changes and periodically. Keep official KYC files in encrypted, role-restricted storage; do not place full identifiers in filenames, chat, or ZiNiao notes. Retain and destroy superseded copies according to the company's legal and records policy.

After a rejection, preserve the exact notice, submitted filename/version and timestamp. Correct one identified issue at a time. Do not repeatedly upload the same rejected evidence or conflicting versions. Escalate through official Amazon/WorldFirst support when the notice remains unclear or a corrected official document is rejected again.

## 11. Readiness gates

### Registration complete

- Seller Central US opens.
- Identity/address checks passed or were not required.
- Deposit account verified and assigned to Amazon.com.
- Charge method valid.
- Tax interview accepted.
- No critical, limited-access, suspended, or pending registration task.
- Company controls email, MFA, recovery and ZiNiao environment.

### Listing ready

In addition to registration, confirm the intended selling plan, category approval, brand/Generic path, GTIN or exemption, listing data, real return settings, and product compliance.

### FBA shipment ready

Registration completion alone is insufficient. Confirm:

- selling-plan choice for the intended workflow;
- FBA enrollment/activation;
- real return settings;
- listing and category approval;
- brand/Generic path and GTIN or exemption;
- product safety, certifications, labeling, IP, origin and dangerous-goods status;
- dimensions, weights, packaging, FNSKU/carton labels;
- shipping plan, freight, customs and importer arrangements.

## 12. Official sources

- Amazon registration: https://sell.amazon.com/zh/sell/registration-guide
- Amazon China-to-US overview: https://sell.amazon.com/zh/global-selling/china
- Amazon pricing: https://sell.amazon.com/zh/pricing
- WorldFirst Amazon North America USD binding: https://www.worldfirst.com.cn/content/helpcenter/detail?pageId=33a5b798-48aa-4a52-93dd-8093079d4dc1
- WorldFirst proof of account: https://www.worldfirst.com.cn/content/articles/b2c_portal/accout-letter-guidelines
- ZiNiao add account: https://www.ziniao.com/help/docs/account/17363301553332
- ZiNiao authorize members: https://www.ziniao.com/help/docs/account/17363302743798
- ZiNiao device use: https://www.ziniao.com/help-v5/docs/network/17363306139516
- IRS W-8BEN-E instructions: https://www.irs.gov/instructions/iw8bene
