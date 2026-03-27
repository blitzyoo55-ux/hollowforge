# HollowForge Frontend Page Regression Design

Date: 2026-03-27

## Scope

Add page-level regression coverage for `ReadyToGo` and `PromptFactory` without changing product behavior.

## Goals

- Lock the primary operator-visible states on `ReadyToGo`.
- Lock the primary operator-visible states on `PromptFactory`.
- Keep tests stable by mocking heavy child components and backend clients.

## Non-Goals

- No refactor of page components.
- No behavior changes to gallery selection, prompt generation, or queue execution.
- No component-level interaction coverage inside `GalleryGrid`, `Lightbox`, or Prompt Factory sub-panels.

## Test Boundaries

### ReadyToGo

- Empty-state rendering when the ready gallery has zero items.
- Error-state rendering when the ready gallery query fails.
- Batch-selection handoff flow at the page level:
  - toggle selection mode
  - select an item through a mocked `GalleryGrid`
  - launch marketing handoff with the expected query string

### PromptFactory

- Shell rendering with mocked capabilities and checkpoint preference queries.
- Quick recipe interaction changing the visible control summary.
- Preview flow rendering latest result sections after a mocked preview mutation succeeds.

## Approach

Use real `QueryClientProvider` and page components, but mock:

- API client functions
- heavyweight child components
- router navigation where page output is the thing under test

This keeps the tests tied to actual page state while avoiding fragile dependency trees.

## Verification

- `npm run test`
- `npm run build`

