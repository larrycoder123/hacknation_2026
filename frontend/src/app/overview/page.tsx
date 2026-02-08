import {
  Brain,
  RefreshCw,
  UserCheck,

} from "lucide-react";

const flowSteps = [
  { title: "Resolved Ticket", desc: "An agent closes a ticket and the resolution becomes a learning signal." },
  { title: "Gap Detection", desc: "The system compares the resolution against existing knowledge automatically." },
  { title: "Draft KB Article", desc: "New or contradicting knowledge is drafted into a KB article by AI." },
  { title: "Human Review", desc: "A reviewer approves, edits, or rejects the draft before publication." },
  { title: "Publish to KB", desc: "Approved articles are embedded and added to the retrieval corpus." },
  { title: "RAG Retrieval", desc: "Future queries score and rerank candidates, learned knowledge improves results." },
];

const features = [
  {
    icon: Brain,
    title: "AI Copilot",
    description:
      "Real-time RAG-powered answer suggestions surface the most relevant scripts, KB articles, and past resolutions while agents handle tickets.",
  },
  {
    icon: RefreshCw,
    title: "Self-Learning Loop",
    description:
      "When a ticket closes, the system compares the resolution against existing knowledge, detecting gaps, contradictions, and confirmations automatically.",
  },
  {
    icon: UserCheck,
    title: "Human-in-the-Loop Review",
    description:
      "Every AI-drafted knowledge article requires explicit human approval before entering the retrieval corpus, keeping quality high.",
  },
];

const techStack = [
  "Next.js",
  "FastAPI",
  "LangGraph",
  "pgvector",
  "Supabase",
  "GPT-4o",
  "Cohere Rerank",
];

const stats = [
  { value: "1,200+", label: "Support Tickets" },
  { value: "150+", label: "KB Articles" },
  { value: "50+", label: "Agent Scripts" },
  { value: "3,072", label: "Embedding Dims" },
];

export default function OverviewPage() {
  return (
    <div className="flex-1 overflow-y-auto bg-background/50 backdrop-blur-xl border border-border rounded-lg shadow-sm">
      <div className="max-w-4xl mx-auto p-8 space-y-12">
        {/* Hero */}
        <section className="space-y-3 text-center pt-8">
          <h1 className="text-4xl font-bold tracking-tight">SupportMind</h1>
          <p className="text-lg text-muted-foreground">
            Self-learning AI support intelligence layer
          </p>
        </section>

        {/* The Problem */}
        <section className="space-y-4">
          <h2 className="text-2xl font-bold tracking-tight">The Problem</h2>
          <p className="text-muted-foreground leading-relaxed">
            Support knowledge lives in scattered scripts, past tickets, and
            tribal memory, so agents waste time searching for answers. New
            resolutions discovered on the floor never make it back into the
            knowledge base, and existing articles drift out of date with no
            systematic way to detect contradictions. Manual KB curation
            doesn&apos;t scale. Teams need an automated learning loop with
            human oversight.
          </p>
        </section>

        {/* How It Works */}
        <section className="space-y-4">
          <h2 className="text-2xl font-bold tracking-tight">How It Works</h2>
          <div className="relative ml-4">
            <div className="absolute left-0 top-4 bottom-4 w-px bg-border" />
            {flowSteps.map(({ title, desc }, i) => (
              <div key={title} className="relative flex items-start gap-5 py-3">
                <div className="relative z-10 w-8 h-8 rounded-full bg-background border-2 border-primary/40 flex items-center justify-center text-xs font-bold text-primary flex-shrink-0 -ml-[15px]">
                  {i + 1}
                </div>
                <div className="pt-1">
                  <p className="font-semibold text-sm leading-none">{title}</p>
                  <p className="text-sm text-muted-foreground mt-1.5">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Key Features */}
        <section className="space-y-4">
          <h2 className="text-2xl font-bold tracking-tight">Key Features</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {features.map(({ icon: Icon, title, description }) => (
              <div
                key={title}
                className="p-4 bg-muted/30 border border-border/50 rounded-lg space-y-2"
              >
                <Icon className="h-6 w-6 text-primary" />
                <h3 className="font-semibold">{title}</h3>
                <p className="text-sm text-muted-foreground">{description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Tech Stack */}
        <section className="space-y-4">
          <h2 className="text-2xl font-bold tracking-tight">Tech Stack</h2>
          <div className="flex flex-wrap gap-2">
            {techStack.map((tech) => (
              <span
                key={tech}
                className="text-xs px-2.5 py-1 bg-muted/50 border border-border/50 rounded-full"
              >
                {tech}
              </span>
            ))}
          </div>
        </section>

        {/* Dataset Stats */}
        <section className="space-y-4 pb-8">
          <h2 className="text-2xl font-bold tracking-tight">Dataset Stats</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {stats.map(({ value, label }) => (
              <div
                key={label}
                className="p-4 bg-muted/30 border border-border/50 rounded-lg text-center"
              >
                <div className="text-2xl font-bold">{value}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  {label}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
