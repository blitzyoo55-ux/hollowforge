# HollowForge Frontend

React operator console for HollowForge.

The project-level entrypoint is the root [`../README.md`](../README.md). Use the
root docs first when re-entering the repo:

- `../README.md`
  - repo map and canonical commands
- `../STATE.md`
  - current runtime snapshot and resume checklist
- `../AGENTS.md`
  - local review and operating guidance
- `../code_review.md`
  - HollowForge-specific review expectations

## Local Commands

```bash
npm run dev
npm run lint
npm run test
npm run build
```

## Important Rule

Frontend work is not deploy-ready until `npm run build` has been run. Keep that
step explicit in reviews, handoffs, and deploy notes.
