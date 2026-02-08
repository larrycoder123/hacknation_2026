"use client";

import { ConversationDisplay, Message } from '@/types';
import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Avatar } from '@/components/ui/avatar';
import { cn } from '@/lib/utils';
import { Send, X, MoreHorizontal, Paperclip } from 'lucide-react';

interface ConversationDetailProps {
    conversation: ConversationDisplay | null;
    messages: Message[];
    onSendMessage: (content: string) => void;
    onCloseConversation: () => void;
    inputMessage?: string;
    onInputChange?: (value: string) => void;
}

/**
 * ConversationDetail Component
 * 
 * Displays the message history of the selected conversation and allows sending new messages.
 * Handles auto-scrolling to the latest message.
 */
export default function ConversationDetail({ conversation, messages, onSendMessage, onCloseConversation, inputMessage, onInputChange }: ConversationDetailProps) {
    const [internalInput, setInternalInput] = useState('');
    const inputValue = inputMessage !== undefined ? inputMessage : internalInput;
    const setInputValue = onInputChange || setInternalInput;
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = () => {
        if (inputValue.trim()) {
            onSendMessage(inputValue);
            setInputValue('');
        }
    };

    if (!conversation) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-background/50 text-muted-foreground gap-2 border border-border rounded-lg shadow-sm m-0">
                <div className="h-12 w-12 rounded-md bg-muted/50 flex items-center justify-center">
                    <MoreHorizontal className="h-6 w-6 opacity-30" />
                </div>
                <p className="text-sm font-medium tracking-tight">Select a conversation</p>
            </div>
        );
    }

    return (
        <div className="flex-1 flex flex-col h-full bg-background relative border border-border rounded-lg shadow-sm overflow-hidden">
            {/* Header */}
            <div className="h-14 border-b border-border flex items-center justify-between px-4 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
                <div className="flex items-center gap-4">
                    <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-2">
                            <span className="text-xs font-mono text-muted-foreground opacity-70">#{conversation.id.slice(0, 8)}</span>
                            <h2 className="text-sm font-semibold text-foreground tracking-tight line-clamp-1">
                                {conversation.subject}
                            </h2>
                            <Badge variant="outline" className={cn(
                                "ml-1.5 text-[10px] uppercase tracking-wider h-4 px-1.5 font-semibold",
                                conversation.status === 'Open' ? "bg-emerald-500/10 text-emerald-600 border-emerald-200/20" : "bg-zinc-100 text-zinc-600"
                            )}>
                                {conversation.status}
                            </Badge>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onCloseConversation}
                        className="h-8 w-8 p-0 sm:w-auto sm:px-3 text-xs gap-1.5 text-muted-foreground hover:text-foreground"
                    >
                        <X className="h-3.5 w-3.5" />
                        <span className="hidden sm:inline">Close</span>
                    </Button>
                </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
                {messages.map((message) => {
                    const isAgent = message.sender === 'agent';
                    const isSystem = message.sender === 'system';

                    if (isSystem) {
                        return (
                            <div key={message.id} className="flex justify-center my-4">
                                <span className="text-xs bg-muted/50 text-muted-foreground px-2 py-1 rounded-full border border-border/50">
                                    {message.content}
                                </span>
                            </div>
                        );
                    }

                    return (
                        <div
                            key={message.id}
                            className={cn(
                                "flex gap-3 max-w-3xl",
                                isAgent ? "ml-auto flex-row-reverse" : ""
                            )}
                        >
                            <div className={cn(
                                "flex flex-col gap-1 min-w-0 max-w-[85%]",
                                isAgent ? "items-end" : "items-start"
                            )}>
                                <div className="flex items-center gap-2">
                                    <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                                        {isAgent ? 'You' : conversation.customerName}
                                    </span>
                                    <span className="text-[10px] text-muted-foreground opacity-50">{message.timestamp}</span>
                                </div>
                                <div
                                    className={cn(
                                        "rounded-lg px-4 py-2 text-sm leading-relaxed shadow-sm w-full",
                                        isAgent
                                            ? "bg-secondary text-foreground border border-transparent"
                                            : "bg-zinc-900 text-foreground border border-border"
                                    )}
                                >
                                    <div className="whitespace-pre-wrap break-words">{message.content}</div>
                                </div>
                            </div>
                        </div>
                    );
                })}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-border bg-background/50">
                <div className="relative rounded-lg border border-border bg-zinc-900/50 focus-within:ring-1 focus-within:ring-ring ring-offset-0 focus-within:border-ring transition-all shadow-sm">
                    <Textarea
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSend();
                            }
                        }}
                        placeholder="Type your reply..."
                        className="min-h-[80px] w-full border-none bg-transparent shadow-none focus-visible:ring-0 p-3 pb-10 resize-none text-sm placeholder:text-muted-foreground/50 leading-relaxed"
                    />
                    <div className="absolute bottom-2 right-2 flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground/40 font-medium select-none mr-2 hidden sm:inline-block">
                            Press Enter to send
                        </span>
                        <Button
                            onClick={handleSend}
                            disabled={!inputValue.trim()}
                            size="sm"
                            className={cn(
                                "h-7 px-3 text-xs font-medium bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm rounded-md transition-all",
                                !inputValue.trim() && "opacity-50"
                            )}
                        >
                            Send Reply
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    );
}
