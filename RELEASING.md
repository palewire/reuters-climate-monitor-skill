# Releasing

This project follows [Semantic Versioning](https://semver.org/) and [Keep a
Changelog](https://keepachangelog.com/en/1.1.0/). Package versions come from
Git tags through `setuptools-scm`; do not edit a version file.

## Release Checklist

- [ ] Review the package metadata and layout described in `AGENTS.md`.
- [ ] Run `make verify`.
- [ ] Run `make package-check PACKAGE=<import-name>`.
- [ ] Run `make coverage PACKAGE=<import-name>`.
- [ ] Review `CHANGELOG.md` and move relevant `Unreleased` entries into a
      dated version section.
- [ ] Choose a major, minor, or patch version according to Semantic Versioning.
- [ ] Obtain explicit human approval for the version and release.
- [ ] Merge the approved release PR.
- [ ] With explicit human approval, create or confirm the exact version tag on
      the release PR's merge commit to trigger package publication.
- [ ] Confirm the release workflow published the expected package to PyPI.
- [ ] Complete the post-merge GitHub Release follow-up below.

## Post-merge GitHub Release Follow-up

Do not create the GitHub Release until the release PR has merged, the exact
version tag exists, and the approved package publication has completed. The tag
must point to the expected merge commit. Creating a tag, publishing a package,
or creating a release still requires explicit human approval.

1. Record the release PR's merge commit and confirm the exact tag resolves to
   it:

   ```sh
   VERSION=2.0.1
   EXPECTED_COMMIT=<release-pr-merge-commit>
   git fetch origin --tags
   test "$(git rev-parse "${VERSION}^{commit}")" = "$EXPECTED_COMMIT"
   ```

2. Prepare concise release notes from the matching version section in
   `CHANGELOG.md`. After the package publication succeeds and with explicit
   human approval, create the GitHub Release from the existing tag:

   ```sh
   gh release create "$VERSION" \
     --verify-tag \
     --title "$VERSION" \
     --notes-file /path/to/release-notes.md
   ```

   The GitHub UI may be used instead, but select the existing tag and publish
   the release rather than creating a draft or prerelease.

3. Verify that the public release uses the expected tag and commit:

   ```sh
   test "$(gh release view "$VERSION" --json tagName --jq .tagName)" = "$VERSION"
   test "$(gh release view "$VERSION" --json isDraft,isPrerelease \
     --jq '(.isDraft == false and .isPrerelease == false)')" = "true"
   test "$(git rev-parse "${VERSION}^{commit}")" = "$EXPECTED_COMMIT"
   ```

## Agent Boundaries

Agents may update release documentation and run the checklist's validation
commands. They must not create tags, GitHub releases, or package publications
without explicit human approval.
