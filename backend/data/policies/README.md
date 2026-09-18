# RAG policy corpus

Source documents for the retrieval corpus. The PDFs themselves are gitignored
(`backend/data/` in `.gitignore`) — they are third-party copyrighted publications, used here
for academic evaluation. Re-download them to reproduce the corpus:

| File | Source | Chunks |
|------|--------|--------|
| `hlib-code-of-conduct.pdf` | https://www.hlib.com.my/Files/Code_of_Conduct_and_Ethics.pdf | 39 |
| `genting-code-of-conduct.pdf` | https://www.gentingmalaysia.com/wp-content/uploads/2019/10/Genting-Code-of-Conduct-Ethics-simplified-with-new-Reg-No_22Oct2019.pdf | 7 |

Ingest with, from `backend/`:

```bash
python scripts/ingest.py data/policies/hlib-code-of-conduct.pdf "HLIB Code of Conduct and Ethics"
python scripts/ingest.py data/policies/genting-code-of-conduct.pdf "Genting Malaysia Code of Conduct and Ethics"
```

Chosen over the GitLab handbook because the project's context is Malaysian corporate email, and
these are real listed-company documents rather than synthetic policy. Cite them in the report;
do not present the text as original.

Both must be attributed. Adding more sources: pick documents that cover the topics
`scripts/eval_set.json` asks about, and extend that eval set at the same time.
