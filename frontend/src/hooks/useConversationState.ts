/**
 * Central state hook for the agent workspace page.
 *
 * Manages:
 *   - Conversation list (fetched on mount from backend)
 *   - Selected conversation + its messages (lazy-loaded on selection)
 *   - AI suggestions (fetched on demand via getSuggestions, template-filled)
 *   - Close flow (calls backend close endpoint, appends system messages for
 *     ticket number and learning classification to the chat)
 *   - Loading / error state for each async operation
 */

import { useState, useEffect, useCallback, useRef } from "react";
import {
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
    closeConversation,
    simulateCustomerReply
} from "@/app/api/client";
import { fillSuggestionTemplates } from "@/lib/templateFiller";

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
    const [isCustomerTyping, setIsCustomerTyping] = useState(false);
    const usedSuggestionIdsRef = useRef<Set<string>>(new Set());
    const sessionSuggestionsRef = useRef<SuggestedAction[]>([]);

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
        usedSuggestionIdsRef.current.clear();
        sessionSuggestionsRef.current = [];
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

        const updatedMessages = [...(messages[selectedConversationId] || []), newMessage];
        setMessages((prev) => ({
            ...prev,
            [selectedConversationId]: updatedMessages,
        }));

        // LLM-powered customer simulation
        const convId = selectedConversationId;
        const delay = 1000 + Math.random() * 2000; // 1-3s random delay

        setTimeout(async () => {
            setIsCustomerTyping(true);
            try {
                const simMessages = updatedMessages
                    .filter((m) => m.sender === "agent" || m.sender === "customer")
                    .map((m) => ({ sender: m.sender as "agent" | "customer", content: m.content }));

                const result = await simulateCustomerReply(convId, simMessages);

                const reply: Message = {
                    id: `m-sim-${Date.now()}`,
                    conversation_id: convId,
                    sender: "customer",
                    content: result.content,
                    timestamp: new Date().toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                    }),
                };
                setMessages((prev) => ({
                    ...prev,
                    [convId]: [...(prev[convId] || []), reply],
                }));
            } catch (err) {
                console.error("Customer simulation failed:", err);
            } finally {
                setIsCustomerTyping(false);
            }
        }, delay);
    }, [selectedConversationId, messages]);

    const getSuggestions = useCallback(async () => {
        if (!selectedConversationId) return;
        setIsSuggestionsLoading(true);
        try {
            // Send live messages so RAG uses the latest customer context
            const conversationMessages = messages[selectedConversationId] || [];
            const liveMessages = conversationMessages
                .filter((m) => m.sender === "agent" || m.sender === "customer")
                .map((m) => ({ sender: m.sender as "agent" | "customer", content: m.content }));

            const excludeIds = Array.from(usedSuggestionIdsRef.current);

            const actions = await fetchSuggestedActions(selectedConversationId, liveMessages, excludeIds);

            // Track these suggestion IDs as used
            actions.forEach((a) => usedSuggestionIdsRef.current.add(a.id));

            // Find current conversation for template context
            const conversation = conversations.find(c => c.id === selectedConversationId) || null;
            // Fill in template placeholders with actual context values
            const filledActions = fillSuggestionTemplates(actions, {
                conversation,
                messages: conversationMessages,
            });
            setSuggestions(filledActions);

            // Accumulate all suggestions shown during this session (deduped by id)
            const existingIds = new Set(sessionSuggestionsRef.current.map(s => s.id));
            for (const action of filledActions) {
                if (!existingIds.has(action.id)) {
                    sessionSuggestionsRef.current.push(action);
                    existingIds.add(action.id);
                }
            }
        } catch (err) {
            console.error("Failed to fetch suggestions:", err);
            setError("Failed to fetch suggestions.");
        } finally {
            setIsSuggestionsLoading(false);
        }
    }, [selectedConversationId, conversations, messages]);

    const closeActiveConversation = useCallback(async (payload: CloseConversationPayload): Promise<CloseConversationResponse | null> => {
        if (!selectedConversationId) return null;

        try {
            const response: CloseConversationResponse = await closeConversation(payload);

            // Update local status
            setConversations((prev) =>
                prev.map((c) =>
                    c.id === selectedConversationId ? { ...c, status: "Resolved" as const } : c
                )
            );

            // System messages (audit trail in chat)
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

            return response;

        } catch (err) {
            console.error("Failed to close conversation:", err);
            setError("Failed to close conversation.");
            return null;
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
        sessionSuggestions: sessionSuggestionsRef.current,
        isConversationsLoading,
        isMessagesLoading,
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
    };
}
