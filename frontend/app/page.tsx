"use client";

import { useState, useEffect } from "react";
import {
  Ticket,
  Message,
  SuggestedAction,
  CloseTicketPayload,
  TicketDisplay,
  toTicketDisplay,
  CloseTicketResponse
} from "./types";
import TicketQueue from "../components/TicketQueue";
import TicketDetail from "../components/TicketDetail";
import AIAssistant from "../components/AIAssistant";
import CloseTicketModal from "../components/CloseTicketModal";
import {
  fetchTickets,
  fetchTicketMessages,
  fetchSuggestedActions,
  closeTicket
} from "./api/client";

export default function Home() {
  const [tickets, setTickets] = useState<TicketDisplay[]>([]);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Record<string, Message[]>>({});
  const [suggestions, setSuggestions] = useState<SuggestedAction[]>([]);
  const [isTicketsLoading, setIsTicketsLoading] = useState(true);
  const [isMessagesLoading, setIsMessagesLoading] = useState(false);
  const [isSuggestionsLoading, setIsSuggestionsLoading] = useState(false);
  const [isCloseModalOpen, setIsCloseModalOpen] = useState(false);

  // Lifted state for the input box
  const [inputMessage, setInputMessage] = useState("");

  const selectedTicket = tickets.find((t) => t.id === selectedTicketId) || null;
  const currentMessages = selectedTicketId ? messages[selectedTicketId] || [] : [];

  // Fetch tickets from backend on mount
  useEffect(() => {
    const loadTickets = async () => {
      try {
        const backendTickets = await fetchTickets();
        setTickets(backendTickets.map(toTicketDisplay));
      } catch (error) {
        console.error("Failed to fetch tickets:", error);
      } finally {
        setIsTicketsLoading(false);
      }
    };
    loadTickets();
  }, []);

  // Fetch messages when a ticket is selected
  useEffect(() => {
    if (!selectedTicketId) return;

    // Check if we already have messages for this ticket
    if (messages[selectedTicketId]) return;

    const loadMessages = async () => {
      setIsMessagesLoading(true);
      try {
        const ticketMessages = await fetchTicketMessages(selectedTicketId);
        setMessages((prev) => ({
          ...prev,
          [selectedTicketId]: ticketMessages,
        }));
      } catch (error) {
        console.error("Failed to fetch messages:", error);
      } finally {
        setIsMessagesLoading(false);
      }
    };
    loadMessages();
  }, [selectedTicketId, messages]);

  const handleSelectTicket = (id: string) => {
    setSelectedTicketId(id);
    setSuggestions([]); // Reset suggestions on ticket switch
    setInputMessage(""); // Reset input
  };

  const handleSendMessage = (content: string) => {
    if (!selectedTicketId) return;

    const newMessage: Message = {
      id: `m${Date.now()}`,
      ticket_id: selectedTicketId,
      sender: "agent",
      content,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    setMessages((prev) => ({
      ...prev,
      [selectedTicketId]: [...(prev[selectedTicketId] || []), newMessage],
    }));
  };

  const handleGetSuggestions = async () => {
    if (!selectedTicketId) return;
    setIsSuggestionsLoading(true);
    try {
      const actions = await fetchSuggestedActions(selectedTicketId);
      setSuggestions(actions);
    } catch (error) {
      console.error("Failed to fetch suggestions:", error);
    } finally {
      setIsSuggestionsLoading(false);
    }
  };

  const handleApplySuggestion = (suggestion: SuggestedAction) => {
    if (suggestion.type === "response") {
      // Extract customer communication template or format content
      let summary = suggestion.content;
      if (suggestion.content.includes("Customer Communication Template:")) {
        summary = suggestion.content
          .split("Customer Communication Template:")[1]
          .replace(/"/g, "")
          .trim();
      } else {
        summary = `Based on the article "${suggestion.title}", here is a summary:\n\n${suggestion.description}`;
      }
      setInputMessage(summary);
    } else if (suggestion.type === "script") {
      alert(`Executing Script: ${suggestion.title}\n\n${suggestion.content}`);
    }
  };

  const handleCloseTicket = async (payload: CloseTicketPayload) => {
    if (!selectedTicketId) return;

    try {
      const response: CloseTicketResponse = await closeTicket(payload);

      // Update ticket status locally
      setTickets((prev) =>
        prev.map((t) =>
          t.id === selectedTicketId ? { ...t, status: "Resolved" as const } : t
        )
      );

      // Add system message about closure
      const systemMessage: Message = {
        id: `sys-${Date.now()}`,
        ticket_id: selectedTicketId,
        sender: "system",
        content: `Ticket closed by agent. Resolution: ${payload.resolution_type}. Notes: ${payload.notes || "None"}`,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };

      setMessages((prev) => ({
        ...prev,
        [selectedTicketId]: [...(prev[selectedTicketId] || []), systemMessage],
      }));

      // Log knowledge article if generated
      if (response.knowledge_article) {
        console.log("Knowledge article generated:", response.knowledge_article);
        // You could show a toast or modal here to display the article
      }
    } catch (error) {
      console.error("Failed to close ticket:", error);
    }
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
