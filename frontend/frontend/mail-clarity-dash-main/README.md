# Mail AI Assistant

Build "iMail" dashboard and Chrome extension panel as plain React functional components 

with Tailwind CSS utility classes only (no shadcn, no component libraries) — this code is 

meant to be adapted into a team codebase, not just demoed, so keep it simple, readable, 

and conventionally structured.

STRUCTURE

Separate mock data from components:

 - /mockData — sample email objects, kept in one file, matching the data shape below

 - /components — presentational components only, no data generation inside them

DATA SHAPE (this is the contract the components should expect as props — treat it as 

the interface the rest of the pipeline will eventually fill in for real):

Email = {

  id, sender, subject, preview, timestamp, priority ("high"|"medium"|"low"),

  threadContext: [ { sender, snippet } ],

  aiSummary: string,

  actionItems: [ string ],

  draftReply: string,

  tone: "professional" | "casual",

  sources: [ { label } ],

  piiMasked: boolean,

  criticConfidence: number  // 0-1, from the Critic Agent

}

COMPONENTS

 - InboxList / EmailListItem — renders the email list with priority badges

 - EmailDetailPanel — composes AISummaryCard, ActionItemsList, DraftReplyEditor, 

   SourcesChips, RefineInput

 - ToneToggle — Professional/Casual switch, controlled component

 - ApproveSendButton — takes an onApproveSend(emailId) callback prop (stub with 

   console.log for now) — this must be the only path that "sends," and should be 

   visually and functionally distinct from Regenerate/Refine actions

 - ExtensionPanel — reuses the same child components in a condensed layout, doesn't 

   duplicate their logic

BEHAVIOR

 - Selecting an email in InboxList updates EmailDetailPanel via props/state, not global 

   state library — keep it simple (useState/lift state up is fine)

 - Regenerate and refine-with-AI actions should be stubbed functions clearly named so 

   they're easy to wire to a real API later (e.g. onRegenerate, onRefine)

 - criticConfidence and piiMasked should be displayed as small indicators (e.g. a badge 

   or icon), since these map to actual project goals (80% critic confidence, PII masking 

   accuracy) and may get asked about later

STYLE

Clean corporate SaaS aesthetic, neutral grays/blues. Prioritize readable component code 

over visual polish — this needs to be easy for teammates to read and extend.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/89e8a0c8-d59d-4141-b1ce-ccd6a2b209c1).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
