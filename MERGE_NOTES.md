# CivicFix Merge Notes — Multilingual + Field Officer + Resolution Evidence

This release merges the teammate's field-officer/review phase into the existing multilingual CivicFix phase without replacing the newer citizen portal, multilingual classifier, or admin console.

## Preserved from the existing phase

- Multilingual citizen UI and voice intake.
- Browser speech recognition with Indian-language locales.
- Language detection and native-script civic classification.
- English TF-IDF + Multinomial Naive Bayes classifier.
- Multilingual character n-gram TF-IDF + Multinomial Naive Bayes classifier.
- Civic lexicon/canonicalization layer.
- Location extraction and device GPS.
- Image relevance validation.
- Duplicate detection with category + 250 m + text similarity.
- Explainable 100-point priority scoring.
- SLA tracking and admin map/operations console.
- Citizen OTP authentication.

## Merged from teammate phase

- Third authenticated role: `field_officer` / Service Officer.
- Five canonical service departments and category-to-department routing.
- Field officer queue, start-work flow and geotagged completion evidence.
- 1–5 star citizen rating and optional written review.
- Admin-visible citizen feedback.

## Added on top of both phases

- Optional citizen after-work photo.
- Citizen GPS capture for the after-work photo.
- Worker/citizen evidence pairing.
- Lightweight OpenCV evidence consistency scoring:
  - ORB feature matching
  - HSV histogram similarity
  - grayscale structure similarity
  - Haversine distance
- Evidence states: pending worker evidence, verified, needs review, admin confirmed, rejected.
- Auto-transition to `RESOLVED` only when the evidence pair meets the configured visual/location consistency thresholds.
- Admin confirmation/rejection controls with an auditable status history.
- Rejection of an auto-verified resolution returns the issue to `IN_PROGRESS` for review.
- Initial complaint-photo GPS metadata (`latitude`, `longitude`, `capture_mode`).
- Legacy database compatibility migration for new attachment metadata and auth columns.
- Canonical department assignment immediately at issue creation, not only at startup.

## Evidence principle

The image comparison is an evidence-consistency signal, not forensic proof. It combines visual and geographic consistency so the admin can inspect the two photos and the supporting metrics before final confirmation.
