# 0003: Free-text columns have their own, lower threshold

Status: accepted (revisit once `evaluate` exists)

- Whole-value detectors ask "is this value an email?" and flag a column at 80% or more of
  sampled values. That cannot work for notes or comments, where perhaps 1 value in 10 leaks a
  phone number.
- Free text is a detector like the others (`FreeTextDetector`) that carries its own `threshold`
  of 5%. The scan uses a detector's own threshold when it has one, else the scan-wide one.
  Why: no special case in the scan loop, and the next detector that needs a different bar
  costs one attribute.
- The detector with the highest match rate wins a column, and ties go to the earlier detector,
  so whole-value detectors beat free text. A column of pure emails is "email", not "free text
  that contains emails". The winner then has to clear its own threshold.
- Free text reuses the validators of the other detectors (IBAN checksum, DNI check letter,
  phone shapes), so a random 9-digit number or a mistyped IBAN does not count.
- **Confidence means something different here:** the share of values that contain PII, not the
  share that match a pattern. The README says so next to the example output.
- **Tradeoff:** the 5% bar has no minimum hit count, so in a tiny sample one leaking row flags
  the column. That is accepted for now: missing a leak is worse than one extra review.
  The number was chosen by judgment, not measured.
- **Not covered:** person names in free text. Rules cannot do it, which is the case for Phase 3.
