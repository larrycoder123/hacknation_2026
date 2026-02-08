I am building a "Self-Learning Support Agent Workspace" for a hackathon. 
I need you to generate the Next.js app that mimics a professional tool like Zendesk or Salesforce Service Cloud.

**Layout Requirements (The 3-Pane "Holy Grail" Layout):**
The screen should be full height (h-screen) and hidden overflow, divided into 3 vertical columns:

1. **Left Sidebar (The Queue)**
   - Header: "Ticket Queue"
   - Content: A list of 5 mock tickets. Each card shows:
     - Priority Badge (High/Med/Low) - make 'High' red.
     - Customer Name
     - Subject line (truncate if long)
     - Time ago (e.g., "2m ago")

2. **Center Stage (The Chat)**
   - Header: "Ticket #1024: Compliance Error 505" with a status badge "Open".
   - Message Area: A scrollable chat history.
     - Mock 5 messages
   - Footer: A sticky input area with a textarea and a "Send" button.

3. **Right Sidebar (The Intelligence Layer)**
   - **Header:** "Knowledge Base"
   - **Section 1: Recommended Actions (The Key Feature)**
     - A card for a script with a title and description.
     - Inside: A mock code block showing `UPDATE settings SET...`
     - A distinct, bright blue button: "Auto-Fill & Run".
    - Another card for a knowledge article with a title and description.
     - Inside: A detailed description on how to solve this problem in general
   - **Section 3: Trust & Lineage**
     - Small text at bottom: "Source: Verified from Ticket #9942 (98% Confidence)".

Make this app best practice and professional. 



# Self-Learning Support Agent Workspace - Prompt

I am building a "Self-Learning Support Agent Workspace" for a hackathon. Generate a Next.js app that mimics professional support tools like Zendesk.

**Layout: 3-Column Full-Height Design**

1. **Left Sidebar - Ticket Queue**
   - Header: "Ticket Queue"
   - List of 5 mock tickets showing: Priority badge (High=red, Med=orange, Low=green), Customer name, Subject (truncated), Time ago

2. **Center Panel - Ticket Detail**
   - Header: Ticket number, subject, and status badge
   - Scrollable chat history: Customer messages, Agent messages
   - Sticky footer: Textarea input and "Send" button
   - Top-right corner: "Close Ticket" button (outlined, subtle)

3. **Right Sidebar - AI Assistant**
   - Header: "AI assisted Knowledge Base"
   - **Knowledge Suggestions Section:**
     - Show when agent explicitly requests help (button: "Get Suggestions")
     - Display up to 3 suggested actions returned from backend API, sorted by confidence score (highest first)
     - Each action card shows:
       - Action title
       - Confidence score badge (e.g., "94%" - green if >80%, yellow if 60-80%, gray if <60%)
       - For scripts: Brief description of what it does
       - For articles/guides: Preview snippet
       - Action button: "View Details" or "Use This"
     - If no suggestions: "No suggestions available. Describe the issue for better results."

**Ticket Closure Flow:**
- When "Close Ticket" clicked, show inline modal/dropdown:
  - Quick radio selection: "Resolved Successfully" or "Not Applicable"
  - Optional brief text input: "Notes (optional)"
  - Buttons: "Close Ticket" (primary) and "Cancel"
  - Helper text: "Successful resolutions help improve AI suggestions"

**Interaction Flow:**
- Agent types message and clicks "Get Suggestions" -> Backend returns suggested actions with confidence scores
- Display suggestions sorted by confidence (highest first)
- Agent can apply suggestion or continue manually

**Technical Notes:**
- Use Tailwind CSS for styling
- Make it production-ready: proper TypeScript types, clean component structure
- Mock backend responses for now 
- Keep UI clean, professional, uncluttered, dark theme. Modern corporate UI.
- Schemas can be found under /schemas