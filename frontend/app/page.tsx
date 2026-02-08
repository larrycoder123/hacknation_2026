"use client";

import { useState, useEffect } from "react";
import {
  Conversation,
  Message,
  SuggestedAction,
  CloseConversationPayload,
  ConversationDisplay,
  toConversationDisplay,
  CloseConversationResponse
} from "./types";
import ConversationQueue from "../components/ConversationQueue";
import ConversationDetail from "../components/ConversationDetail";
import AIAssistant from "../components/AIAssistant";
import CloseConversationModal from "../components/CloseConversationModal";
import {
  fetchConversations,
  fetchConversationMessages,
  fetchSuggestedActions,
  closeConversation
} from "./api/client";

export default function Home() {
  const [conversations, setConversations] = useState<ConversationDisplay[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Record<string, Message[]>>({});
  const [suggestions, setSuggestions] = useState<SuggestedAction[]>([]);
  const [isConversationsLoading, setIsConversationsLoading] = useState(true);
  const [isMessagesLoading, setIsMessagesLoading] = useState(false);
  const [isSuggestionsLoading, setIsSuggestionsLoading] = useState(false);
  const [isCloseModalOpen, setIsCloseModalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Lifted state for the input box
  const [inputMessage, setInputMessage] = useState("");

  const selectedConversation = conversations.find((c) => c.id === selectedConversationId) || null;
  const currentMessages = selectedConversationId ? messages[selectedConversationId] || [] : [];

  // Fetch conversations from backend on mount
  useEffect(() => {
    const loadConversations = async () => {
      try {
        const backendConversations = await fetchConversations();
        setConversations(backendConversations.map(toConversationDisplay));
      } catch (error) {
        console.error("Failed to fetch conversations:", error);
        setError("Failed to load conversations. Please refresh the page.");
      } finally {
        setIsConversationsLoading(false);
      }
    };
    loadConversations();
  }, []);

  // Fetch messages when a conversation is selected
  useEffect(() => {
    if (!selectedConversationId) return;

    // Check if we already have messages for this conversation
    if (messages[selectedConversationId]) return;

    const loadMessages = async () => {
      setIsMessagesLoading(true);
      try {
        const conversationMessages = await fetchConversationMessages(selectedConversationId);
        setMessages((prev) => ({
          ...prev,
          [selectedConversationId]: conversationMessages,
        }));
      } catch (error) {
        console.error("Failed to fetch messages:", error);
        setError("Failed to load messages.");
      } finally {
        setIsMessagesLoading(false);
      }
    };
    loadMessages();
  }, [selectedConversationId, messages]);

  const handleSelectConversation = (id: string) => {
    setSelectedConversationId(id);
    setSuggestions([]); // Reset suggestions on conversation switch
    setInputMessage(""); // Reset input
  };

  const handleSendMessage = (content: string) => {
    if (!selectedConversationId) return;

    const newMessage: Message = {
      id: `m${Date.now()}`,
      conversation_id: selectedConversationId,
      sender: "agent",
      content,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    setMessages((prev) => ({
      ...prev,
      [selectedConversationId]: [...(prev[selectedConversationId] || []), newMessage],
    }));
  };

  const handleGetSuggestions = async () => {
    if (!selectedConversationId) return;
    setIsSuggestionsLoading(true);
    try {
      const actions = await fetchSuggestedActions(selectedConversationId);
      setSuggestions(actions);
    } catch (error) {
      console.error("Failed to fetch suggestions:", error);
      setError("Failed to fetch suggestions.");
    } finally {
      setIsSuggestionsLoading(false);
    }
  };

  const handleApplySuggestion = (suggestion: SuggestedAction) => {
    if (suggestion.type === "script") {
      alert(`Executing Script: ${suggestion.title}\n\n${suggestion.content}`);
    }
  };

  const handleCloseConversation = async (payload: CloseConversationPayload) => {
    if (!selectedConversationId) return;

    try {
      const response: CloseConversationResponse = await closeConversation(payload);

      // Update conversation status locally
      setConversations((prev) =>
        prev.map((c) =>
          c.id === selectedConversationId ? { ...c, status: "Resolved" as const } : c
        )
      );

      // Add system message about closure
      const systemMessage: Message = {
        id: `sys-${Date.now()}`,
        conversation_id: selectedConversationId,
        sender: "system",
        content: `Conversation closed by agent. Resolution: ${payload.resolution_type}. Notes: ${payload.notes || "None"}`,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };

      setMessages((prev) => ({
        ...prev,
        [selectedConversationId]: [...(prev[selectedConversationId] || []), systemMessage],
      }));

      // Show ticket number as system message
      if (response.ticket?.ticket_number) {
        const ticketMsg: Message = {
          id: `sys-ticket-${Date.now()}`,
          conversation_id: selectedConversationId,
          sender: "system",
          content: `Ticket created: ${response.ticket.ticket_number}`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        };
        setMessages((prev) => ({
          ...prev,
          [selectedConversationId]: [...(prev[selectedConversationId] || []), ticketMsg],
        }));
      }

      // Show learning result as system message
      if (response.learning_result?.gap_classification) {
        const classificationMessages: Record<string, string> = {
          SAME_KNOWLEDGE: "Knowledge confirmed — existing article boosted",
          NEW_KNOWLEDGE: "Knowledge gap detected — new KB article drafted for review",
          CONTRADICTS: "Contradiction detected — existing KB flagged for review",
        };
        const learningMsg: Message = {
          id: `sys-learn-${Date.now()}`,
          conversation_id: selectedConversationId,
          sender: "system",
          content: classificationMessages[response.learning_result.gap_classification]
            || "Learning pipeline completed",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        };
        setMessages((prev) => ({
          ...prev,
          [selectedConversationId]: [...(prev[selectedConversationId] || []), learningMsg],
        }));
      }

      // Show warnings via error banner
      if (response.warnings?.length) {
        setError(response.warnings.join("; "));
      }
    } catch (error) {
      console.error("Failed to close conversation:", error);
      setError("Failed to close conversation.");
    }
  };

  return (
    <main className="flex h-full w-full text-foreground overflow-hidden font-sans antialiased selection:bg-primary/20 relative gap-4 md:gap-6">
      {error && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 bg-destructive/90 text-white px-4 py-2 text-sm flex items-center gap-4 rounded-full shadow-lg backdrop-blur-md animate-in fade-in slide-in-from-top-4">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="font-bold hover:opacity-80">X</button>
        </div>
      )}

      <ConversationQueue
        conversations={conversations}
        selectedConversationId={selectedConversationId}
        onSelectConversation={handleSelectConversation}
      />

      <ConversationDetail
        conversation={selectedConversation}
        messages={currentMessages}
        onSendMessage={handleSendMessage}
        onCloseConversation={() => selectedConversationId && setIsCloseModalOpen(true)}
        inputMessage={inputMessage}
        onInputChange={setInputMessage}
      />

      <AIAssistant
        suggestions={suggestions}
        isLoading={isSuggestionsLoading}
        onGetSuggestions={handleGetSuggestions}
        onApplySuggestion={handleApplySuggestion}
      />

      {selectedConversationId && (
        <CloseConversationModal
          isOpen={isCloseModalOpen}
          onClose={() => setIsCloseModalOpen(false)}
          onConfirm={handleCloseConversation}
          conversationId={selectedConversationId}
        />
      )}
    </main>
  );
}
