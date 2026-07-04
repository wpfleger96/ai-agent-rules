<!-- Author's personal claude.ai custom-instructions backup (Dropbox folder map).
     Not deployed by the CLI — kept here so personal content lives with the other
     profile fragments. -->

## Dropbox

I use Dropbox to store important documents across multiple life domains. Top-level folders include:

- `/Medical/` — Clinical records, sleep studies, lab results, medication history, research papers
- `/Financial/` — Tax documents by year (1099s, W2s, stock plan supplements), medical expense tracking
- `/Work/Square/` — Block/Square employment docs (compensation, official policies)
- `/House/Eastwood Dr/` — Housing documents (homeowners insurance)
- `/Auto/` — Auto insurance (Progressive, organized by year)
- `/Receipts/` — Receipts organized by year → category (Medical, House, etc.)
- `/Homelab/` — Tech/homelab configs, network diagrams, AI/ML research papers
- `/Backups/` — Device backups, mom's backup, Enpass, old school files
- `/_Archive/` — Archived older content

### Connector Tips (personal folder references — originals before genericization)

- Always scope searches with `path` when you know the relevant folder to avoid noise from unrelated folders (especially `/Backups/` which contains thousands of files).
- Search and list_folder return `path` (ns_path, e.g. `ns:2207500880//Medical/file.pdf`) and `path_display` (fq_path, e.g. `/Medical/file.pdf`); search also returns a tool-ready `id` (file_id). fq_path and file_id both work directly in follow-on calls — prefer the returned `id` or `path_display`.
