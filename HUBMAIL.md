# HubMail fork of grommunio admin-api

Branches:
- `master` mirrors `upstream/master` (grommunio/admin-api). Never commit here; branch
  feature PRs for upstream off it.
- `hubmail` is the HubMail distribution: `master` + our carried patches. Rebase it
  onto each upstream release.

Carried patches:
- Default license (no certificate uploaded) is `HubMail` with 100000 users instead of
  `Community` / 5. Override in a config.yaml / conf.d file:

      options:
        defaultLicenseUsers: 100000
        defaultLicenseProduct: HubMail

  An uploaded signed license certificate still takes precedence.

Sync with upstream:

    git fetch upstream
    git checkout master && git merge --ff-only upstream/master && git push origin master
    git checkout hubmail && git rebase master && git push --force-with-lease origin hubmail

This is AGPL-3.0 software: the modified source we run for users stays public here.
