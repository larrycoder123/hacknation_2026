"use client";

import { useState } from "react";
import { Ticket, Message, SuggestedAction, CloseTicketPayload } from "./types";
import { MOCK_TICKETS, MOCK_MESSAGES, MOCK_SUGGESTIONS } from "./data";
import TicketQueue from "../components/TicketQueue";
import TicketDetail from "../components/TicketDetail";
import AIAssistant from "../components/AIAssistant";
import CloseTicketModal from "../components/CloseTicketModal";

export default function Home() {
  const [tickets, setTickets] = useState<Ticket[]>(MOCK_TICKETS);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Record<string, Message[]>>(MOCK_MESSAGES);
  const [suggestions, setSuggestions] = useState<SuggestedAction[]>([]);
  const [isSuggestionsLoading, setIsSuggestionsLoading] = useState(false);
  const [isCloseModalOpen, setIsCloseModalOpen] = useState(false);

  // Lifted state for the input box
  const [inputMessage, setInputMessage] = useState('');

  const selectedTicket = tickets.find((t) => t.id === selectedTicketId) || null;
  const currentMessages = selectedTicketId ? (messages[selectedTicketId] || []) : [];

  const handleSelectTicket = (id: string) => {
    setSelectedTicketId(id);
    setSuggestions([]); // Reset suggestions on ticket switch
    setInputMessage(''); // Reset input
  };

  const handleSendMessage = (content: string) => {
    if (!selectedTicketId) return;

    const newMessage: Message = {
      id: `m${Date.now()}`,
      ticketId: selectedTicketId,
      sender: "agent",
      content,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => ({
      ...prev,
      [selectedTicketId]: [...(prev[selectedTicketId] || []), newMessage],
    }));
  };

  const handleGetSuggestions = () => {
    setIsSuggestionsLoading(true);
    // Simulate API delay
    setTimeout(() => {
      setSuggestions(MOCK_SUGGESTIONS);
      setIsSuggestionsLoading(false);
    }, 1200);
  };

  const handleApplySuggestion = (suggestion: SuggestedAction) => {
    if (suggestion.type === 'response') {
      // "Summarize" and format logic (Mocked)
      // In a real app, this would call an LLM to summarize the article based on the chat context.
      // Here we'll just extract the "Customer Communication Template" part or create a summary.

      // Simple heuristic for the mock:
      let summary = suggestion.content;
      if (suggestion.content.includes("Customer Communication Template:")) {
        summary = suggestion.content.split("Customer Communication Template:")[1].replace(/"/g, '').trim();
      } else {
        // If no template, we just use the description or a placeholder summary
        summary = `Based on the article "${suggestion.title}", here is a summary:\n\n${suggestion.description}`;
      }

      setInputMessage(summary);
    } else if (suggestion.type === 'script') {
      // For scripts, we can maybe show a confirmation or a toast
      alert(`Executing Script: ${suggestion.title}\n\n${suggestion.content}`);
    }
  };

  const handleCloseTicket = (payload: CloseTicketPayload) => {
    if (!selectedTicketId) return;

    setTickets((prev) =>
      prev.map(t => t.id === selectedTicketId ? { ...t, status: 'Resolved' } : t)
    );

    const systemMessage: Message = {
      id: `sys-${Date.now()}`,
      ticketId: selectedTicketId,
      sender: 'system',
      content: `Ticket closed by agent. Resolution: ${payload.resolution_type}. Notes: ${payload.notes || 'None'}`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => ({
      ...prev,
      [selectedTicketId]: [...(prev[selectedTicketId] || []), systemMessage],
    }));
  };

  return (
    <main className="flex h-full w-full bg-background text-foreground overflow-hidden font-sans antialiased selection:bg-primary/30">
      <TicketQueue
        tickets={tickets}
        selectedTicketId={selectedTicketId}
        onSelectTicket={handleSelectTicket}
      />

      <TicketDetail
        ticket={selectedTicket}
        messages={currentMessages}
        onSendMessage={handleSendMessage}
        onCloseTicket={() => selectedTicketId && setIsCloseModalOpen(true)}
        inputMessage={inputMessage}
        onInputChange={setInputMessage}
      />

      <AIAssistant
        suggestions={suggestions}
        isLoading={isSuggestionsLoading}
        onGetSuggestions={handleGetSuggestions}
        onApplySuggestion={handleApplySuggestion}
      />

      {selectedTicketId && (
        <CloseTicketModal
          isOpen={isCloseModalOpen}
          onClose={() => setIsCloseModalOpen(false)}
          onConfirm={handleCloseTicket}
          ticketId={selectedTicketId}
        />
      )}
    </main>
  );
}
