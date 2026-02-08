# SupportMind Frontend

Next.js 16 agent workspace for customer support. Two pages: a live conversation view with retrieval-based suggestions, and a review page for approving or rejecting generated KB drafts.

## Project Structure

```
src/
├── app/
│   ├── page.tsx                     # Agent workspace (3-column layout)
│   ├── review/page.tsx              # Learning event review page
│   ├── layout.tsx                   # Root layout
│   └── api/client.ts               # Backend API client (fetch wrappers)
├── components/
│   ├── AppNav.tsx                   # Sidebar navigation
│   ├── ConversationQueue.tsx        # Left column: conversation list
│   ├── ConversationDetail.tsx       # Center column: chat messages + input
│   ├── AIAssistant.tsx              # Right column: retrieval suggestions
│   ├── CloseConversationModal.tsx   # Close dialog (resolution type + notes)
│   ├── LearningEventList.tsx        # Learning event list (review page)
│   ├── LearningEventDetail.tsx      # Learning event detail (review page)
│   ├── ExpandableText.tsx           # Collapsible long text display
│   ├── MarkdownRenderer.tsx         # Markdown rendering for responses
│   └── ui/                          # Shadcn/ui primitives (button, badge, input, etc.)
├── hooks/
│   └── useConversationState.ts      # Conversation state management
├── lib/
│   ├── data.ts                      # Static/shared data helpers
│   ├── templateFiller.ts            # Placeholder replacement for script templates
│   └── utils.ts                     # Utility functions (cn, etc.)
└── types/
    └── index.ts                     # TypeScript interfaces matching backend schemas
```

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Agent Workspace | 3-column layout: conversation queue, chat detail, suggestion sidebar |
| `/review` | Learning Events | List of learning events (GAP/CONTRADICTION) with approve/reject actions |

## API Client

`src/app/api/client.ts` wraps all backend calls:

- `getConversations()` — list conversations
- `getConversation(id)` — single conversation
- `getMessages(id)` — message history
- `getSuggestedActions(id)` — trigger retrieval pipeline
- `closeConversation(id, payload)` — close + generate ticket + run learning
- `reviewLearningEvent(id, decision)` — approve/reject KB draft

All calls go to `http://localhost:8000` by default (configurable via `NEXT_PUBLIC_API_URL`).

## Development

```bash
npm install
npm run dev      # http://localhost:3000
npm run build    # Production build
npm run lint     # ESLint
```

Requires the backend running at port 8000 (see [backend/README.md](../backend/README.md)).