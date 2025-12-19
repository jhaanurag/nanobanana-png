# Contributing to nanobanana-png

Thank you for your interest in contributing! Please follow these guidelines to help us keep the project healthy and easy to maintain.

## How to contribute

- Fork the repository and create a new branch for your change (name it descriptively, e.g. `fix/typo`, `feat/new-renderer`).
- Make small, focused commits with clear messages.
- Run tests (if any) and ensure linting passes.
- Open a pull request against the `main` branch and describe the change, the motivation, and any relevant details.

## Code style

- Follow existing project conventions.
- Keep changes minimal and well-scoped.

## Git basics covered in this guide

This repository's maintainers prefer a clean history. Here are the common commands to be aware of:

- Create a branch: `git checkout -b add-contributing-guide`
- Commit changes: `git add <file> && git commit -m "Message"`
- Stash WIP: `git stash push -m "wip: reason"`
- Rebase your branch onto the latest main:
  - `git fetch origin`
  - `git rebase origin/main`
- Merge into `main` (fast-forward preferred):
  - `git checkout main`
  - `git pull --rebase`
  - `git merge --ff-only add-contributing-guide`

## Thank you!

Contributions are appreciated — please be respectful and patient during review.  

---
*This file was added by an automated contribution guide.*
