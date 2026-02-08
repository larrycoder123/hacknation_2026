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

      // Log ticket if generated
      if (response.ticket) {
        console.log("Ticket generated:", response.ticket);
        // You could show a toast or modal here to display the ticket
      }
    } catch (error) {
      console.error("Failed to close conversation:", error);
    }
  };

  return (
    <main className="flex h-full w-full bg-background text-foreground overflow-hidden font-sans antialiased selection:bg-primary/30">
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
