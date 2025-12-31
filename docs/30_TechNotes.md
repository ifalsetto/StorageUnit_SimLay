# Tech Notes

## Possible Architecture Directions

### Option A — Local-first tool
- Runs on desktop
- Data stored locally first
- Optional sync later
- Privacy-friendly

### Option B — Web app
- Cloud backend
- Accessible anywhere
- Easy collaboration
- Future mobile support

Both paths remain open.

---

## AI Components (Future)

- Object detection
- Category classification
- Comparable-value lookup
- Summary insights
- Duplicate detection

---

## Data Model (Early Draft)

**Unit**
- id
- name
- location
- date_acquired

**Photo**
- id
- unit_id
- filepath/url
- extracted_tags

**Item**
- id
- unit_id
- title
- category
- confidence
- est_value_low
- est_value_high
- status (unreviewed / kept / sold / donated / trashed)

**User**
- id
- name
- email

---

## Integration Ideas

- Google Drive
- Local folder sync
- Zip import
- Export to:
  - CSV
  - Excel
  - PDF reports

---

## Security & Privacy Thoughts

- Photos may show personal data
- Should support:
  - Local-only mode
  - Encrypted storage (future)
