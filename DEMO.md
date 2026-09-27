# CivicFix 4–5 minute integrated demo

## 1. Citizen intake

Open `/login` → choose **Citizen** → request OTP (demo mode).

Go to `/report` and select Marathi. Use voice or type:

> आमच्या रस्त्यावर खूप मोठा खड्डा आहे.

Capture/share the issue location and add the complaint photo.

Show the receipt:

- detected language
- category + confidence
- location
- duplicate intelligence
- explainable 100-point priority
- SLA window

## 2. Admin triage

Open `/admin` and open the resulting civic issue. Show:

- AI category
- complaint count / duplicate consolidation
- priority factors
- SLA state
- canonical department
- assignment controls

Assign it to the matching field officer department.

## 3. Field officer

Open `/login` → choose **Service Officer**. Use the corresponding demo account from `FIELD_OFFICER_SETUP.md`.

Open the assigned complaint, click **Start work**, then upload a completion photo with browser location enabled. The upload is saved as field evidence and moves the work into progress.

## 4. Citizen completion confirmation

Return to the citizen account → `/complaints`. On the resolved/in-progress case, use **Upload after-work photo**. CivicFix captures current GPS coordinates and compares the citizen photo with the field-worker completion photo.

Two outcomes can be demonstrated:

- sufficiently consistent image + location → `verified` → issue automatically becomes `RESOLVED`
- weaker pair → `needs_review` → admin confirmation required

## 5. Admin evidence confirmation

Open the same case in `/admin`. Show the **Resolution evidence** card:

- worker completion photo
- citizen after-work photo
- visual similarity
- location distance
- combined consistency score
- evidence status

Click **Confirm completion** to record the final admin decision.

For an unsuccessful evidence case, **Reject & review** returns an auto-resolved issue to `IN_PROGRESS`.

## 6. Citizen feedback

After resolution, the citizen can optionally submit a 1–5 star rating and written review. The admin case drawer shows the feedback summary alongside resolution evidence.

## Story to tell the judges

**Citizen speaks naturally → AI understands the civic issue → municipality deduplicates and prioritizes it → the right field officer receives it → work is completed with geotagged evidence → citizen can independently upload an after-work photo → AI checks whether the two pieces of evidence are geographically and visually consistent → admin confirms the outcome → citizen rates the service.**
