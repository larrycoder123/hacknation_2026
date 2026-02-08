import { SuggestedAction, ConversationDisplay, Message } from "@/types";

/**
 * Context data available for template replacement in suggestions.
 */
export interface TemplateContext {
    conversation?: ConversationDisplay | null;
    messages?: Message[];
}

/**
 * Replaces template placeholders in a string with actual values from context.
 * 
 * Supported placeholders:
 * - {{conversation_id}} - Current conversation ID
 * - {{customer_name}} - Customer's name
 * - {{property_id}} - Property ID (derived from conversation ID)
 * - {{ticket_subject}} - Conversation subject
 * - {{current_date}} - Today's date in readable format
 * - {{agent_name}} - Current agent name (placeholder: "Support Agent")
 */
function fillTemplate(template: string, context: TemplateContext): string {
    const { conversation, messages } = context;

    const replacements: Record<string, string> = {
        "{{conversation_id}}": conversation?.id || "N/A",
        "{{customer_name}}": conversation?.customerName || "Customer",
        "{{property_id}}": conversation?.id ? `prop-${conversation.id.slice(0, 4)}` : "N/A",
        "{{ticket_subject}}": conversation?.subject || "N/A",
        "{{current_date}}": new Date().toLocaleDateString("en-US", {
            year: "numeric",
            month: "long",
            day: "numeric",
        }),
        "{{agent_name}}": "Support Agent",
    };

    let result = template;
    for (const [placeholder, value] of Object.entries(replacements)) {
        result = result.replaceAll(placeholder, value);
    }

    return result;
}

/**
 * Processes a list of suggested actions, filling in template placeholders
 * with values from the current conversation context.
 */
export function fillSuggestionTemplates(
    suggestions: SuggestedAction[],
    context: TemplateContext
): SuggestedAction[] {
    return suggestions.map((suggestion) => ({
        ...suggestion,
        title: fillTemplate(suggestion.title, context),
        description: fillTemplate(suggestion.description, context),
        content: fillTemplate(suggestion.content, context),
    }));
}
