# Prepare a public repository

The owner requested a **private** research repository with `.agents/` tracked so other agents can continue on another computer. Do not add `.agents/` to the ignore rules during this private handoff.

Publication is a later, separate decision after the project works. It is not authorized by the repository-creation request.

## Preserve the privacy boundary

Adding `.agents/` to `.gitignore` affects untracked files. Removing tracked files from the index stops future tracking, but **neither operation removes copies from earlier commits**. Making this repository public without addressing its history could expose internal notes and user-specific setup details.

The preferred option is a clean public export:

1. Keep this research repository private as the internal record.
2. Select only original implementation code, appropriate tests, and documentation intended for outside users.
3. Create a new repository with a new Git history after the owner approves publication.
4. Add `.agents/` to that repository's ignore rules and exclude personalized root agent instructions.
5. Review the new repository's complete tree, history, branches, and tags before changing visibility or pushing publicly.

If the owner instead wants this same repository made public, prepare a separate history-cleanup plan and obtain authorization for the history rewrite. Keep a private backup and verify every retained branch and tag. Do not treat a deletion commit as cleanup of earlier commits.

## Review the release contents

Before publication, check the following:

- Internal handoff notes, agent coordination, personal paths, hardware serials, account details, and signed URLs are absent from public history.
- DJI APKs, firmware, recovered proprietary code, full decompiled trees, captures, and analysis databases are absent unless their distribution has separately been established as appropriate.
- Any reused open-source code has its license and attribution preserved. A link to a project is not permission to copy its code.
- A license for the original project code has been chosen. None is selected during this documentation bootstrap.
- Compatibility and latency claims match reproduced tests, with exact models and firmware listed.
- Public setup instructions work from a clean checkout and do not depend on this private `.agents/` folder.
- Repository visibility remains private until the owner explicitly authorizes publication.

This file is an instruction for a later release review. It does not authorize purchases, history rewrites, deletion of the private record, or a visibility change now.
