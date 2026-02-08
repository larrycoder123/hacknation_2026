"use client";

import { SuggestedAction, ActionType } from '@/types';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Sparkles, Terminal, MessageSquare, AlertCircle, RefreshCw, Star } from 'lucide-react';
import ExpandableText from './ExpandableText';
import MarkdownRenderer from './MarkdownRenderer';

interface AIAssistantProps {
    suggestions: SuggestedAction[];
    isLoading: boolean;
    onGetSuggestions: () => void;
    onApplySuggestion: (suggestion: SuggestedAction) => void;
}

const ConfidenceScore = ({ score }: { score: number }) => {
    let colorClass = 'text-muted-foreground';
    if (score >= 0.8) {
        colorClass = 'text-emerald-500';
    } else if (score >= 0.6) {
        colorClass = 'text-amber-500';
    }

    return (
        <span className={cn("text-[10px] font-mono font-medium", colorClass)}>
            {Math.round(score * 100)}% Match
        </span>
    );
};

const ActionIcon = ({ type }: { type: ActionType }) => {
    switch (type) {
        case 'script':
            return <Terminal className="w-3.5 h-3.5 text-blue-400" />;
        case 'response':
            return <MessageSquare className="w-3.5 h-3.5 text-primary" />;
        default:
            return <AlertCircle className="w-3.5 h-3.5 text-red-500" />;
    }
}

/**
 * AIAssistant Component
 * 
 * Displays AI-generated suggestions for the current conversation.
 * It shows a list of suggested actions (scripts, responses) with confidence scores.
 */
export default function AIAssistant({ suggestions, isLoading, onGetSuggestions, onApplySuggestion }: AIAssistantProps) {
    return (
        <div className="w-[420px] 2xl:w-[500px] h-full flex flex-col bg-background/50 backdrop-blur-xl flex-shrink-0 border border-border rounded-lg shadow-sm overflow-hidden">
            <div className="p-4 h-14 border-b border-border/50 flex items-center justify-between bg-background/50">
                <div className="flex items-center gap-2">
                    <div className="p-1 rounded-md bg-primary/10">
                        <Sparkles className="w-3.5 h-3.5 text-primary" />
                    </div>
                    <h2 className="text-sm font-semibold text-foreground tracking-tight">AI Assistant</h2>
                </div>
                {suggestions.length > 0 && !isLoading && (
                    <Button
                        onClick={onGetSuggestions}
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground rounded-md"
                    >
                        <RefreshCw className="w-3.5 h-3.5" />
                    </Button>
                )}
            </div>

            <div className="flex-1 overflow-y-auto p-4 scrollbar-hide">
                {suggestions.length === 0 && !isLoading ? (
                    <div className="h-full flex flex-col items-center justify-center text-center space-y-4 opacity-0 animate-in fade-in slide-in-from-bottom-4 duration-700 fill-mode-forwards" style={{ animationDelay: '100ms', opacity: 1 }}>
                        <div className="h-10 w-10 rounded-md bg-muted/50 flex items-center justify-center">
                            <Sparkles className="w-5 h-5 text-muted-foreground/40" />
                        </div>
                        <div className="space-y-1 max-w-[200px]">
                            <h3 className="text-sm font-medium text-foreground">No suggestions yet</h3>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                                Analyze conversations to get context-aware actions.
                            </p>
                        </div>
                        <Button
                            onClick={onGetSuggestions}
                            className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm text-xs h-8 px-4"
                            size="sm"
                        >
                            Analyze Context
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {isLoading ? (
                            <div className="space-y-3">
                                {[1, 2, 3].map((i) => (
                                    <div key={i} className="h-32 bg-muted/20 rounded-md animate-pulse border border-border/40"></div>
                                ))}
                            </div>
                        ) : (
                            <>
                                {/* ── Top Suggestion (adapted) ── */}
                                {suggestions.length > 0 && (() => {
                                    const top = suggestions[0];
                                    const rest = suggestions.slice(1);
                                    return (
                                        <>
                                            <div className="flex items-center gap-1.5 px-1 pb-1">
                                                <Star className="w-3 h-3 text-amber-500 fill-amber-500" />
                                                <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Best Match</span>
                                                <ConfidenceScore score={top.confidence_score} />
                                            </div>

                                            <div className="p-3.5 border border-primary/30 rounded-lg bg-primary/5 space-y-3">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <div className="p-1 rounded-md bg-primary/10 border border-primary/20">
                                                            <ActionIcon type={top.type} />
                                                        </div>
                                                        <h3 className="text-sm font-semibold text-foreground leading-tight">{top.title}</h3>
                                                    </div>
                                                </div>

                                                {/* Adapted summary */}
                                                {top.adapted_summary && (
                                                    <div className="text-sm text-foreground/90 leading-relaxed">
                                                        <MarkdownRenderer content={top.adapted_summary} />
                                                    </div>
                                                )}

                                                {/* Source reference */}
                                                <div className="flex items-center justify-between pt-2 border-t border-primary/10">
                                                    <span className="text-[10px] text-muted-foreground font-medium">
                                                        {top.source}
                                                    </span>
                                                    {top.type === 'script' && (
                                                        <Button
                                                            onClick={() => onApplySuggestion(top)}
                                                            size="sm"
                                                            className="h-6 text-[10px] bg-foreground text-background hover:bg-foreground/90 gap-1.5 px-2.5 shadow-sm"
                                                        >
                                                            <Terminal className="w-3 h-3" />
                                                            Run Script
                                                        </Button>
                                                    )}
                                                </div>

                                                {/* Expandable full content */}
                                                <details className="group">
                                                    <summary className="text-[10px] text-muted-foreground cursor-pointer hover:text-foreground transition-colors select-none">
                                                        View full source content
                                                    </summary>
                                                    <div className="mt-2 bg-muted/30 rounded-md p-2.5 border border-border/50">
                                                        <ExpandableText
                                                            content={top.content}
                                                            maxLength={300}
                                                            isMarkdown={top.type !== 'script'}
                                                            className={top.type === 'script' ? "font-mono text-xs" : ""}
                                                        />
                                                    </div>
                                                </details>
                                            </div>

                                            {/* ── Other Suggestions ── */}
                                            {rest.length > 0 && (
                                                <>
                                                    <div className="flex items-center px-1 pt-3 pb-1">
                                                        <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Other Suggestions</span>
                                                    </div>
                                                    {rest.map((suggestion) => (
                                                        <div
                                                            key={suggestion.id}
                                                            className="group p-3 border border-border rounded-md bg-card hover:border-border/80 transition-all shadow-sm space-y-2.5"
                                                        >
                                                            <div className="flex justify-between items-start">
                                                                <div className="flex items-center gap-2">
                                                                    <div className="p-1 rounded-md bg-muted/50 border border-border/50">
                                                                        <ActionIcon type={suggestion.type} />
                                                                    </div>
                                                                    <span className="text-xs font-medium text-muted-foreground capitalize">{suggestion.type}</span>
                                                                </div>
                                                                <ConfidenceScore score={suggestion.confidence_score} />
                                                            </div>

                                                            <div className="space-y-1">
                                                                <h3 className="text-sm font-medium text-foreground leading-tight">{suggestion.title}</h3>
                                                                <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                                                                    {suggestion.description}
                                                                </p>
                                                            </div>

                                                            {suggestion.type === 'script' && (
                                                                <div className="bg-muted/30 rounded-md p-2.5 border border-border/50">
                                                                    <ExpandableText
                                                                        content={suggestion.content}
                                                                        maxLength={150}
                                                                        className="font-mono text-xs"
                                                                    />
                                                                </div>
                                                            )}

                                                            {suggestion.type === 'response' && (
                                                                <div className="bg-muted/30 rounded-md p-2.5 border border-border/50">
                                                                    <ExpandableText
                                                                        content={suggestion.content}
                                                                        maxLength={200}
                                                                        isMarkdown={true}
                                                                    />
                                                                </div>
                                                            )}

                                                            <div className="flex items-center justify-between pt-2 border-t border-border/40">
                                                                <span className="text-[10px] text-muted-foreground truncate max-w-[100px] opacity-70">
                                                                    {suggestion.source}
                                                                </span>
                                                                {suggestion.type === 'script' && (
                                                                    <Button
                                                                        onClick={() => onApplySuggestion(suggestion)}
                                                                        size="sm"
                                                                        className="h-6 text-[10px] bg-foreground text-background hover:bg-foreground/90 gap-1.5 px-2.5 shadow-sm"
                                                                    >
                                                                        <Terminal className="w-3 h-3" />
                                                                        Run
                                                                    </Button>
                                                                )}
                                                            </div>
                                                        </div>
                                                    ))}
                                                </>
                                            )}
                                        </>
                                    );
                                })()}
                            </>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
