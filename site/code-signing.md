---
layout: page
title: Code signing policy
lang: en
description: How the TS-Pico Updater for Windows is signed, who approves each signed release, and what the program sends over the network.
---

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by
[SignPath Foundation](https://signpath.org/).

## What is signed

Only **TS-Pico-Updater.exe**, the Windows version of the TS-Pico updater. It is built from the
[`windows-updater/`](https://github.com/timex-sinclair-projects/tspico-firmware-build/tree/main/windows-updater)
folder of the
[tspico-firmware-build](https://github.com/timex-sinclair-projects/tspico-firmware-build)
repository, which is MIT-licensed. Each build runs in GitHub Actions
([`windows-updater.yml`](https://github.com/timex-sinclair-projects/tspico-firmware-build/blob/main/.github/workflows/windows-updater.yml))
from the repository's source, and a member of the team approves every signing request by hand.

The signed exe shows **SignPath Foundation** as its publisher. You can check it in Windows:
right-click the file, choose **Properties**, then the **Digital Signatures** tab.

## Team roles

<!-- TODO: confirm these with the team. Everyone listed must use MFA on GitHub and SignPath. -->

| Role | Who | What they do |
|---|---|---|
| Committers and reviewers | [the repository's maintainers](https://github.com/orgs/timex-sinclair-projects/people) | Change the source. They review every pull request from anyone outside the team. |
| Approvers | [David Anderson](https://github.com/factus10) | Approve each signing request, after checking that the build came from a reviewed commit on `main`. |

## Privacy policy

This program will not transfer any information to other networked systems unless specifically
requested by the user or the person installing or operating it.

When you press **Start**, the updater downloads the firmware and its files from this site's
updater pages (`timex-sinclair-projects.github.io/tspico-firmware-build/updater/`), hosted on
GitHub Pages. It sends nothing about you or your computer. As with any download, GitHub sees the
request: see [GitHub's privacy statement](https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement).

## Installing and removing

There is nothing to install. The program runs from the file you downloaded and changes nothing
on your computer. To remove it, delete the file.

## Reporting a problem

If you think a signed file from this project is malicious or was not built from this
repository, [open an issue](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues)
or contact [SignPath Foundation](https://signpath.org/).
