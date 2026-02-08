"use client";

import { useState } from "react";
import { SuggestedAction } from "@/types";
import ConversationQueue from "@/components/ConversationQueue";
import ConversationDetail from "@/components/ConversationDetail";
import AIAssistant from "@/components/AIAssistant";
import CloseConversationModal from "@/components/CloseConversationModal";
import { useConversationState } from "@/hooks/useConversationState";

export default function Home() {
  const {
    conversations,
    selectedConversationId,
    currentConversation,
    currentMessages,
    suggestions,
    isSuggestionsLoading,
    isCustomerTyping,
    error,
    setError,
    inputMessage,
    setInputMessage,
    selectConversation,
    sendMessage,
    getSuggestions,
    closeActiveConversation,
  } = useConversationState();

  const [isCloseModalOpen, setIsCloseModalOpen] = useState(false);

  const handleApplySuggestion = (suggestion: SuggestedAction) => {
    if (suggestion.type === "script") {
      alert(`Executing Script: ${suggestion.title}\n\n${suggestion.content}`);
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
        onSelectConversation={selectConversation}
      />

      <ConversationDetail
        conversation={currentConversation}
        messages={currentMessages}
        onSendMessage={sendMessage}
        onCloseConversation={() => selectedConversationId && setIsCloseModalOpen(true)}
        inputMessage={inputMessage}
        onInputChange={setInputMessage}
        isCustomerTyping={isCustomerTyping}
      />

      <AIAssistant
        suggestions={suggestions}
        isLoading={isSuggestionsLoading}
        onGetSuggestions={getSuggestions}
        onApplySuggestion={handleApplySuggestion}
      />

      {selectedConversationId && (
        <CloseConversationModal
          isOpen={isCloseModalOpen}
          onClose={() => setIsCloseModalOpen(false)}
          onConfirm={closeActiveConversation}
          conversationId={selectedConversationId}
        />
      )}
    </main>
  );
}
