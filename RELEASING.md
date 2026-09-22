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
- [ ] Confirm the release workflow published the expected package to PyPI and
      created the GitHub Release with the `.skill` archive attached.

## GitHub Release verification

The release workflow creates the GitHub Release after the PyPI publication
completes. It uses the existing tag, generates release notes, and attaches
`reuters-climate-paragraph.skill`. The tag must point to the expected merge
commit, and creating a tag or publishing a package still requires explicit
human approval.

1. Record the release PR's merge commit and confirm the exact tag resolves to
   it:

   ```sh
   VERSION=2.0.1
   EXPECTED_COMMIT=<release-pr-merge-commit>
   git fetch origin --tags
   test "$(git rev-parse "${VERSION}^{commit}")" = "$EXPECTED_COMMIT"
   ```

2. After the package publication succeeds, verify the GitHub Release and its
   Skill asset:

   ```sh
   gh release view "$VERSION" \
     --json tagName,isDraft,isPrerelease,assets \
     --jq '{
       tag: .tagName,
       draft: .isDraft,
       prerelease: .isPrerelease,
       skill: ([.assets[].name] | index("reuters-climate-paragraph.skill"))
     }'
   ```

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
