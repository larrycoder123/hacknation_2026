import { useState, useEffect, useCallback } from "react";
import {
    Conversation,
    Message,
    SuggestedAction,
    CloseConversationPayload,
    ConversationDisplay,
    toConversationDisplay,
    CloseConversationResponse
} from "@/types";
import {
    fetchConversations,
    fetchConversationMessages,
    fetchSuggestedActions,
    closeConversation
} from "@/app/api/client";

export function useConversationState() {
    const [conversations, setConversations] = useState<ConversationDisplay[]>([]);
    const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
    const [messages, setMessages] = useState<Record<string, Message[]>>({});
    const [suggestions, setSuggestions] = useState<SuggestedAction[]>([]);

    const [isConversationsLoading, setIsConversationsLoading] = useState(true);
    const [isMessagesLoading, setIsMessagesLoading] = useState(false);
    const [isSuggestionsLoading, setIsSuggestionsLoading] = useState(false);

    const [error, setError] = useState<string | null>(null);
    const [inputMessage, setInputMessage] = useState("");

    // Fetch conversations on mount
    useEffect(() => {
        const loadConversations = async () => {
            try {
                const backendConversations = await fetchConversations();
                setConversations(backendConversations.map(toConversationDisplay));
            } catch (err) {
                console.error("Failed to fetch conversations:", err);
                setError("Failed to load conversations. Please refresh the page.");
            } finally {
                setIsConversationsLoading(false);
            }
        };
        loadConversations();
    }, []);

    // Fetch messages when selection changes
    useEffect(() => {
        if (!selectedConversationId) return;
        if (messages[selectedConversationId]) return;

        const loadMessages = async () => {
            setIsMessagesLoading(true);
            try {
                const conversationMessages = await fetchConversationMessages(selectedConversationId);
                setMessages((prev) => ({
                    ...prev,
                    [selectedConversationId]: conversationMessages,
                }));
            } catch (err) {
                console.error("Failed to fetch messages:", err);
                setError("Failed to load messages.");
            } finally {
                setIsMessagesLoading(false);
            }
        };
        loadMessages();
    }, [selectedConversationId, messages]);

    const selectConversation = useCallback((id: string) => {
        setSelectedConversationId(id);
        setSuggestions([]);
        setInputMessage("");
    }, []);

    const sendMessage = useCallback((content: string) => {
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
    }, [selectedConversationId]);

    const getSuggestions = useCallback(async () => {
        if (!selectedConversationId) return;
        setIsSuggestionsLoading(true);
        try {
            const actions = await fetchSuggestedActions(selectedConversationId);
            setSuggestions(actions);
        } catch (err) {
            console.error("Failed to fetch suggestions:", err);
            setError("Failed to fetch suggestions.");
        } finally {
            setIsSuggestionsLoading(false);
        }
    }, [selectedConversationId]);

    const closeActiveConversation = useCallback(async (payload: CloseConversationPayload) => {
        if (!selectedConversationId) return;

        try {
            const response: CloseConversationResponse = await closeConversation(payload);

            // Update local status
            setConversations((prev) =>
                prev.map((c) =>
                    c.id === selectedConversationId ? { ...c, status: "Resolved" as const } : c
                )
            );

            // System messages
            const newMessages: Message[] = [];

            newMessages.push({
                id: `sys-${Date.now()}`,
                conversation_id: selectedConversationId,
                sender: "system",
                content: `Conversation closed by agent. Resolution: ${payload.resolution_type}. Notes: ${payload.notes || "None"}`,
                timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            });

            if (response.ticket?.ticket_number) {
                newMessages.push({
                    id: `sys-ticket-${Date.now()}`,
                    conversation_id: selectedConversationId,
                    sender: "system",
                    content: `Ticket created: ${response.ticket.ticket_number}`,
                    timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                });
            }

            if (response.learning_result?.gap_classification) {
                const classificationMessages: Record<string, string> = {
                    SAME_KNOWLEDGE: "Knowledge confirmed — existing article boosted",
                    NEW_KNOWLEDGE: "Knowledge gap detected — new KB article drafted for review",
                    CONTRADICTS: "Contradiction detected — existing KB flagged for review",
                };
                newMessages.push({
                    id: `sys-learn-${Date.now()}`,
                    conversation_id: selectedConversationId,
                    sender: "system",
                    content: classificationMessages[response.learning_result.gap_classification] || "Learning pipeline completed",
                    timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                });
            }

            setMessages((prev) => ({
                ...prev,
                [selectedConversationId]: [...(prev[selectedConversationId] || []), ...newMessages],
            }));

            if (response.warnings?.length) {
                setError(response.warnings.join("; "));
            }

        } catch (err) {
            console.error("Failed to close conversation:", err);
            setError("Failed to close conversation.");
        }
    }, [selectedConversationId]);

    const currentConversation = conversations.find((c) => c.id === selectedConversationId) || null;
    const currentMessages = selectedConversationId ? messages[selectedConversationId] || [] : [];

    return {
        conversations,
        selectedConversationId,
        currentConversation,
        currentMessages,
        suggestions,
        isConversationsLoading,
        isMessagesLoading,
        isSuggestionsLoading,
        error,
        setError,
        inputMessage,
        setInputMessage,
        selectConversation,
        sendMessage,
        getSuggestions,
        closeActiveConversation,
    };
}
